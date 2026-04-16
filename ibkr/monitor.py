import json
import os
import threading
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper


WATCHLIST_FILE = os.getenv("WATCHLIST_FILE", "watchlist_short.json")


@dataclass
class PositionRow:
    account: str
    symbol: str
    secType: str
    exchange: str
    currency: str
    position: float
    marketPrice: float
    marketValue: float
    averageCost: float
    unrealizedPNL: float
    realizedPNL: float
    conId: int = 0


def load_watchlist(path: str) -> list[str]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到监控池文件: {p}")

    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError('watchlist_short.json 必须是 JSON 数组，例如 ["TSLL", "TQQQ"]')

    result = []
    for item in data:
        if not isinstance(item, str):
            continue
        s = item.strip().upper()
        if s:
            result.append(s)

    if not result:
        raise ValueError("监控池为空，请至少配置一个股票代码")

    seen = set()
    uniq = []
    for s in result:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    return uniq


class ReadOnlyIBApp(EWrapper, EClient):
    def __init__(self, watchlist: list[str]):
        EClient.__init__(self, self)

        self.watchlist = set(watchlist)
        self.watchlist_order = watchlist[:]

        self.accounts: list[str] = []
        self.account: Optional[str] = None

        self.positions: dict[str, PositionRow] = {}

        self.daily_pnl: Optional[float] = None
        self.total_unrealized_pnl: Optional[float] = None
        self.total_realized_pnl: Optional[float] = None

        self._portfolio_done = False
        self._pnl_received = False
        self._done = False
        self._pnl_req_id = 9001

        # reqPnLSingle 相关
        self._pnl_single_received: set[str] = set()
        self._pnl_single_reqids: dict[int, str] = {}

    def nextValidId(self, orderId: int):
        print(f"[INFO] 已连接 TWS, nextValidId={orderId}")

    def managedAccounts(self, accountsList: str):
        self.accounts = [a.strip() for a in accountsList.split(",") if a.strip()]
        if not self.accounts:
            print("[ERROR] TWS 没有返回账户")
            self._done = True
            return

        self.account = self.accounts[0]
        print(f"[INFO] 使用账户: {self.account}")

        self.reqAccountUpdates(True, self.account)
        self.reqPnL(self._pnl_req_id, self.account, "")

    def updatePortfolio(
        self,
        contract: Contract,
        position: float,
        marketPrice: float,
        marketValue: float,
        averageCost: float,
        unrealizedPNL: float,
        realizedPNL: float,
        accountName: str,
    ):
        symbol = (contract.symbol or "").upper().strip()
        if not symbol:
            return

        if symbol not in self.watchlist:
            return

        if abs(float(position)) < 1e-12:
            self.positions.pop(symbol, None)
            return

        self.positions[symbol] = PositionRow(
            account=accountName,
            symbol=symbol,
            secType=contract.secType,
            exchange=contract.exchange,
            currency=contract.currency,
            position=float(position),
            marketPrice=float(marketPrice),
            marketValue=float(marketValue),
            averageCost=float(averageCost),
            unrealizedPNL=float(unrealizedPNL),
            realizedPNL=float(realizedPNL),
            conId=contract.conId,
        )

    def pnl(self, reqId: int, dailyPnL: float, unrealizedPnL: float, realizedPnL: float):
        if reqId != self._pnl_req_id:
            return
        self.daily_pnl = float(dailyPnL)
        self.total_unrealized_pnl = float(unrealizedPnL)
        self.total_realized_pnl = float(realizedPnL)
        self._pnl_received = True

    def accountDownloadEnd(self, accountName: str):
        print(f"[INFO] 账户持仓下载完成: {accountName}")

        self._pnl_single_received = set()
        self._pnl_single_reqids = {}

        for i, (symbol, row) in enumerate(self.positions.items()):
            req_id = 8000 + i
            self._pnl_single_reqids[req_id] = symbol
            self.reqPnLSingle(req_id, self.account, "", row.conId)
            print(f"[INFO] 订阅实时盈亏: {symbol} conId={row.conId} reqId={req_id}")

        expected = set(self.positions.keys())

        def _wait_pnl():
            deadline = time.time() + 5
            while time.time() < deadline:
                if self._pnl_single_received >= expected:
                    break
                time.sleep(0.2)
            self._portfolio_done = True

        threading.Thread(target=_wait_pnl, daemon=True).start()

    def pnlSingle(self, reqId: int, pos: int, dailyPnL: float,
                  unrealizedPnL: float, realizedPnL: float, value: float):
        symbol = self._pnl_single_reqids.get(reqId)
        if not symbol:
            return

        row = self.positions.get(symbol)
        if row:
            row.unrealizedPNL = float(unrealizedPnL)
            print(f"[INFO] 实时盈亏更新: {symbol} unrealizedPNL={unrealizedPnL}")

        self._pnl_single_received.add(symbol)

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        print(f"[ERROR] reqId={reqId}, code={errorCode}, msg={errorString}")


