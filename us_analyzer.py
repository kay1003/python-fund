import akshare as ak
import pandas as pd
from datetime import datetime

def us_analyze_etf(symbol: str = "107.VOO", years: int = 5):
    df = ak.stock_us_hist(symbol=symbol)
    df['日期'] = pd.to_datetime(df['日期'])
    df = df.sort_values('日期').reset_index(drop=True)
    # 筛选近N年
    cutoff = datetime.now() - pd.DateOffset(years=years)
    df = df[df['日期'] >= cutoff].copy()

    # 计算涨跌幅
    # df['涨跌幅'] = df['收盘价'].pct_change()
    df.dropna(inplace=True)

    # 添加辅助列
    df['年份'] = df['日期'].dt.year
    df['月份'] = df['日期'].dt.month
    df['日'] = df['日期'].dt.day
    df['上下半月'] = df['日'].apply(lambda x: '上半月' if x <= 15 else '下半月')
    df['星期'] = df['日期'].dt.day_name(locale='zh_CN')
    df['上下半年'] = df['月份'].apply(lambda m: '上半年' if m <= 6 else '下半年')
    df['是否下跌'] = df['涨跌幅'] < 0

    # —— 每日数据
    daily = df[['日期', '星期', '涨跌幅']].copy()

    # —— 月度上下半月下跌统计
    total_month_half = df.groupby(['年份','月份','上下半月']).size().reset_index(name='交易日总数')
    down_month_half = df[df['是否下跌']].groupby(['年份','月份','上下半月']).size().reset_index(name='下跌日数')
    month_half = pd.merge(total_month_half, down_month_half, how='left', on=['年份','月份','上下半月']).fillna(0)
    month_half['下跌概率'] = month_half['下跌日数'] / month_half['交易日总数']

    # —— 年度上下半年下跌统计
    total_halfyear = df.groupby(['年份','上下半年']).size().reset_index(name='交易日总数')
    down_halfyear = df[df['是否下跌']].groupby(['年份','上下半年']).size().reset_index(name='下跌日数')
    halfyear = pd.merge(total_halfyear, down_halfyear, how='left', on=['年份','上下半年']).fillna(0)
    halfyear['下跌概率'] = halfyear['下跌日数'] / halfyear['交易日总数']

    return daily, month_half, halfyear