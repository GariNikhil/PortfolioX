"""Tests for the consent-gated mfapi.in NAV fetcher.

The transport is a fake in every test: no test ever touches the network.
The canned responses mirror the real API shapes verified live:
/mf/search returns a list of {schemeCode, schemeName}; /mf/{code}
returns {"meta": {...}, "data": [{"date", "nav"}, ...]} newest-first.
"""

import json
import unittest
from unittest.mock import MagicMock, patch

from market_data.mfapi import (
    MfapiFetchError,
    fetch_mf_navs,
    match_scheme,
)

SEARCH_URL_HDFC = (
    "https://api.mfapi.in/mf/search?q=HDFC%20ELSS%20TAX%20SAVER"
)
SEARCH_URL_PARAG = (
    "https://api.mfapi.in/mf/search?q=PARAG%20PARIKH%20ELSS%20TAX%20SAVER"
)

HDFC_HITS = [
    {"schemeCode": 101979, "schemeName": "HDFC ELSS - Tax Saver Fund - Regular Plan - Growth Option"},
    {"schemeCode": 101980, "schemeName": "HDFC ELSS - Tax Saver Fund - Regular Plan - IDCW Option"},
    {"schemeCode": 119059, "schemeName": "HDFC ELSS - Tax Saver Fund - Direct Plan - IDCW Option"},
    {"schemeCode": 119060, "schemeName": "HDFC ELSS - Tax Saver Fund - Direct Plan - Growth Option"},
]


def detail(code, nav):
    return 200, json.dumps({
        "meta": {"scheme_code": code},
        "data": [
            {"date": "28-10-2026", "nav": f"{nav}"},
            {"date": "27-10-2026", "nav": f"{nav - 1}"},
        ],
    })


def fake_transport_factory(responses):
    class FakeTransport:
        def __init__(self):
            self.requests = []

        def __call__(self, url, headers):
            self.requests.append(url)
            if url not in responses:
                return 404, "{}"
            return responses[url]

    return FakeTransport


class ConsentTests(unittest.TestCase):
    def test_no_consent_means_no_network_traffic(self):
        transport = fake_transport_factory({})()

        with self.assertRaises(MfapiFetchError):
            fetch_mf_navs(["HDFC ELSS"], lambda: False, transport)

        self.assertEqual(transport.requests, [])

    def test_consent_must_be_callable(self):
        transport = fake_transport_factory({})()

        with self.assertRaises(MfapiFetchError):
            fetch_mf_navs(["HDFC ELSS"], "yes", transport)

        self.assertEqual(transport.requests, [])

    def test_broken_consent_raises_without_network_traffic(self):
        transport = fake_transport_factory({})()

        def broken_consent():
            raise RuntimeError("dialog crashed")

        with self.assertRaises(MfapiFetchError):
            fetch_mf_navs(["HDFC ELSS"], broken_consent, transport)

        self.assertEqual(transport.requests, [])


