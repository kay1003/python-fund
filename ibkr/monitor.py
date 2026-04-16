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

# 上次推送内容缓存文件（用于对比是否变化）
LAST_PUSH_FILE = Path(__file__).parent / ".last_push.json"


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
        pass  # 正常连接不记录日志

    def managedAccounts(self, accountsList: str):
        self.accounts = [a.strip() for a in accountsList.split(",") if a.strip()]
        if not self.accounts:
            print("[ERROR] TWS 没有返回账户")
            self._done = True
            return

        self.account = self.accounts[0]
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
        self._pnl_single_received = set()
        self._pnl_single_reqids = {}

        for i, (symbol, row) in enumerate(self.positions.items()):
            req_id = 8000 + i
            self._pnl_single_reqids[req_id] = symbol
            self.reqPnLSingle(req_id, self.account, "", row.conId)

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

        self._pnl_single_received.add(symbol)

    def error(self, reqId, errorCode, errorString, advancedOrderRejectJson=""):
        # IB API 会把正常连接消息也走 error 回调，过滤掉这些
        # 2104, 2106, 2158 是数据场连接正常的通知，不是错误
        if errorCode in (2104, 2106, 2158):
            return
        print(f"[ERROR] reqId={reqId}, code={errorCode}, msg={errorString}")


def build_brief(app: ReadOnlyIBApp) -> tuple[str, str]:
    title = "持仓简报"
    lines = []
    total_pnl = 0.0
    total_cost = 0.0
    found_any = False

    for symbol in app.watchlist_order:
        row = app.positions.get(symbol)
        if not row:
            continue

        pnl = float(row.unrealizedPNL or 0.0)
        avg_cost = float(row.averageCost or 0.0)
        position = float(row.position or 0.0)
        cost_basis = avg_cost * position  # 成本基础 = 均价 × 持仓数量
        pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0  # 收益率

        total_pnl += pnl
        total_cost += cost_basis
        found_any = True
        emoji = "📈" if pnl >= 0 else "📉"

        lines.append(
            f"{emoji} **{symbol}** 未实现盈亏：${pnl:,.2f} ({pnl_pct:+.2f}%)\n"
            f"- 均价：${avg_cost:,.2f}\n"
            f"- 成本基础：${cost_basis:,.2f}"
        )

    if not found_any:
        lines.append("当前短线池无持仓")
    else:
        total_pnl_pct = (total_pnl / total_cost * 100) if total_cost > 0 else 0
        lines.append(f"\n**💰 总成本基础：${total_cost:,.2f}**")
        lines.append(f"**📊 总未实现盈亏：${total_pnl:,.2f} ({total_pnl_pct:+.2f}%)**")

    content = "\n\n".join(lines)
    return title, content


def _load_last_push() -> dict:
    """加载上次推送的内容摘要"""
    if LAST_PUSH_FILE.exists():
        try:
            return json.loads(LAST_PUSH_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def _save_last_push(summary: dict):
    """保存本次推送的内容摘要"""
    try:
        LAST_PUSH_FILE.write_text(json.dumps(summary, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass  # 保存失败不记录日志


def _build_content_summary(positions: dict, watchlist_order: list) -> dict:
    """构建内容摘要，用于对比是否变化"""
    summary = {}
    for symbol in watchlist_order:
        row = positions.get(symbol)
        if row:
            # 只取关键字段，避免浮点精度问题
            summary[symbol] = {
                "position": round(float(row.position), 4),
                "averageCost": round(float(row.averageCost or 0), 2),
                "unrealizedPNL": round(float(row.unrealizedPNL or 0), 2),
            }
    return summary


def _has_content_changed(positions: dict, watchlist_order: list) -> bool:
    """检查持仓内容是否发生变化"""
    current = _build_content_summary(positions, watchlist_order)
    last = _load_last_push()

    if not last:
        return True

    if current != last:
        return True

    return False


def send_pushplus(title: str, content: str, positions: dict = None, watchlist_order: list = None):
    """发送 PushPlus 推送，支持内容变化检测"""
    token = os.getenv("PUSHPLUS_TOKEN", "").strip()
    topic = os.getenv("PUSHPLUS_TOPIC", "").strip()

    if not token:
        print("[WARN] 未设置 PUSHPLUS_TOKEN，跳过推送")
        return

    # 内容变化检测
    if positions is not None and watchlist_order is not None:
        if not _has_content_changed(positions, watchlist_order):
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
            # 推送成功后保存内容摘要
            if positions is not None and watchlist_order is not None:
                _save_last_push(_build_content_summary(positions, watchlist_order))
            # 检查返回结果，非成功状态记录错误
            try:
                result = json.loads(body)
                if result.get("code") != 200:
                    print(f"[ERROR] PushPlus 推送异常: {body}")
            except Exception:
                pass
    except Exception as e:
        print(f"[ERROR] PushPlus 推送失败: {e}")


def print_console_summary(app: ReadOnlyIBApp, title: str, content: str):
    # 控制台不输出，所有信息通过 PushPlus 推送
    pass


def run_readonly_report(
    host: str = "127.0.0.1",
    port: int = 7496,
    client_id: int = 101,
    timeout_seconds: int = 20,
):
    watchlist = load_watchlist(WATCHLIST_FILE)

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
    send_pushplus(title, content, positions=app.positions, watchlist_order=app.watchlist_order)


if __name__ == "__main__":
    run_readonly_report(
        host=os.getenv("IBKR_HOST", "127.0.0.1"),
        port=int(os.getenv("IBKR_PORT", "7496")),
        client_id=int(os.getenv("IBKR_CLIENT_ID", "101")),
        timeout_seconds=int(os.getenv("IBKR_TIMEOUT", "20")),
    )