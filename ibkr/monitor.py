import json
import os
import http.client
import datetime as _dt
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Callable
from typing import Optional
import xml.etree.ElementTree as ET

from ibapi.client import EClient
from ibapi.contract import Contract
from ibapi.wrapper import EWrapper


MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


for env_file in (PROJECT_ROOT / ".env", MODULE_DIR / ".env"):
    _load_env_file(env_file)


WATCHLIST_FILE = os.getenv("WATCHLIST_FILE", "watchlist_short.json")
REALIZED_PNL_START_DATE = os.getenv("IBKR_REALIZED_PNL_START_DATE", "20260410")
REALIZED_PNL_END_DATE = os.getenv("IBKR_REALIZED_PNL_END_DATE", "")
FLEX_BASE_URL = "https://ndcdyn.interactivebrokers.com/AccountManagement/FlexWebService"

# 上次推送内容缓存文件（用于对比是否变化）
LAST_PUSH_FILE = MODULE_DIR / ".last_push.json"


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


@dataclass(frozen=True)
class RealizedPnlSummary:
    status: str
    start_date: str
    values_by_currency: dict[str, Decimal]
    error: str = ""

    @property
    def cache_key(self) -> dict:
        return {
            "status": self.status,
            "startDate": self.start_date,
            "values": {
                currency: str(amount.quantize(Decimal("0.01")))
                for currency, amount in sorted(self.values_by_currency.items())
            },
        }


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


def _format_date_zh(date_value: str) -> str:
    if len(date_value) == 8 and date_value.isdigit():
        return f"{date_value[:4]}年{int(date_value[4:6])}月{int(date_value[6:])}日"
    return date_value


def _parse_money(value: str | None) -> Decimal | None:
    if value is None:
        return None
    cleaned = value.strip().replace(",", "")
    if not cleaned:
        return None
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _first_attr(node: ET.Element, names: tuple[str, ...]) -> str | None:
    lower_attrs = {key.lower(): value for key, value in node.attrib.items()}
    for name in names:
        value = lower_attrs.get(name.lower())
        if value not in (None, ""):
            return value
    return None


def _parse_flex_date(value: str | None) -> str | None:
    if not value:
        return None
    digits = "".join(ch for ch in value if ch.isdigit())
    if len(digits) >= 8:
        return digits[:8]
    return None


def _default_realized_pnl_end_date() -> str:
    return (_dt.date.today() - _dt.timedelta(days=1)).strftime("%Y%m%d")


def parse_realized_pnl_from_flex_xml(xml_text: str, start_date: str) -> RealizedPnlSummary:
    root = ET.fromstring(xml_text)
    error_node = root.find(".//ErrorMessage")
    if error_node is not None and error_node.text:
        raise RuntimeError(error_node.text.strip())

    summary_result = _parse_realized_pnl_summary_rows(root, start_date)
    if summary_result is not None:
        return summary_result

    totals: dict[str, Decimal] = {}
    trade_count = 0
    seen_trade = False
    for trade in root.iter():
        if trade.tag.split("}")[-1].lower() != "trade":
            continue
        seen_trade = True

        trade_date = _parse_flex_date(
            _first_attr(trade, ("dateTime", "tradeDate", "reportDate", "settleDate"))
        )
        if trade_date and trade_date < start_date:
            continue

        realized_pnl = _parse_money(
            _first_attr(
                trade,
                (
                    "realizedPNL",
                    "realizedPnl",
                    "realizedPL",
                    "realizedP/L",
                    "fifoPnlRealized",
                ),
            )
        )
        if realized_pnl is None:
            continue

        currency = (_first_attr(trade, ("currency", "ibCommissionCurrency")) or "UNKNOWN").upper()
        fx_rate = _parse_money(_first_attr(trade, ("fxRateToBase", "fxRateToBaseCurrency")))
        base_currency = (
            _first_attr(trade, ("baseCurrency", "reportingCurrency"))
            or root.attrib.get("currency")
            or ""
        ).upper()
        if fx_rate is not None and base_currency:
            currency = base_currency
            realized_pnl *= fx_rate

        totals[currency] = totals.get(currency, Decimal("0")) + realized_pnl
        trade_count += 1

    if seen_trade and trade_count == 0:
        raise RuntimeError("Flex Trades section did not contain Realized PNL fields")
    if trade_count == 0:
        return RealizedPnlSummary(status="ok", start_date=start_date, values_by_currency={})
    return RealizedPnlSummary(status="ok", start_date=start_date, values_by_currency=totals)


