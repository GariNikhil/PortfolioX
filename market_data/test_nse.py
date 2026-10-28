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
    def test_default_transport_is_urllib_and_gated_by_consent(self):
        # Patch urllib so even the consented path stays offline in tests.
        with patch("market_data.nse.urllib.request.urlopen") as fake_open:
            fake_open.return_value.__enter__.return_value.status = 200
            fake_open.return_value.__enter__.return_value.read.return_value = (
                json.dumps(quote(123.45)).encode()
            )

            result = fetch_nse_prices(["ITC"], lambda: True)

        self.assertEqual(result["prices"], {"ITC": 123.45})


if __name__ == "__main__":
    unittest.main()
