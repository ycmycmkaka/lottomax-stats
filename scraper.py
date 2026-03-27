import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime
import re
import time

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}

def scrape_url(url, all_draws):
    print(f"📡 嘗試獲取數據: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, 'html.parser')
        
        found_in_table = False
        # 第一個方法：喺表格入面搵
        for row in soup.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) >= 2:
                raw_date = cols[0].get_text(" ", strip=True)
                
                # 🌟 完美避開 "with MAXMILLIONS"：只精準抽出 月份, 日期, 年份
                date_match = re.search(r'([A-Za-z]+,\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}|[A-Za-z]+\s+\d{1,2},\s+\d{4})', raw_date)
                if not date_match:
                    continue
                    
                date_str = date_match.group(1)
                date_obj = pd.to_datetime(date_str, errors="coerce")
                if pd.isna(date_obj):
                    continue
                clean_date = date_obj.strftime("%Y-%m-%d")
                
                # 抽號碼
                balls = []
                for element in cols[1].find_all(['li', 'div', 'span', 'a']):
                    txt = element.get_text(strip=True)
                    if txt.isdigit():
                        balls.append(int(txt))
                        
                if len(balls) < 7:
                    txt = cols[1].get_text(" ", strip=True)
                    balls = [int(x) for x in re.findall(r"\b([1-9]|[1-4]\d|50)\b", txt)]
                
                # 防重覆、抽頭7個主波
                ordered = []
                for n in balls:
                    if n not in ordered: ordered.append(n)
                if len(ordered) < 7: continue
                nums = sorted(ordered[:7])
                
                # 抽獎金
                prize_formatted = "-"
                if len(cols) >= 3:
                    prize_text = cols[2].get_text(" ", strip=True)
                    money_match = re.search(r'\$([0-9,]+)', prize_text)
                    if money_match:
                        val = int(money_match.group(1).replace(',', ''))
                        prize_formatted = f"${val // 1000000}M" if val >= 1000000 else f"${val:,}"
                    elif "million" in prize_text.lower():
                        num_match = re.search(r'([0-9]+)\s*Million', prize_text, re.IGNORECASE)
                        if num_match: prize_formatted = f"${num_match.group(1)}M"

                detail_url = f"https://ca.lottonumbers.com/lotto-max/numbers/{clean_date}"
                
                all_draws.append({
                    'date': clean_date,
                    'n1': nums[0], 'n2': nums[1], 'n3': nums[2],
                    'n4': nums[3], 'n5': nums[4], 'n6': nums[5], 'n7': nums[6],
                    'prize': prize_formatted,
                    'detail_url': detail_url
                })
                found_in_table = True
                
        # 第二個方法：如果表格搵唔到，用 Regex 強制抽取內文 (防護網)
        if not found_in_table:
            text = soup.get_text("\n", strip=True)
            MONTHS = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
            pattern = re.compile(
                rf"(Tuesday|Friday)\s+{MONTHS}\s+(\d{{1,2}})\s+(20\d{{2}})(.*?)"
                rf"(?=(Tuesday|Friday)\s+{MONTHS}\s+\d{{1,2}}\s+20\d{{2}}|$)", re.S
            )
            for m in pattern.finditer(text):
                date_str = f"{m.group(2)} {m.group(3)} {m.group(4)}"
                date_obj = pd.to_datetime(date_str, errors="coerce")
                if pd.isna(date_obj): continue
                clean_date = date_obj.strftime("%Y-%m-%d")

                block = m.group(5)
                balls = [int(x) for x in re.findall(r"\b([1-9]|[1-4]\d|50)\b", block)]
                ordered = []
                for n in balls:
                    if n not in ordered: ordered.append(n)
                if len(ordered) < 7: continue
                nums = sorted(ordered[:7])

                prize_formatted = "-"
                money_match = re.search(r'\$([0-9,]+)', block)
                if money_match:
                    val = int(money_match.group(1).replace(',', ''))
                    prize_formatted = f"${val // 1000000}M" if val >= 1000000 else f"${val:,}"
                
                all_draws.append({
                    'date': clean_date, 'n1': nums[0], 'n2': nums[1], 'n3': nums[2],
                    'n4': nums[3], 'n5': nums[4], 'n6': nums[5], 'n7': nums[6],
                    'prize': prize_formatted,
                    'detail_url': f"https://ca.lottonumbers.com/lotto-max/numbers/{clean_date}"
                })

    except Exception as e:
        print(f"⚠️ 讀取 {url} 時發生錯誤: {e}")

def get_web_data():
    all_draws = []
    # 🌟 換晒你指定嘅新網址
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
    
    # 🌟 終極防重覆：用日期物件做基準剷走 Duplicate，絕不手軟
    df = df.drop_duplicates(subset=['date_obj'], keep='first').copy()
    
    # 🌟 補漏獎金機制：如果刮唔到獎金，自動入去詳細頁面刮
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
            except:
                pass
    
    prev_numbers = set()
    results = []
    
    for _, row in df.iterrows():
        row_dict = row.to_dict()
        nums = [int(row_dict[f'n{i}']) for i in range(1, 8)]
        
        odds = sum(1 for n in nums if n % 2 != 0)
        row_dict['odd_even'] = f"{odds}單 {7-odds}雙"
        
        # 精準計算有幾多個連續
        consec_count = 0
        for i in range(len(nums)-1):
            if nums[i+1] - nums[i] == 1:
                consec_count += 1
        row_dict['consecutive'] = f"{consec_count} 個連續"
        
        curr_set = set(nums)
        row_dict['repeats'] = len(curr_set.intersection(prev_numbers)) if prev_numbers else 0
        prev_numbers = curr_set
        
        zones_hit = set([(n - 1) // 10 + 1 for n in nums])
        zones_list = sorted(list(zones_hit))
        row_dict['zone'] = f"{len(zones_list)}個區 ({','.join(map(str, zones_list))})"
        
        results.append(row_dict)
        
    final_df = pd.DataFrame(results).sort_values('date_obj', ascending=False)
    final_df['date'] = final_df['date_obj'].dt.strftime('%Y-%m-%d')
    
    cols_to_keep = ['date', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'n7', 'prize', 'odd_even', 'consecutive', 'repeats', 'zone']
    return final_df[cols_to_keep]

def main():
    print("🚀 啟動 Lotto Max 全自動網頁爬蟲 (全新 ca.lottonumbers.com 完美版)...")
    df = get_web_data()
    
    if len(df) > 0:
        final_df = calculate_metrics(df)
        final_df.to_csv('data.csv', index=False)
        print(f"✅ 大功告成！全自動抓取並分析咗 {len(final_df)} 期無瑕疵數據！")
    else:
        print("❌ 錯誤：爬唔到任何數據。")

if __name__ == "__main__":
    main()
