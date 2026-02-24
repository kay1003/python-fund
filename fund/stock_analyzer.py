import akshare as ak

from fund.utils import (
    get_yesterday_str,
    prepare_hist_df,
    resolve_analysis_year,
    summarize_intervals,
)



def stock_analyze_investment(
    symbol: str = "09618",
    start_date: str = "20250101",
    end_date: str = "",
    analysis_year: int | None = None,
):
    if not end_date:
        end_date = get_yesterday_str()

    df = ak.stock_hk_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust="qfq")
    df = prepare_hist_df(df)

    # 计算每日涨跌幅
    # df["涨跌幅"] = df["收盘"].pct_change() * 100

    # 筛选出下跌交易日
    df_down = df[df["涨跌幅"] < 0]

    analysis_year = resolve_analysis_year(df, "日期", analysis_year)
    year_mask = df["日期"].dt.year == analysis_year
    all_days = int(year_mask.sum())
    down_days = int((df_down["日期"].dt.year == analysis_year).sum())
    down_rate = round(down_days / all_days * 100, 2) if all_days else 0.0

    # 统计并输出
    print(
        f"Stock[{symbol}]-{analysis_year}年全部交易日数量：{all_days}天，"
        f"下跌交易日数量：{down_days}天。下跌率：{down_rate}%"
    )
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

    summaries = summarize_intervals(df_down, intervals, strategy="fixed", fixed_amounts=amounts)

    for summary in summaries:
        print(f"\n--- 跌幅区间：{summary.upper:.1f}% 到 {summary.lower:.1f}% ---")
        print(
            f"共 {summary.days} 天，单次投入：{summary.per_day_amount:.0f} 元，"
            f"总投入：{summary.total_invest:.0f} 元"
        )
        if not summary.subset.empty:
            print(summary.subset[["日期", "涨跌幅"]].to_string(index=False))

    # 总投入汇总
    print(f"\n==== Stock[{symbol}]-总投入情况 ====")
    print(f"总投入：{sum(s.total_invest for s in summaries):.0f} 元")
    for summary in summaries:
        print(f"区间 {summary.upper:.1f}% 到 {summary.lower:.1f}%：投入 {summary.total_invest:.0f} 元")
    print(f"\n##########Stock[{symbol}] analyze end ################################################\n\n\n")