def _parse_realized_pnl_summary_rows(
    root: ET.Element,
    start_date: str,
) -> RealizedPnlSummary | None:
    totals: dict[str, Decimal] = {}
    found_rows = 0
    for node in root.iter():
        tag_name = node.tag.split("}")[-1].lower()
        if tag_name == "trade":
            continue

        realized_pnl = _parse_money(
            _first_attr(
                node,
                (
                    "totalRealizedPNL",
                    "totalRealizedPnl",
                    "totalRealizedPL",
                    "totalRealizedP/L",
                    "realizedTotal",
                    "realizedPNL",
                    "realizedPnl",
                ),
            )
        )
        if realized_pnl is None:
            continue

        row_label = (
            _first_attr(node, ("symbol", "assetClass", "description"))
            or node.attrib.get("levelOfDetail")
            or ""
        ).strip().lower()
        if "total" in row_label or "all asset" in row_label:
            continue

        currency = (
            _first_attr(node, ("currency", "baseCurrency", "reportingCurrency"))
            or root.attrib.get("currency")
            or "USD"
        ).upper()
        totals[currency] = totals.get(currency, Decimal("0")) + realized_pnl
        found_rows += 1

    if found_rows == 0:
        return None
    return RealizedPnlSummary(status="ok", start_date=start_date, values_by_currency=totals)


