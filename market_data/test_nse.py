"""Tests for the consent-gated NSE fetcher.

The transport is a fake in every test: no test ever touches the network.
The critical assertion is that NOTHING is fetched without consent.
"""

import json
import unittest
from unittest.mock import patch

from market_data.nse import (
    ConsentRequired,
    NseFetchError,
    fetch_nse_prices,
    is_mutual_fund_scheme,
    nse_symbol,
)


class FakeTransport:
    """Records every request; serves canned quote payloads."""

    def __init__(self, responses=None):
        self.requests = []
        self.responses = responses or {}

    def __call__(self, url, headers):
        self.requests.append(url)
        if url in self.responses:
            return self.responses[url]
        symbol = url.split("symbol=")[-1]
        payload = self.responses.get(("quote", symbol))
        if payload is not None:
            return 200, json.dumps(payload)
        return 404, json.dumps({"error": "not found"})


def quote(price):
    return {"priceInfo": {"lastPrice": price}}


class ConsentTests(unittest.TestCase):
    def test_no_consent_means_no_network_traffic(self):
        transport = FakeTransport()

        with self.assertRaises(ConsentRequired):
            fetch_nse_prices(["RELIANCE"], lambda: False, transport)

        self.assertEqual(transport.requests, [])

    def test_consent_must_be_callable(self):
        transport = FakeTransport()

        with self.assertRaises(ConsentRequired):
            fetch_nse_prices(["RELIANCE"], "yes", transport)

        self.assertEqual(transport.requests, [])

    def test_raising_consent_aborts_cleanly(self):
        def broken_consent():
            raise RuntimeError("dialog crashed")

        transport = FakeTransport()

        with self.assertRaises(ConsentRequired):
            fetch_nse_prices(["RELIANCE"], broken_consent, transport)

        self.assertEqual(transport.requests, [])

    def test_consent_granted_fetches_warmup_then_quotes(self):
        transport = FakeTransport({("quote", "RELIANCE"): quote(2600.5)})

        result = fetch_nse_prices(["RELIANCE"], lambda: True, transport)

        self.assertEqual(result["prices"], {"RELIANCE": 2600.5})
        self.assertEqual(result["failures"], {})
        # Warm-up homepage first, then the quote endpoint.
        self.assertEqual(len(transport.requests), 2)
        self.assertTrue(transport.requests[0].startswith("https://www.nseindia.com"))
        self.assertIn("symbol=RELIANCE", transport.requests[1])


class SymbolMappingTests(unittest.TestCase):
    def test_mechanical_mapping(self):
        self.assertEqual(nse_symbol("RELIANCE"), "RELIANCE")
        self.assertEqual(nse_symbol("TATASTEEL"), "TATASTEEL")

    def test_overrides(self):
        self.assertEqual(nse_symbol("COAL INDIA LTD"), "COALINDIA")
        self.assertEqual(nse_symbol("RELIANCE POWER L"), "RPOWER")
        self.assertEqual(nse_symbol("PUNJ. NATIONLBAK"), "PNB")

    def test_amc_prefix_display_names_map_to_the_ticker(self):
        # Fund-house display names from holding reports: the NSE ticker
        # is the part after 'AMC - '. Mechanical mapping alone would ask
        # NSE for GROWWAMCGROWWGOLD and get a 403.
        self.assertEqual(nse_symbol("GROWWAMC - GROWWGOLD"), "GROWWGOLD")
        self.assertEqual(nse_symbol("GROWWAMC - GROWWSLVR"), "GROWWSLVR")
        self.assertEqual(nse_symbol("GROWWAMC - GROWWDEFNC"), "GROWWDEFNC")

    def test_mutual_fund_scheme_detection(self):
        self.assertTrue(
            is_mutual_fund_scheme("HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH")
        )
        self.assertTrue(is_mutual_fund_scheme("Some Fund IDCW"))
        self.assertTrue(is_mutual_fund_scheme("Some Regular Plan"))
        self.assertFalse(is_mutual_fund_scheme("RELIANCE"))
        self.assertFalse(is_mutual_fund_scheme("GROWWAMC - GROWWGOLD"))
        self.assertFalse(is_mutual_fund_scheme(""))

    def test_delisted_symbol_maps_to_none(self):
        self.assertIsNone(nse_symbol("VEDANTA"))

    def test_empty_maps_to_none(self):
        self.assertIsNone(nse_symbol(""))
        self.assertIsNone(nse_symbol(None))


