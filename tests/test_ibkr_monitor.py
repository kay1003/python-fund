import sys
import types
import unittest
from decimal import Decimal
from unittest.mock import patch


def _install_fake_ibapi() -> None:
    if "ibapi.client" in sys.modules:
        return

    ibapi = types.ModuleType("ibapi")
    client = types.ModuleType("ibapi.client")
    contract = types.ModuleType("ibapi.contract")
    wrapper = types.ModuleType("ibapi.wrapper")

    class EClient:
        def __init__(self, wrapper):
            self.wrapper = wrapper

    class EWrapper:
        pass

    class Contract:
        pass

    client.EClient = EClient
    contract.Contract = Contract
    wrapper.EWrapper = EWrapper
    sys.modules["ibapi"] = ibapi
    sys.modules["ibapi.client"] = client
    sys.modules["ibapi.contract"] = contract
    sys.modules["ibapi.wrapper"] = wrapper


_install_fake_ibapi()

from ibkr.monitor import (  # noqa: E402
    PositionRow,
    RealizedPnlSummary,
    _build_content_summary,
    fetch_realized_pnl_summary,
    format_realized_pnl_line,
    parse_realized_pnl_from_flex_xml,
)


class FlexRealizedPnlTests(unittest.TestCase):
    def test_parse_single_currency_from_start_date(self):
        xml = """
        <FlexQueryResponse>
          <FlexStatements>
            <FlexStatement>
              <Trades>
                <Trade dateTime="2026-04-09;09:30:00" currency="USD" realizedPNL="99.00" />
                <Trade dateTime="2026-04-10;09:30:00" currency="USD" realizedPNL="50.25" />
                <Trade tradeDate="20260501" currency="USD" realizedPnl="-10.00" />
              </Trades>
            </FlexStatement>
          </FlexStatements>
        </FlexQueryResponse>
        """
        result = parse_realized_pnl_from_flex_xml(xml, "20260410")

        self.assertEqual(result.status, "ok")
        self.assertEqual(result.values_by_currency, {"USD": Decimal("40.25")})

    def test_parse_empty_trades_as_zero(self):
        xml = """
        <FlexQueryResponse>
          <FlexStatements>
            <FlexStatement><Trades /></FlexStatement>
          </FlexStatements>
        </FlexQueryResponse>
        """
        result = parse_realized_pnl_from_flex_xml(xml, "20260410")

        self.assertEqual(result.values_by_currency, {})
        self.assertIn("$0.00", format_realized_pnl_line(result))

    def test_parse_multi_currency_without_adding_together(self):
        xml = """
        <FlexQueryResponse>
          <FlexStatements>
            <FlexStatement>
              <Trades>
                <Trade tradeDate="20260410" currency="USD" realizedPNL="10" />
                <Trade tradeDate="20260411" currency="HKD" realizedPNL="20" />
              </Trades>
            </FlexStatement>
          </FlexStatements>
        </FlexQueryResponse>
        """
        result = parse_realized_pnl_from_flex_xml(xml, "20260410")
        line = format_realized_pnl_line(result)

        self.assertEqual(result.values_by_currency, {"HKD": Decimal("20"), "USD": Decimal("10")})
        self.assertIn("$10.00", line)
        self.assertIn("HKD 20.00", line)

    def test_parse_realized_unrealized_summary_rows(self):
        xml = """
        <FlexQueryResponse currency="USD">
          <FlexStatements>
            <FlexStatement>
              <RealizedUnrealizedPerformanceSummaryInBase>
                <RealizedUnrealizedPerformanceSummary assetClass="STK" symbol="AAPL" totalRealizedPNL="15.50" />
                <RealizedUnrealizedPerformanceSummary assetClass="STK" symbol="MSFT" totalRealizedPNL="-3.25" />
                <RealizedUnrealizedPerformanceSummary assetClass="Total" symbol="Total" totalRealizedPNL="12.25" />
              </RealizedUnrealizedPerformanceSummaryInBase>
            </FlexStatement>
          </FlexStatements>
        </FlexQueryResponse>
        """
        result = parse_realized_pnl_from_flex_xml(xml, "20260410")

        self.assertEqual(result.values_by_currency, {"USD": Decimal("12.25")})

    def test_missing_realized_pnl_field_is_error(self):
        xml = """
        <FlexQueryResponse>
          <FlexStatements>
            <FlexStatement>
              <Trades>
                <Trade tradeDate="20260410" currency="USD" proceeds="10" />
              </Trades>
            </FlexStatement>
          </FlexStatements>
        </FlexQueryResponse>
        """

        with self.assertRaises(RuntimeError):
            parse_realized_pnl_from_flex_xml(xml, "20260410")

    def test_fetch_flex_statement_retries_until_available(self):
        responses = iter(
            [
                "<FlexStatementResponse><Status>Success</Status><ReferenceCode>abc</ReferenceCode></FlexStatementResponse>",
                "<FlexQueryResponse><ErrorMessage>Statement generation in progress</ErrorMessage></FlexQueryResponse>",
                """
                <FlexQueryResponse>
                  <FlexStatements>
                    <FlexStatement>
                      <Trades>
                        <Trade tradeDate="20260410" currency="USD" realizedPNL="12.50" />
                      </Trades>
                    </FlexStatement>
                  </FlexStatements>
                </FlexQueryResponse>
                """,
            ]
        )
        urls = []

        def fake_request(url):
            urls.append(url)
            return next(responses)

        with patch.dict(
            "os.environ",
            {"IBKR_FLEX_TOKEN": "token", "IBKR_FLEX_QUERY_ID": "query"},
            clear=False,
        ):
            result = fetch_realized_pnl_summary(
                start_date="20260410",
                request_fn=fake_request,
                sleep_fn=lambda _: None,
            )

        self.assertEqual(result.values_by_currency, {"USD": Decimal("12.50")})
        self.assertIn("SendRequest", urls[0])
        self.assertIn("GetStatement", urls[1])

    def test_realized_pnl_is_in_content_summary(self):
        positions = {
            "TSLL": PositionRow(
                account="U1",
                symbol="TSLL",
                secType="STK",
                exchange="SMART",
                currency="USD",
                position=100,
                marketPrice=10,
                marketValue=1000,
                averageCost=8,
                unrealizedPNL=200,
                realizedPNL=0,
            )
        }
        realized = RealizedPnlSummary(
            status="ok",
            start_date="20260410",
            values_by_currency={"USD": Decimal("12.34")},
        )

        summary = _build_content_summary(positions, realized)

        self.assertEqual(summary["_realizedPnlSince"]["values"], {"USD": "12.34"})


if __name__ == "__main__":
    unittest.main()