def build_brief(app: ReadOnlyIBApp) -> tuple[str, str]:
    title = "持仓简报"
    lines = []
    total = 0.0
    found_any = False

    for symbol in app.watchlist_order:
        row = app.positions.get(symbol)
        if not row:
            continue

        pnl = float(row.unrealizedPNL or 0.0)
        total += pnl
        found_any = True
        emoji = "📈" if pnl >= 0 else "📉"
        lines.append(f"{emoji} **{symbol}** 未实现盈亏：${pnl:,.2f}")

    if not found_any:
        lines.append("当前短线池无持仓")

    lines.append(f"\n**合计：${total:,.2f}**")

    content = "\n\n".join(lines)
    return title, content


def send_pushplus(title: str, content: str):
    token = os.getenv("PUSHPLUS_TOKEN", "").strip()
    topic = os.getenv("PUSHPLUS_TOPIC", "").strip()

    if not token:
        print("[WARN] 未设置 PUSHPLUS_TOKEN，跳过推送")
        return

    url = "https://www.pushplus.plus/send"
    payload = {
        "token": token,
        "title": title,
        "content": content,
        "template": "markdown",
    }

    if topic:
        payload["topic"] = topic

    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print("[INFO] PushPlus 返回:", body)
    except Exception as e:
        print(f"[ERROR] PushPlus 推送失败: {e}")


def print_console_summary(app: ReadOnlyIBApp, title: str, content: str):
    print("\n===== 控制台预览 =====")
    print(title)
    print(content)

    if app.positions:
        print("\n当前纳入监控的持仓:")
        for symbol in app.watchlist_order:
            row = app.positions.get(symbol)
            if not row:
                continue
            print(
                f"{symbol} | 数量={row.position} | 市价={row.marketPrice} | "
                f"未实现盈亏={row.unrealizedPNL}"
            )
    else:
        print("\n当前监控池没有持仓")


def run_readonly_report(
    host: str = "127.0.0.1",
    port: int = 7496,
    client_id: int = 101,
    timeout_seconds: int = 20,
):
    watchlist = load_watchlist(WATCHLIST_FILE)
    print("[INFO] 短线监控池:", ", ".join(watchlist))

    app = ReadOnlyIBApp(watchlist=watchlist)
    app.connect(host, port, client_id)

    api_thread = threading.Thread(target=app.run, daemon=True)
    api_thread.start()

    end_time = time.time() + timeout_seconds

    while time.time() < end_time:
        if app._portfolio_done and app._pnl_received:
            break
        time.sleep(0.5)

    if app.account:
        try:
            app.reqAccountUpdates(False, app.account)
        except Exception:
            pass

    try:
        app.cancelPnL(app._pnl_req_id)
    except Exception:
        pass

    # 取消所有 pnlSingle 订阅
    for req_id in app._pnl_single_reqids:
        try:
            app.cancelPnLSingle(req_id)
        except Exception:
            pass

    app.disconnect()

    title, content = build_brief(app)
    print_console_summary(app, title, content)
    send_pushplus(title, content)


if __name__ == "__main__":
    run_readonly_report(
        host=os.getenv("IBKR_HOST", "127.0.0.1"),
        port=int(os.getenv("IBKR_PORT", "7496")),
        client_id=int(os.getenv("IBKR_CLIENT_ID", "101")),
        timeout_seconds=int(os.getenv("IBKR_TIMEOUT", "20")),
    )