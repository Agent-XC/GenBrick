import logging
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from pipeline.links import USER_AGENT, fetch_status_code, resolve_official_link


def test_a_live_page_resolves_as_ok():
    url, status = resolve_official_link("75192-1", fetch=lambda url: 200)

    assert url == "https://www.lego.com/en-us/product/75192"
    assert status == "ok"


def test_a_404_response_resolves_as_retired():
    def fetch_404(url: str) -> int:
        raise urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)

    _, status = resolve_official_link("99999-1", fetch=fetch_404)

    assert status == "retired"


@pytest.mark.parametrize(
    "fetch",
    [
        pytest.param(lambda url: (_ for _ in ()).throw(urllib.error.URLError("timed out")), id="network-error"),
        pytest.param(
            lambda url: (_ for _ in ()).throw(
                urllib.error.HTTPError(url, 500, "Server Error", hdrs=None, fp=None)
            ),
            id="server-error",
        ),
        pytest.param(lambda url: 301, id="unexpected-status-code"),
    ],
)
def test_a_checker_failure_resolves_as_unchecked_without_crashing(fetch):
    url, status = resolve_official_link("75192-1", fetch=fetch)

    assert url == "https://www.lego.com/en-us/product/75192"
    assert status == "unchecked"


def test_fetch_status_code_sends_a_browser_like_user_agent():
    """Issue #15's investigation: a bare urllib request (Python's default
    "Python-urllib/x.y" User-Agent) gets 403'd by LEGO.com's bot protection —
    every one of 12 owned Boxes resolved 'unchecked' in the live DB. A
    browser-like User-Agent header is the fix.
    """
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.__enter__.return_value = mock_response

    with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
        fetch_status_code("https://www.lego.com/en-us/product/75192")

    request = mock_urlopen.call_args[0][0]
    assert request.get_header("User-agent") == USER_AGENT


@pytest.mark.parametrize(
    "fetch",
    [
        pytest.param(lambda url: (_ for _ in ()).throw(urllib.error.URLError("timed out")), id="network-error"),
        pytest.param(lambda url: 301, id="unexpected-status-code"),
    ],
)
def test_a_checker_failure_logs_a_warning_so_it_shows_up_in_the_actions_run_log(fetch, caplog):
    """Issue #15: every owned Box resolved 'unchecked' with nothing in the
    weekly Action's own logs explaining why — a failure that lands on
    'unchecked' must now log a warning naming the set_num and URL.
    """
    with caplog.at_level(logging.WARNING):
        resolve_official_link("75192-1", fetch=fetch)

    assert len(caplog.records) == 1
    assert "75192-1" in caplog.records[0].message
    assert "https://www.lego.com/en-us/product/75192" in caplog.records[0].message


def test_a_404_does_not_log_a_warning_since_retired_is_an_expected_outcome(caplog):
    def fetch_404(url: str) -> int:
        raise urllib.error.HTTPError(url, 404, "Not Found", hdrs=None, fp=None)

    with caplog.at_level(logging.WARNING):
        resolve_official_link("99999-1", fetch=fetch_404)

    assert caplog.records == []
