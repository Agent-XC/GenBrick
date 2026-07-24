import logging
from unittest.mock import MagicMock, call, patch

import pytest

from pipeline.links import USER_AGENT, resolve_official_link


def test_a_live_page_resolves_as_ok():
    url, status = resolve_official_link("75192-1", fetch=lambda url: 200)

    assert url == "https://www.lego.com/fr-fr/product/75192"
    assert status == "ok"


def test_a_404_status_resolves_as_retired():
    """Unlike urllib, a real-browser fetch doesn't raise on a non-2xx status
    — every HTTP status (200, 404, 403, ...) comes back as a plain return
    value (see pipeline/links.py's _navigate_and_get_status), so 404 is told
    apart from other failures by its status code alone, not an exception.
    """
    _, status = resolve_official_link("99999-1", fetch=lambda url: 404)

    assert status == "retired"


@pytest.mark.parametrize(
    "fetch",
    [
        pytest.param(lambda url: (_ for _ in ()).throw(RuntimeError("navigation timeout")), id="navigation-failure"),
        pytest.param(lambda url: 500, id="server-error"),
        pytest.param(lambda url: 301, id="unexpected-status-code"),
    ],
)
def test_a_checker_failure_resolves_as_unchecked_without_crashing(fetch):
    url, status = resolve_official_link("75192-1", fetch=fetch)

    assert url == "https://www.lego.com/fr-fr/product/75192"
    assert status == "unchecked"


def test_fetch_status_code_sends_a_browser_like_user_agent():
    """Issue #15's investigation: LEGO.com's bot protection 403s a bare HTTP
    client even with a spoofed browser User-Agent header — a real browser is
    required, not just a header. USER_AGENT is still set explicitly on the
    Playwright page so headless Chromium presents as ordinary desktop Chrome
    rather than its default "HeadlessChrome" UA, which some bot protection
    treats as its own signal.
    """
    from pipeline.links import fetch_status_code

    mock_page = MagicMock()
    mock_page.goto.return_value = MagicMock(status=200)
    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page
    mock_playwright_context = MagicMock()
    mock_playwright_context.chromium.launch.return_value = mock_browser

    with patch("pipeline.links.sync_playwright") as mock_sync_playwright:
        mock_sync_playwright.return_value.__enter__.return_value = mock_playwright_context
        fetch_status_code("https://www.lego.com/fr-fr/product/75192")

    mock_browser.new_page.assert_called_once_with(user_agent=USER_AGENT)
    mock_browser.close.assert_called_once()


def test_a_checker_failure_logs_a_warning_so_it_shows_up_in_the_actions_run_log(caplog):
    with caplog.at_level(logging.WARNING):
        resolve_official_link("75192-1", fetch=lambda url: (_ for _ in ()).throw(RuntimeError("timed out")))

    assert len(caplog.records) == 1
    assert "75192-1" in caplog.records[0].message
    assert "https://www.lego.com/fr-fr/product/75192" in caplog.records[0].message


def test_an_unexpected_status_code_also_logs_a_warning(caplog):
    with caplog.at_level(logging.WARNING):
        resolve_official_link("75192-1", fetch=lambda url: 301)

    assert len(caplog.records) == 1
    assert "75192-1" in caplog.records[0].message


def test_a_404_does_not_log_a_warning_since_retired_is_an_expected_outcome(caplog):
    with caplog.at_level(logging.WARNING):
        resolve_official_link("99999-1", fetch=lambda url: 404)

    assert caplog.records == []


def test_playwright_link_resolver_shares_one_browser_and_page_across_calls():
    """The whole point of playwright_link_resolver over resolve_official_link's
    plain default: launching a browser once for the batch of checks in a
    pipeline run, not once per set_num (issue #15 — up to ~1,000+ checks in
    production). Assert the browser/page are created exactly once no matter
    how many set_nums get resolved through the yielded callable.
    """
    from pipeline.links import playwright_link_resolver

    mock_page = MagicMock()
    mock_page.goto.return_value = MagicMock(status=200)
    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page
    mock_playwright_context = MagicMock()
    mock_playwright_context.chromium.launch.return_value = mock_browser

    with patch("pipeline.links.sync_playwright") as mock_sync_playwright:
        mock_sync_playwright.return_value.__enter__.return_value = mock_playwright_context
        with playwright_link_resolver() as resolve:
            first = resolve("75192-1")
            second = resolve("10281-1")

    assert first == ("https://www.lego.com/fr-fr/product/75192", "ok")
    assert second == ("https://www.lego.com/fr-fr/product/10281", "ok")
    mock_browser.new_page.assert_called_once_with(user_agent=USER_AGENT)
    assert mock_page.goto.call_args_list == [
        call("https://www.lego.com/fr-fr/product/75192", wait_until="domcontentloaded", timeout=15000),
        call("https://www.lego.com/fr-fr/product/10281", wait_until="domcontentloaded", timeout=15000),
    ]
    mock_browser.close.assert_called_once()