class FailureHandlingTests(unittest.TestCase):
    def test_per_symbol_failure_does_not_block_others(self):
        responses = {
            ("quote", "RELIANCE"): quote(2600.5),
            # ITC gets a 404 from the default path.
        }
        transport = FakeTransport(responses)

        result = fetch_nse_prices(["RELIANCE", "ITC"], lambda: True, transport)

        self.assertEqual(result["prices"], {"RELIANCE": 2600.5})
        self.assertIn("HTTP 404", result["failures"]["ITC"])

    def test_delisted_symbol_reported_as_failure(self):
        transport = FakeTransport()

        result = fetch_nse_prices(["VEDANTA", "RELIANCE"], lambda: True, transport)

        self.assertEqual(result["failures"]["VEDANTA"], "cannot map to an NSE symbol")
        self.assertEqual(result["prices"], {})  # RELIANCE 404'd in this fake

    def test_mutual_fund_scheme_skipped_without_a_request(self):
        transport = FakeTransport({("quote", "GROWWGOLD"): quote(75.2)})

        result = fetch_nse_prices(
            [
                "HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH",
                "GROWWAMC - GROWWGOLD",
            ],
            lambda: True,
            transport,
        )

        # The MF scheme is reported with a friendly reason and the ETF
        # display name is fetched under its real ticker.
        self.assertIn(
            "mutual fund scheme",
            result["failures"]["HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH"],
        )
        self.assertEqual(result["prices"], {"GROWWAMC - GROWWGOLD": 75.2})
        quote_requests = [r for r in transport.requests if "symbol=" in r]
        self.assertEqual(quote_requests, [
            "https://www.nseindia.com/api/quote-equity?symbol=GROWWGOLD",
        ])

    def test_transport_exception_reported_per_symbol(self):
        def exploding_transport(url, headers):
            if "symbol=" in url:
                raise ConnectionError("reset by peer")
            return 200, ""

        result = fetch_nse_prices(["ITC"], lambda: True, exploding_transport)

        self.assertIn("request failed", result["failures"]["ITC"])

    def test_non_json_body_reported(self):
        transport = FakeTransport()
        transport.responses[("quote", "ITC")] = None
        transport.responses["https://www.nseindia.com/api/quote-equity?symbol=ITC"] = (
            200,
            "<html>blocked</html>",
        )

        result = fetch_nse_prices(["ITC"], lambda: True, transport)

        self.assertEqual(result["failures"]["ITC"], "NSE returned a non-JSON response")

    def test_priceless_payload_reported(self):
        transport = FakeTransport({("quote", "ITC"): {"priceInfo": {}}})

        result = fetch_nse_prices(["ITC"], lambda: True, transport)

        self.assertEqual(result["failures"]["ITC"], "no price in the NSE response")

    def test_string_price_with_currency_is_cleaned(self):
        transport = FakeTransport({("quote", "ITC"): quote("₹ 450.60")})

        result = fetch_nse_prices(["ITC"], lambda: True, transport)

        self.assertEqual(result["prices"], {"ITC": 450.6})


class DefaultTransportTests(unittest.TestCase):
    def test_default_transport_is_the_cookie_transport_and_gated(self):
        # Patch the transport class so the consented default path stays
        # offline; gating itself is covered by the consent tests above.
        calls = []

        class StubTransport:
            def __call__(self, url, headers):
                calls.append(url)
                if "symbol=" in url:
                    return 200, json.dumps(quote(123.45))
                return 200, ""

        with patch("market_data.nse._UrllibTransport", StubTransport):
            result = fetch_nse_prices(["ITC"], lambda: True)

        self.assertEqual(result["prices"], {"ITC": 123.45})
        self.assertEqual(len(calls), 2)  # warm-up + one quote


if __name__ == "__main__":
    unittest.main()
