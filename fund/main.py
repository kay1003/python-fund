import argparse

from fund.us_analyzer import us_analyze_etf


def main() -> None:
    parser = argparse.ArgumentParser(description="US ETF 分析")
    parser.add_argument("--symbol", default="107.VOO", help="美股/ETF 代码，例如 107.VOO")
    parser.add_argument("--years", type=int, default=5, help="统计最近 N 年")
    args = parser.parse_args()

    daily, month_half, halfyear = us_analyze_etf(args.symbol, args.years)

    print(f"\n📌 每日涨跌幅（最近 {args.years} 年）示例 ： ")
    print(daily.tail(10).to_string(index=False))

    print(f"\n📌 每月上下半月下跌概率（最近 {args.years} 年）：")
    print(month_half.to_string(index=False))

    print(f"\n📌 每年上半年/下半年下跌概率（最近 {args.years} 年）：")
    print(halfyear.to_string(index=False))


if __name__ == "__main__":
    main()
