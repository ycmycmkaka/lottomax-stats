import pandas as pd
import requests
from bs4 import BeautifulSoup
import re
import time

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

MAX_NUMBER = 52


def extract_numbers_from_text(text: str):
    """
    由文字入面抽出 1-52 號碼。
    """
    return [int(x) for x in re.findall(r'\b([1-9]|[1-4]\d|5[0-2])\b', text)]


def get_zone_number(n: int) -> int:
    """
    分區規則：
    1-10   -> 1區
    11-20  -> 2區
    21-30  -> 3區
    31-40  -> 4區
    41-52  -> 5區
    """
    if 1 <= n <= 10:
      return 1
    if n <= 20:
      return 2
    if n <= 30:
      return 3
    if n <= 40:
      return 4
    return 5


def scrape_url(url, all_draws):
    print(f"📡 嘗試獲取數據: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')

        found_in_table = False

        # 方法 1：表格抽取
        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) < 2:
                continue

            raw_date = cols[0].get_text(" ", strip=True)

            date_match = re.search(
                r'([A-Za-z]+,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}|[A-Za-z]+\s+\d{1,2},\s+\d{4})',
                raw_date
            )
            if not date_match:
                continue

            date_str = date_match.group(1)
            date_obj = pd.to_datetime(date_str, errors="coerce")
            if pd.isna(date_obj):
                continue

            clean_date = date_obj.strftime("%Y-%m-%d")

            balls = []
            for element in cols[1].find_all(['li', 'div', 'span', 'a']):
                txt = element.get_text(strip=True)
                if txt.isdigit():
                    val = int(txt)
                    if 1 <= val <= MAX_NUMBER:
                        balls.append(val)

            if len(balls) < 7:
                txt = cols[1].get_text(" ", strip=True)
                balls = extract_numbers_from_text(txt)

            ordered = []
            for n in balls:
                if n not in ordered:
                    ordered.append(n)

            if len(ordered) < 7:
                continue

            nums = sorted(ordered[:7])

            prize_formatted = "-"
            if len(cols) >= 3:
                prize_text = cols[2].get_text(" ", strip=True)
                money_match = re.search(r'\$([0-9,]+)', prize_text)
                if money_match:
                    val = int(money_match.group(1).replace(',', ''))
                    prize_formatted = f"${val // 1000000}M" if val >= 1000000 else f"${val:,}"
                elif "million" in prize_text.lower():
                    num_match = re.search(r'([0-9]+)\s*Million', prize_text, re.IGNORECASE)
                    if num_match:
                        prize_formatted = f"${num_match.group(1)}M"

            detail_url = f"https://ca.lottonumbers.com/lotto-max/numbers/{clean_date}"

            all_draws.append({
                'date': clean_date,
                'n1': nums[0],
                'n2': nums[1],
                'n3': nums[2],
                'n4': nums[3],
                'n5': nums[4],
                'n6': nums[5],
                'n7': nums[6],
                'prize': prize_formatted,
                'detail_url': detail_url
            })
            found_in_table = True

        # 方法 2：Regex 後備抽取
        if not found_in_table:
            text = soup.get_text("\n", strip=True)
            months = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
            pattern = re.compile(
                rf"(Tuesday|Friday)\s+{months}\s+(\d{{1,2}})\s+(20\d{{2}})(.*?)"
                rf"(?=(Tuesday|Friday)\s+{months}\s+\d{{1,2}}\s+20\d{{2}}|$)",
                re.S
            )

            for m in pattern.finditer(text):
                date_str = f"{m.group(2)} {m.group(3)} {m.group(4)}"
                date_obj = pd.to_datetime(date_str, errors="coerce")
                if pd.isna(date_obj):
                    continue

                clean_date = date_obj.strftime("%Y-%m-%d")
                block = m.group(5)

                balls = extract_numbers_from_text(block)

                ordered = []
                for n in balls:
                    if n not in ordered:
                        ordered.append(n)

                if len(ordered) < 7:
                    continue

                nums = sorted(ordered[:7])

                prize_formatted = "-"
                money_match = re.search(r'\$([0-9,]+)', block)
                if money_match:
                    val = int(money_match.group(1).replace(',', ''))
                    prize_formatted = f"${val // 1000000}M" if val >= 1000000 else f"${val:,}"

                all_draws.append({
                    'date': clean_date,
                    'n1': nums[0],
                    'n2': nums[1],
                    'n3': nums[2],
                    'n4': nums[3],
                    'n5': nums[4],
                    'n6': nums[5],
                    'n7': nums[6],
                    'prize': prize_formatted,
                    'detail_url': f"https://ca.lottonumbers.com/lotto-max/numbers/{clean_date}"
                })

    except Exception as e:
        print(f"⚠️ 讀取 {url} 時發生錯誤: {e}")


