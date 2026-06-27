"""
update_data.py
警視庁メールけいしちょうオープンデータを取得し、data.jsonを更新する
毎月1日にGitHub Actionsから自動実行される
"""
import requests
import json
import re
import random
from io import StringIO
import csv
from datetime import datetime, timedelta

# ---- 区市の代表座標 ----
AREA_COORDS = {
    '千代田区': (35.6940, 139.7536), '中央区': (35.6709, 139.7730),
    '港区': (35.6581, 139.7514), '新宿区': (35.6938, 139.7036),
    '文京区': (35.7078, 139.7520), '台東区': (35.7126, 139.7793),
    '墨田区': (35.7098, 139.8012), '江東区': (35.6731, 139.8171),
    '品川区': (35.6093, 139.7300), '目黒区': (35.6415, 139.6985),
    '大田区': (35.5617, 139.7162), '世田谷区': (35.6464, 139.6534),
    '渋谷区': (35.6627, 139.7043), '中野区': (35.7074, 139.6655),
    '杉並区': (35.6993, 139.6366), '豊島区': (35.7245, 139.7167),
    '北区': (35.7528, 139.7335), '荒川区': (35.7358, 139.7837),
    '板橋区': (35.7527, 139.7096), '練馬区': (35.7358, 139.6521),
    '足立区': (35.7754, 139.8044), '葛飾区': (35.7345, 139.8477),
    '江戸川区': (35.7067, 139.8682),
    '八王子市': (35.6664, 139.3160), '立川市': (35.6927, 139.4081),
    '武蔵野市': (35.7073, 139.5700), '三鷹市': (35.6838, 139.5581),
    '青梅市': (35.7879, 139.2760), '府中市': (35.6691, 139.4775),
    '昭島市': (35.7055, 139.3534), '調布市': (35.6518, 139.5437),
    '町田市': (35.5488, 139.4427), '小金井市': (35.7000, 139.5013),
    '小平市': (35.7274, 139.4756), '日野市': (35.6712, 139.3960),
    '東村山市': (35.7546, 139.4681), '国分寺市': (35.7008, 139.4622),
    '国立市': (35.6841, 139.4387), '福生市': (35.7382, 139.3309),
    '多摩市': (35.6367, 139.4465), '稲城市': (35.6381, 139.5043),
    '羽村市': (35.7681, 139.3115), 'あきる野市': (35.7290, 139.2940),
    '西東京市': (35.7251, 139.5383),
}

# ---- 住所抽出パターン ----
ADDR_PATTERN = r'((?:千代田|中央|港|新宿|文京|台東|墨田|江東|品川|目黒|大田|世田谷|渋谷|中野|杉並|豊島|北|荒川|板橋|練馬|足立|葛飾|江戸川)区|(?:八王子|立川|武蔵野|三鷹|青梅|府中|昭島|調布|町田|小金井|小平|日野|東村山|国分寺|国立|福生|多摩|稲城|羽村|あきる野|西東京)市)([\u3040-\u9fff\u30a0-\u30ffA-Za-z0-9０-９]+?[0-9０-９一二三四五六七八九十]+丁目)'
TOWN_PATTERN = r'((?:千代田|中央|港|新宿|文京|台東|墨田|江東|品川|目黒|大田|世田谷|渋谷|中野|杉並|豊島|北|荒川|板橋|練馬|足立|葛飾|江戸川)区|(?:八王子|立川|武蔵野|三鷹|青梅|府中|昭島|調布|町田|小金井|小平|日野|東村山|国分寺|国立|福生|多摩|稲城|羽村|あきる野|西東京)市)([\u3040-\u9fff]{2,8}(?:町|台|ケ丘|が丘|ヶ丘)(?:[0-9０-９\-−－][0-9０-９\-−－]*)?)'


def pseudo_geocode(ku, cho):
    base = AREA_COORDS.get(ku)
    if not base:
        return None, None
    seed = hash(cho) % 10000
    rng = random.Random(seed)
    dlat = (rng.random() - 0.5) * 0.04
    dlng = (rng.random() - 0.5) * 0.05
    return round(base[0] + dlat, 6), round(base[1] + dlng, 6)


def get_kind(title):
    title = str(title)
    if re.search(r'ひったくり', title): return 'ひったくり'
    if re.search(r'強盗', title): return '強盗'
    if re.search(r'わいせつ|痴漢', title): return 'わいせつ'
    if re.search(r'子供', title): return '子供への声かけ'
    if re.search(r'声かけ|不審者|つきまとい', title): return '声かけ・不審者'
    if re.search(r'窃盗|自転車盗|車上', title): return '窃盗'
    if re.search(r'通り魔', title): return '通り魔'
    if re.search(r'詐欺|アポ電', title): return '詐欺'
    return 'その他'


def fetch_csv():
    """警視庁メールけいしちょうオープンデータを取得（過去2年分）"""
    rows = []
    today = datetime.today()
    for delta in range(0, 25):  # 最大25ヶ月前まで
        dt = today - timedelta(days=delta * 30)
        year = dt.year
        url = f'https://mail.keishicho.metro.tokyo.lg.jp/opendata/csv/{year}.csv'
        try:
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                r.encoding = 'utf-8-sig'
                reader = csv.DictReader(StringIO(r.text))
                for row in reader:
                    rows.append(row)
                print(f'{year}年: {len(rows)}件取得')
                break
        except Exception as e:
            print(f'{year}年取得失敗: {e}')
    return rows


def parse_rows(rows):
    records = []
    seen = set()
    for row in rows:
        text  = str(row.get('配信本文', ''))
        title = str(row.get('配信表題', ''))
        date  = str(row.get('配信日時', ''))[:10]

        matches = re.findall(ADDR_PATTERN, text) or re.findall(TOWN_PATTERN, text)
        for ku, cho in matches:
            lat, lng = pseudo_geocode(ku, cho)
            if not lat:
                continue
            key = (ku + cho, date, get_kind(title))
            if key in seen:
                continue
            seen.add(key)
            records.append({'lat': lat, 'lng': lng, 'k': get_kind(title), 'd': date, 'a': ku + cho})
    return records


if __name__ == '__main__':
    print('データ取得開始...')
    rows = fetch_csv()
    records = parse_rows(rows)
    print(f'件数: {len(records)}')

    with open('data.json', 'w', encoding='utf-8') as f:
        json.dump(records, f, ensure_ascii=False, separators=(',', ':'))
    print('data.json を更新しました')
