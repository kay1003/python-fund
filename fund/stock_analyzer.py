import datetime

import akshare as ak
import pandas as pd


pd.set_option('display.max_rows', None)  # 显示所有行
pd.set_option('display.max_columns', None)  # 显示所有列




def stock_analyze_investment(symbol: str = "09618", start_date: str = "20250101", end_date: str = ""):
    if not end_date:
        end_date = get_yesterday()

    df = ak.stock_hk_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
    # 格式处理
    df["日期"] = pd.to_datetime(df["日期"])
    df = df.sort_values("日期").reset_index(drop=True)

    # 计算每日涨跌幅
    # df["涨跌幅"] = df["收盘"].pct_change() * 100

    # 筛选出下跌交易日
    df['涨跌幅'] = df['涨跌幅'].astype(float)
    df_down = df[df["涨跌幅"] < 0]

    all = len(df[df['日期'].dt.year == 2025])
    down = len(df_down[df_down['日期'].dt.year == 2025])

    # 统计并输出
    print(f"ETF[{symbol}]-2025年全部交易日数量：{all}天，下跌交易日数量：{down}天。下跌率：{round(down / all * 100, 2)}%")
    # 定义跌幅区间：[(上限, 下限)]
    intervals = [
        (-0.0, -0.5),
        (-0.5, -1.0),
        (-1.0, -1.5),
        (-1.5, -2.0),
        (-2.0, -5.0),
        (-5.0, -10.0),
    ]

    # 区间对应的投资金额（单位：元）
    amounts = [500, 1000, 1500, 2000, 2500, 5000]

    # 用于汇总每个区间的总投资额
    total_invest_per_interval = []

    # 遍历每个跌幅区间
    for i, (upper, lower) in enumerate(intervals):
        mask = (df_down['涨跌幅'] <= upper) & (df_down['涨跌幅'] > lower)
        subset = df_down[mask]

        invest_per_day = amounts[i]
        total_invest = len(subset) * invest_per_day
        total_invest_per_interval.append(total_invest)

        print(f"\n--- 跌幅区间：{upper:.1f}% 到 {lower:.1f}% ---")
        print(f"共 {len(subset)} 天，单次投入：{invest_per_day} 元，总投入：{total_invest} 元")
        if not subset.empty:
            print(subset[['日期', '涨跌幅']].to_string(index=False))

    # 总投入汇总
    print(f"\n==== ETF[{symbol}]-总投入情况 ====")
    print(f"总投入：{sum(total_invest_per_interval)} 元")
    for i, (upper, lower) in enumerate(intervals):
        print(f"区间 {upper:.1f}% 到 {lower:.1f}%：投入 {total_invest_per_interval[i]} 元")
    print(f"\n##########ETF[{symbol}] analyze end ################################################\n\n\n")

def get_yesterday():
    today = datetime.date.today()
    oneday = datetime.timedelta(days=1)
    yesterday = today - oneday
    return yesterday.strftime('%Y%m%d')