class FetchTests(unittest.TestCase):
    def test_search_then_detail_fetches_the_latest_nav(self):
        transport = fake_transport_factory({
            SEARCH_URL_HDFC: (200, json.dumps(HDFC_HITS)),
            "https://api.mfapi.in/mf/119060": detail(119060, 1854.32),
        })()

        result = fetch_mf_navs(
            ["HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH"], lambda: True, transport,
        )

        self.assertEqual(
            result["prices"], {"HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH": 1854.32},
        )
        self.assertEqual(result["failures"], {})
        self.assertEqual(
            transport.requests,
            [SEARCH_URL_HDFC, "https://api.mfapi.in/mf/119060"],
        )

    def test_direct_plan_beats_regular_and_idcw_variants(self):
        transport = fake_transport_factory({
            SEARCH_URL_HDFC: (200, json.dumps(HDFC_HITS)),
            "https://api.mfapi.in/mf/119060": detail(119060, 1854.32),
        })()

        result = fetch_mf_navs(
            ["HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH"], lambda: True, transport,
        )

        # The Regular Plan or IDCW NAV would silently misvalue the holding.
        self.assertEqual(transport.requests[-1], "https://api.mfapi.in/mf/119060")

    def test_unknown_scheme_reported_as_failure(self):
        transport = fake_transport_factory({
            SEARCH_URL_HDFC: (200, "[]"),
        })()

        result = fetch_mf_navs(
            ["HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH"], lambda: True, transport,
        )

        self.assertEqual(result["prices"], {})
        self.assertEqual(
            result["failures"]["HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH"],
            "no mfapi scheme matched",
        )

    def test_per_scheme_failure_does_not_block_others(self):
        transport = fake_transport_factory({
            SEARCH_URL_HDFC: (200, json.dumps(HDFC_HITS)),
            "https://api.mfapi.in/mf/119060": detail(119060, 1854.32),
            SEARCH_URL_PARAG: (503, "busy"),
        })()

        result = fetch_mf_navs(
            [
                "HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH",
                "PARAG PARIKH ELSS TAX SAVER FUND DIRECT GROWTH",
            ],
            lambda: True,
            transport,
        )

        self.assertEqual(
            result["prices"], {"HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH": 1854.32},
        )
        self.assertEqual(
            result["failures"]["PARAG PARIKH ELSS TAX SAVER FUND DIRECT GROWTH"],
            "mfapi search returned HTTP 503",
        )

    def test_search_non_json_reported(self):
        transport = fake_transport_factory({
            SEARCH_URL_HDFC: (200, "<html>blocked</html>"),
        })()

        result = fetch_mf_navs(["HDFC ELSS TAX SAVER FUND"], lambda: True, transport)

        self.assertEqual(
            result["failures"]["HDFC ELSS TAX SAVER FUND"],
            "mfapi search returned a non-JSON response",
        )

    def test_empty_nav_history_reported(self):
        transport = fake_transport_factory({
            SEARCH_URL_HDFC: (200, json.dumps(HDFC_HITS)),
            "https://api.mfapi.in/mf/119060": (200, json.dumps({"meta": {}, "data": []})),
        })()

        result = fetch_mf_navs(
            ["HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH"], lambda: True, transport,
        )

        self.assertEqual(
            result["failures"]["HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH"],
            "no NAV history in the mfapi response",
        )


class MatchTests(unittest.TestCase):
    def test_direct_plan_wins_over_regular(self):
        match = match_scheme("HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH", HDFC_HITS)

        self.assertEqual(match["schemeCode"], 119060)

    def test_regular_plan_wins_when_stored_says_regular(self):
        match = match_scheme("HDFC ELSS TAX SAVER FUND REGULAR GROWTH", HDFC_HITS)

        self.assertEqual(match["schemeCode"], 101979)

    def test_family_anchor_blocks_cross_fund_matches(self):
        # 'QUANT ELSS ...' shares every generic token with the HDFC hits;
        # the anchor rule must reject them all.
        match = match_scheme("QUANT ELSS TAX SAVER FUND DIRECT PLAN GROWTH", HDFC_HITS)

        self.assertIsNone(match)

    def test_no_tokens_means_no_match(self):
        self.assertIsNone(match_scheme("", HDFC_HITS))
        self.assertIsNone(match_scheme("!!!", HDFC_HITS))

    def test_non_dict_hits_are_ignored(self):
        match = match_scheme("HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH", [None, 42])

        self.assertIsNone(match)


class DefaultTransportTests(unittest.TestCase):
    def test_default_transport_is_urllib_and_gated_by_consent(self):
        # Patch urllib so even the consented path stays offline in tests;
        # side_effect serves the search response, then the detail response.
        responses = [
            (200, json.dumps(HDFC_HITS).encode()),
            (200, detail(119060, 1854.32)[1].encode()),
        ]

        def fake_open_factory(responses):
            def fake_open(request, timeout=None):
                context = MagicMock()
                status, body = responses.pop(0)
                context.__enter__.return_value.status = status
                context.__enter__.return_value.read.return_value = body
                return context
            return fake_open

        with patch(
            "market_data.mfapi.urllib.request.urlopen", fake_open_factory(responses),
        ):
            result = fetch_mf_navs(
                ["HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH"], lambda: True,
            )

        self.assertEqual(
            result["prices"]["HDFC ELSS TAX SAVER FUND DIRECT PLAN GROWTH"],
            1854.32,
        )
        self.assertEqual(result["failures"], {})


if __name__ == "__main__":
    unittest.main()
