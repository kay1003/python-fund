import akshare as ak

def main() -> None:
    stock_sse_deal_daily_df = ak.stock_sse_deal_daily(date="20250625")
    print(stock_sse_deal_daily_df)


if __name__ == "__main__":
    main()
