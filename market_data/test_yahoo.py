"""Tests for the consent-gated Yahoo fallback fetcher.

The transport is a fake in every test: no test ever touches the network.
"""

import json
import unittest
from unittest.mock import patch

from market_data.yahoo import (
    YahooFetchError,
    fetch_yahoo_prices,
    yahoo_symbol,
)


class FakeTransport:
    """Records every request; serves canned chart payloads."""

    def __init__(self, responses=None):
        self.requests = []
        self.responses = responses or {}

    def __call__(self, url, headers):
        self.requests.append(url)
        if url in self.responses:
            return self.responses[url]
        return 404, json.dumps({"chart": {"result": None, "error": "x"}})


def chart_payload(price):
    return 200, json.dumps(
        {"chart": {"result": [{"meta": {"regularMarketPrice": price}}]}}
    )


class ConsentTests(unittest.TestCase):
    def test_no_consent_means_no_network_traffic(self):
        transport = FakeTransport()

        with self.assertRaises(YahooFetchError):
            fetch_yahoo_prices(["RELIANCE"], lambda: False, transport)

        self.assertEqual(transport.requests, [])

    def test_consent_must_be_callable(self):
        transport = FakeTransport()

        with self.assertRaises(YahooFetchError):
            fetch_yahoo_prices(["RELIANCE"], "yes", transport)

        self.assertEqual(transport.requests, [])


class SymbolMappingTests(unittest.TestCase):
    def test_nse_ticker_gets_the_ns_suffix(self):
        self.assertEqual(yahoo_symbol("RELIANCE"), "RELIANCE.NS")

    def test_amc_display_name_maps_through_the_nse_ticker(self):
        self.assertEqual(yahoo_symbol("GROWWAMC - GROWWGOLD"), "GROWWGOLD.NS")

    def test_unmappable_symbol_is_none(self):
        self.assertIsNone(yahoo_symbol("VEDANTA"))
        self.assertIsNone(yahoo_symbol(""))


class FetchTests(unittest.TestCase):
    def test_fetches_warmup_free_per_symbol_quotes(self):
        transport = FakeTransport({
            "https://query1.finance.yahoo.com/v8/finance/chart/RELIANCE.NS":
                chart_payload(1177.1),
        })

        result = fetch_yahoo_prices(["RELIANCE"], lambda: True, transport)

        self.assertEqual(result["prices"], {"RELIANCE": 1177.1})
        self.assertEqual(result["failures"], {})
        self.assertEqual(len(transport.requests), 1)  # no warm-up needed

    def test_per_symbol_failure_does_not_block_others(self):
        transport = FakeTransport({
            "https://query1.finance.yahoo.com/v8/finance/chart/RELIANCE.NS":
                chart_payload(1177.1),
            # ITC falls through to the 404 default.
        })

        result = fetch_yahoo_prices(["RELIANCE", "ITC"], lambda: True, transport)

        self.assertEqual(result["prices"], {"RELIANCE": 1177.1})
        self.assertIn("HTTP 404", result["failures"]["ITC"])

    def test_unmappable_symbol_reported(self):
        transport = FakeTransport()

        result = fetch_yahoo_prices(["VEDANTA"], lambda: True, transport)

        self.assertEqual(
            result["failures"]["VEDANTA"], "cannot map to a Yahoo symbol",
        )
        self.assertEqual(transport.requests, [])

    def test_transport_exception_reported_per_symbol(self):
        def exploding_transport(url, headers):
            raise ConnectionError("reset by peer")

        result = fetch_yahoo_prices(["ITC"], lambda: True, exploding_transport)

        self.assertIn("request failed", result["failures"]["ITC"])

    def test_non_json_body_reported(self):
        transport = FakeTransport({
            "https://query1.finance.yahoo.com/v8/finance/chart/ITC.NS":
                (200, "<html>blocked</html>"),
        })

        result = fetch_yahoo_prices(["ITC"], lambda: True, transport)

        self.assertEqual(result["failures"]["ITC"], "Yahoo returned a non-JSON response")

    def test_priceless_payload_reported(self):
        transport = FakeTransport({
            "https://query1.finance.yahoo.com/v8/finance/chart/ITC.NS":
                (200, json.dumps({"chart": {"result": [{"meta": {}}]}})),
        })

        result = fetch_yahoo_prices(["ITC"], lambda: True, transport)

        self.assertEqual(result["failures"]["ITC"], "no price in the Yahoo response")

    def test_int_price_is_accepted(self):
        transport = FakeTransport({
            "https://query1.finance.yahoo.com/v8/finance/chart/ITC.NS":
                chart_payload(450),
        })

        result = fetch_yahoo_prices(["ITC"], lambda: True, transport)

        self.assertEqual(result["prices"], {"ITC": 450.0})


class DefaultTransportTests(unittest.TestCase):
    def test_default_transport_is_urllib_and_gated_by_consent(self):
        # Patch urllib so even the consented path stays offline in tests.
        with patch("market_data.yahoo.urllib.request.urlopen") as fake_open:
            fake_open.return_value.__enter__.return_value.status = 200
            fake_open.return_value.__enter__.return_value.read.return_value = (
                chart_payload(123.45)[1].encode()
            )

            result = fetch_yahoo_prices(["ITC"], lambda: True)

        self.assertEqual(result["prices"], {"ITC": 123.45})


if __name__ == "__main__":
    unittest.main()
