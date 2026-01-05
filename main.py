import datetime

from fund.etf_analyzer import etf_analyze_investment
from stock_analyzer import stock_analyze_investment
from us_analyzer import us_analyze_etf


def print_hi(name):
    # 在下面的代码行中使用断点来调试脚本。
    print(f'Hi, {name}')  # 按 Ctrl+F8 切换断点。

def demo(text :str, temp1 :int, temp2):
    result = temp1+ temp2;
    print(f'Hello, {text}, result is {result}')


# 按装订区域中的绿色按钮以运行脚本。
if __name__ == '__main__':
    # etf_analyze_investment("515450")
    # etf_analyze_investment(symbol="159545")

    # stock_analyze_investment(symbol="09618")
    years = 5
    daily, month_half, halfyear = us_analyze_etf("107.VOO", years)

    print(f"\n📌 每日涨跌幅（最近 {years} 年）示例：")
    print(daily.tail(10).to_string(index=False))

    print(f"\n📌 每月上下半月下跌概率（最近 {years} 年）：")
    print(month_half.to_string(index=False))

    print(f"\n📌 每年上半年/下半年下跌概率（最近 {years} 年）：")
    print(halfyear.to_string(index=False))

