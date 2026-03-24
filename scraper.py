import pandas as pd
import os

def calculate_metrics(df):
    date_col = next((c for c in df.columns if 'date' in c.lower()), None)
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col], errors='coerce')
        df = df.sort_values(date_col)

    cols_map = {c.lower().strip(): c for c in df.columns}
    target_cols = [cols_map[f'n{i}'] for i in range(1, 8) if f'n{i}' in cols_map]

    if len(target_cols) < 7:
        print(f"❌ 搵唔到 n1-n7 欄位！現有欄位：{list(df.columns)}")
        return df

    prev_numbers = set()
    results = []

    for _, row in df.iterrows():
        # 【關鍵修復】將 Pandas Row 轉換為 Dictionary，咁就可以隨便加新 Column
        row_dict = row.to_dict()

        nums = []
        for col in target_cols:
            val = str(row_dict[col]).strip()
            if val.isdigit():
                nums.append(int(val))
        
        # 如果嗰行搵唔齊 7 個號碼，照樣保留原數據，然後跳過計算
        if len(nums) < 7:
            results.append(row_dict)
            continue

        nums.sort()
        
        # 1. 單雙
        odds = len([n for n in nums if n % 2 != 0])
        row_dict['odd_even'] = f"{odds}O{7-odds}E"
        
        # 2. 連續
        has_consec = "No"
        for i in range(len(nums)-1):
            if nums[i+1] - nums[i] == 1:
                has_consec = "Yes"
                break
        row_dict['consecutive'] = has_consec
        
        # 3. 上期重複
        current_numbers = set(nums)
        row_dict['repeats'] = len(current_numbers.intersection(prev_numbers)) if prev_numbers else 0
        prev_numbers = current_numbers
        
        # 4. 分區 (Zone)
        row_dict['zone'] = f"Z{(nums[0]-1)//7 + 1}"
        
        # 將加咗新料嘅 Dictionary 放回結果清單
        results.append(row_dict)

    # 重新組裝做 DataFrame
    final_df = pd.DataFrame(results)
    if date_col:
        final_df = final_df.sort_values(date_col, ascending=False)
    return final_df

def main():
    if os.path.exists('data.csv'):
        df = pd.read_csv('data.csv')
        updated_df = calculate_metrics(df)
        updated_df.to_csv('data.csv', index=False)
        print("✅ 成功解決 KeyError，數據已更新！")
    else:
        print("❌ 搵唔到 data.csv")

if __name__ == "__main__":
    main()