def get_web_data():
    all_draws = []
    urls = [
        "https://ca.lottonumbers.com/lotto-max/past-numbers",
        "https://ca.lottonumbers.com/lotto-max/numbers/2026",
        "https://ca.lottonumbers.com/lotto-max/numbers/2025",
        "https://ca.lottonumbers.com/lotto-max/numbers/2024",
        "https://ca.lottonumbers.com/lotto-max/numbers/2023",
        "https://ca.lottonumbers.com/lotto-max/numbers/2022"
    ]

    for url in urls:
        scrape_url(url, all_draws)

    return pd.DataFrame(all_draws)


def calculate_metrics(df):
    df['date_obj'] = pd.to_datetime(df['date'], errors='coerce')
    df = df.dropna(subset=['date_obj'])
    df = df.sort_values('date_obj', ascending=True)

    # 用日期去重
    df = df.drop_duplicates(subset=['date_obj'], keep='first').copy()

    # 補抓獎金
    for idx, row in df.iterrows():
        if row['prize'] == '-':
            try:
                r = requests.get(row['detail_url'], headers=HEADERS, timeout=10)
                text = BeautifulSoup(r.text, "html.parser").get_text(" ", strip=True)
                m = re.search(r"Jackpot:\s*\$([0-9,]+)", text, re.I)
                if m:
                    val = int(m.group(1).replace(',', ''))
                    df.at[idx, 'prize'] = f"${val // 1000000}M" if val >= 1000000 else f"${val:,}"
                time.sleep(0.5)
            except Exception:
                pass

    prev_numbers = set()
    results = []

    for _, row in df.iterrows():
        row_dict = row.to_dict()
        nums = [int(row_dict[f'n{i}']) for i in range(1, 8)]

        odds = sum(1 for n in nums if n % 2 != 0)
        row_dict['odd_even'] = f"{odds}單 {7 - odds}雙"

        consec_count = 0
        for i in range(len(nums) - 1):
            if nums[i + 1] - nums[i] == 1:
                consec_count += 1
        row_dict['consecutive'] = f"{consec_count} 個連續"

        curr_set = set(nums)
        row_dict['repeats'] = len(curr_set.intersection(prev_numbers)) if prev_numbers else 0
        prev_numbers = curr_set

        zones_hit = sorted({get_zone_number(n) for n in nums})
        row_dict['zone'] = f"{len(zones_hit)}個區 ({','.join(map(str, zones_hit))})"

        results.append(row_dict)

    final_df = pd.DataFrame(results).sort_values('date_obj', ascending=False)
    final_df['date'] = final_df['date_obj'].dt.strftime('%Y-%m-%d')

    cols_to_keep = [
        'date',
        'n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'n7',
        'prize',
        'odd_even',
        'consecutive',
        'repeats',
        'zone'
    ]
    return final_df[cols_to_keep]


def main():
    print("🚀 啟動 Lotto Max 全自動網頁爬蟲...")
    df = get_web_data()

    if len(df) > 0:
        final_df = calculate_metrics(df)
        final_df.to_csv('data.csv', index=False)
        print(f"✅ 大功告成！成功抓取並分析咗 {len(final_df)} 期數據。")
    else:
        print("❌ 錯誤：爬唔到任何數據。")


if __name__ == "__main__":
    main()
