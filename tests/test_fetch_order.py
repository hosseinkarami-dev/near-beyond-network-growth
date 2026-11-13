import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from urllib.error import HTTPError
from urllib.request import Request


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from fetch import _fetch_order, _nearblocks_urlopen
from sources import SOURCES, SourceName


class FetchOrderTests(unittest.TestCase):
    def test_daily_validator_stake_is_last_and_supply_runs_first(self):
        ordered = _fetch_order(SOURCES)
        names = [source.name for source in ordered]

        self.assertEqual(names[-1], SourceName.FASTNEAR_DAILY_ACTIVE_VALIDATOR_STAKE)
        self.assertLess(names.index(SourceName.BIGQUERY_DAILY_SUPPLY), names.index(names[-1]))

    def test_daily_validator_stake_is_deferred_for_custom_source_order(self):
        sources = tuple(reversed(SOURCES))
        names = [source.name for source in _fetch_order(sources)]

        self.assertEqual(names[-1], SourceName.FASTNEAR_DAILY_ACTIVE_VALIDATOR_STAKE)
        self.assertLess(names.index(SourceName.BIGQUERY_DAILY_SUPPLY), names.index(names[-1]))

    def test_nearblocks_retries_http_429_with_backoff(self):
        throttled = HTTPError("https://api.nearblocks.io", 429, "Too Many Requests", None, None)
        response = Mock()
        with (
            patch("fetch.urlopen", side_effect=[throttled, response]) as open_request,
            patch("fetch.time.sleep") as sleep,
            patch("fetch._last_nearblocks_response_at", None),
        ):
            self.assertIs(_nearblocks_urlopen(Request("https://api.nearblocks.io"), 5), response)

        self.assertEqual(open_request.call_count, 2)
        self.assertTrue(any(call.args[0] >= 1 for call in sleep.call_args_list))

    def test_nearblocks_spaces_successful_requests(self):
        first_response = Mock()
        second_response = Mock()
        with (
            patch("fetch.urlopen", side_effect=[first_response, second_response]),
            patch("fetch.time.sleep") as sleep,
            patch("fetch.time.monotonic", side_effect=[100.0, 100.2, 100.3]),
            patch("fetch._last_nearblocks_response_at", None),
        ):
            _nearblocks_urlopen(Request("https://api.nearblocks.io", method="GET"), 5)
            _nearblocks_urlopen(Request("https://api.nearblocks.io", method="GET"), 5)

        self.assertAlmostEqual(sleep.call_args.args[0], 0.8)


if __name__ == "__main__":
    unittest.main()
