import pandas as pd
import os

def calculate_metrics(df):
    # 1. 淨係保留有用嘅欄位，將 Excel 啲 Unnamed 垃圾吉格清走
    cols_to_keep = ['date', 'weekday', 'n1', 'n2', 'n3', 'n4', 'n5', 'n6', 'n7', 'bonus']
    df = df[[c for c in cols_to_keep if c in df.columns]].copy()
    
    # 2. 處理日期，排好先後次序 (由舊到新，方便計重複號碼)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date', ascending=True)
    
    prev_numbers = set()
    
    # 3. 逐行計數
    def process_row(row):
        nonlocal prev_numbers
        # 攞 n1 到 n7 嘅號碼
        nums = [int(row[f'n{i}']) for i in range(1, 8)]
        nums.sort()
        
        # 單雙
        odds = len([n for n in nums if n % 2 != 0])
        odd_even = f"{odds}O{7-odds}E"
        
        # 連續
        has_consec = "No"
        for i in range(len(nums)-1):
            if nums[i+1] - nums[i] == 1:
                has_consec = "Yes"
                break
                
        # 上期重複
        repeats = len(set(nums).intersection(prev_numbers)) if prev_numbers else 0
        prev_numbers = set(nums)
        
        # 分區
        zone = f"Z{(nums[0]-1)//7 + 1}"
        
        return pd.Series([odd_even, has_consec, repeats, zone])
        
    # 將計好嘅 4 個結果寫入表度
    df[['odd_even', 'consecutive', 'repeats', 'zone']] = df.apply(process_row, axis=1)
    
    # 4. 排返由新到舊 (最新一期擺最頂)
    df = df.sort_values('date', ascending=False)
    # 將日期變返靚靚格式 (例如 2024-03-20)
    df['date'] = df['date'].dt.strftime('%Y-%m-%d')
    
    return df

def main():
    if os.path.exists('data.csv'):
        df = pd.read_csv('data.csv')
        updated_df = calculate_metrics(df)
        updated_df.to_csv('data.csv', index=False)
        print("✅ 成功！已經為你份專屬 CSV 完成所有統計計算。")
    else:
        print("❌ 搵唔到 data.csv")

if __name__ == "__main__":
    main()