def _flex_request(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "python-fund-ibkr-monitor/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        try:
            body = resp.read()
        except http.client.IncompleteRead as exc:
            body = exc.partial
            text = body.decode("utf-8", errors="replace")
            if not _looks_like_complete_flex_xml(text):
                raise
            return text
        return body.decode("utf-8", errors="replace")


def _flex_url(path: str, params: dict[str, str]) -> str:
    return f"{FLEX_BASE_URL}/{path}?{urllib.parse.urlencode(params)}"


def _looks_like_complete_flex_xml(xml_text: str) -> bool:
    stripped = xml_text.rstrip()
    return stripped.endswith("</FlexQueryResponse>") or stripped.endswith("</FlexStatementResponse>")


def _request_with_retries(
    request_call: Callable[[], str],
    sleep_fn: Callable[[float], None],
    attempts: int = 3,
) -> str:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return request_call()
        except (urllib.error.URLError, http.client.HTTPException, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt == attempts - 1:
                break
            sleep_fn(2)
    if last_error is not None:
        raise last_error
    raise RuntimeError("Flex request failed")


def _extract_flex_reference(response_xml: str) -> str:
    root = ET.fromstring(response_xml)
    status = root.findtext(".//Status")
    if status and status.lower() != "success":
        code = root.findtext(".//ErrorCode") or "unknown"
        message = root.findtext(".//ErrorMessage") or "Flex request failed"
        raise RuntimeError(f"Flex SendRequest failed: {code} {message}")

    reference_code = root.findtext(".//ReferenceCode")
    if not reference_code:
        raise RuntimeError("Flex SendRequest did not return ReferenceCode")
    return reference_code.strip()


def fetch_realized_pnl_summary(
    start_date: str = REALIZED_PNL_START_DATE,
    end_date: str = REALIZED_PNL_END_DATE,
    request_fn: Callable[[str], str] = _flex_request,
    sleep_fn: Callable[[float], None] = time.sleep,
    max_attempts: int = 5,
) -> RealizedPnlSummary:
    token = os.getenv("IBKR_FLEX_TOKEN", "").strip()
    query_id = os.getenv("IBKR_FLEX_QUERY_ID", "").strip()
    if not token or not query_id:
        print("[WARN] 未设置 IBKR_FLEX_TOKEN 或 IBKR_FLEX_QUERY_ID，跳过已实现盈亏统计")
        return RealizedPnlSummary(status="unconfigured", start_date=start_date, values_by_currency={})

    try:
        if not end_date:
            end_date = _default_realized_pnl_end_date()
        send_xml = _request_with_retries(
            lambda: request_fn(
                _flex_url(
                    "SendRequest",
                    {"t": token, "q": query_id, "fd": start_date, "td": end_date, "v": "3"},
                )
            ),
            sleep_fn,
        )
        reference_code = _extract_flex_reference(send_xml)
        statement_url = _flex_url("GetStatement", {"t": token, "q": reference_code, "v": "3"})
        sleep_fn(20)

        last_error = ""
        for attempt in range(max_attempts):
            statement_xml = _request_with_retries(lambda: request_fn(statement_url), sleep_fn)
            try:
                return parse_realized_pnl_from_flex_xml(statement_xml, start_date)
            except RuntimeError as exc:
                last_error = str(exc)
                if attempt == max_attempts - 1:
                    break
                sleep_fn(2)
        raise RuntimeError(last_error or "Flex statement was not available")
    except Exception as exc:
        print(f"[ERROR] 获取 Flex 已实现盈亏失败: {exc}")
        return RealizedPnlSummary(
            status="error",
            start_date=start_date,
            values_by_currency={},
            error=str(exc),
        )


def format_realized_pnl_line(summary: RealizedPnlSummary) -> str:
    date_label = _format_date_zh(summary.start_date)
    if summary.status == "unconfigured":
        return f"**自 {date_label} 以来已实现全部盈亏：未配置 Flex**"
    if summary.status == "error":
        return f"**自 {date_label} 以来已实现全部盈亏：获取失败**"
    if not summary.values_by_currency:
        return f"**自 {date_label} 以来已实现全部盈亏：$0.00**"

    parts = []
    for currency, amount in sorted(summary.values_by_currency.items()):
        symbol = "$" if currency in ("USD", "UNKNOWN") else f"{currency} "
        parts.append(f"{symbol}{amount:,.2f}")
    return f"**自 {date_label} 以来已实现全部盈亏：{', '.join(parts)}**"


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

        # 过滤：排除美债（BOND类型）和成本基础<=8000的持仓
        cost_basis = float(averageCost) * float(position)
        if contract.secType == "BOND":
            return
        if cost_basis <= 8000:
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


def build_brief(app: ReadOnlyIBApp, realized_pnl: RealizedPnlSummary | None = None) -> tuple[str, str]:
    title = "持仓简报"
    lines = []
    total_market_value = 0.0
    total_unrealized_pnl = 0.0
    total_cost_basis = 0.0
    found_any = False

    # 按持仓市值排序，大市值在前
    sorted_positions = sorted(
        app.positions.items(),
        key=lambda x: float(x[1].marketValue or 0.0),
        reverse=True
    )

    for symbol, row in sorted_positions:
        position = float(row.position or 0.0)
        pnl = float(row.unrealizedPNL or 0.0)
        market_value = float(row.marketValue or 0.0)
        avg_cost = float(row.averageCost or 0.0)
        market_price = float(row.marketPrice or 0.0)

        # 成本基础 = 均价 × 持仓数量
        cost_basis = avg_cost * position

        # 盈亏百分比
        pnl_pct = (pnl / cost_basis * 100) if cost_basis > 0 else 0

        total_unrealized_pnl += pnl
        total_market_value += market_value
        total_cost_basis += cost_basis
        found_any = True
        emoji = "📈" if pnl >= 0 else "📉"

        lines.append(
            f"{emoji} **{symbol}** 未实现盈亏：${pnl:,.2f} ({pnl_pct:+.2f}%)\n"
            f"- 均价：${avg_cost:,.2f}，现价：${market_price:,.2f}\n"
            f"- 成本基础：${cost_basis:,.2f}"
        )

    if not found_any:
        lines.append("当前无符合条件的持仓（成本基础>$8000，不含美债）")
    else:
        total_pnl_pct = (total_unrealized_pnl / total_cost_basis * 100) if total_cost_basis > 0 else 0
        lines.append(f"\n**💰 总成本基础：${total_cost_basis:,.2f}**")
        lines.append(f"**📊 总未实现盈亏：${total_unrealized_pnl:,.2f} ({total_pnl_pct:+.2f}%)**")

    if realized_pnl is not None:
        lines.append(format_realized_pnl_line(realized_pnl))

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
    """保存本次推送的内容摘要，包含时间戳"""
    try:
        data = {
            "content": summary,
            "last_push_time": time.time(),
        }
        LAST_PUSH_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass  # 保存失败不记录日志


def _build_content_summary(positions: dict, realized_pnl: RealizedPnlSummary | None = None) -> dict:
    """构建内容摘要，用于对比是否变化（使用IB原始数据）"""
    summary = {}
    for symbol, row in positions.items():
        position = float(row.position or 0.0)
        avg_cost = float(row.averageCost or 0.0)
        cost_basis = avg_cost * position
        summary[symbol] = {
            "position": round(position, 4),
            "averageCost": round(avg_cost, 2),
            "costBasis": round(cost_basis, 2),
            "unrealizedPNL": round(float(row.unrealizedPNL or 0), 2),
        }
    if realized_pnl is not None:
        summary["_realizedPnlSince"] = realized_pnl.cache_key
    return summary


def _has_content_changed(positions: dict, realized_pnl: RealizedPnlSummary | None = None) -> bool:
    """检查持仓内容是否发生变化，或超过60秒未推送"""
    current = _build_content_summary(positions, realized_pnl)
    last_data = _load_last_push()

    if not last_data:
        return True

    # 兼容旧格式（直接是内容摘要）
    if "content" in last_data:
        last_content = last_data.get("content", {})
        last_push_time = last_data.get("last_push_time", 0)
    else:
        last_content = last_data
        last_push_time = 0

    # 内容变化，触发推送
    if current != last_content:
        return True

    # 内容没变，但超过5分钟，强制推送一次
    if time.time() - last_push_time > 300:  # 300秒 = 5分钟
        return True

    return False


def send_pushplus(
    title: str,
    content: str,
    positions: dict = None,
    realized_pnl: RealizedPnlSummary | None = None,
):
    """发送 PushPlus 推送，支持内容变化检测"""
    token = os.getenv("PUSHPLUS_TOKEN", "").strip()
    topic = os.getenv("PUSHPLUS_TOPIC", "").strip()

    if not token:
        print("[WARN] 未设置 PUSHPLUS_TOKEN，跳过推送")
        return

    # 内容变化检测
    if positions is not None:
        if not _has_content_changed(positions, realized_pnl):
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
            try:
                result = json.loads(body)
                code = result.get("code")
                if code == 200:
                    # 推送成功，保存缓存
                    if positions is not None:
                        _save_last_push(_build_content_summary(positions, realized_pnl))
                elif code == 999:
                    # 服务端说内容相同，也保存缓存（更新时间戳），避免死循环
                    if positions is not None:
                        _save_last_push(_build_content_summary(positions, realized_pnl))
                else:
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

    # 连接失败或数据未就绪，直接退出不推送
    if not app._portfolio_done:
        try:
            app.disconnect()
        except Exception:
            pass
        return

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

    realized_pnl = fetch_realized_pnl_summary()
    title, content = build_brief(app, realized_pnl)
    print_console_summary(app, title, content)
    send_pushplus(title, content, positions=app.positions, realized_pnl=realized_pnl)


if __name__ == "__main__":
    run_readonly_report(
        host=os.getenv("IBKR_HOST", "127.0.0.1"),
        port=int(os.getenv("IBKR_PORT", "7496")),
        client_id=int(os.getenv("IBKR_CLIENT_ID", "101")),
        timeout_seconds=int(os.getenv("IBKR_TIMEOUT", "20")),
    )
