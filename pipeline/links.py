import logging
from collections.abc import Callable, Iterator
from contextlib import contextmanager

from playwright.sync_api import Page, sync_playwright

logger = logging.getLogger(__name__)

# A bare HTTP client gets 403'd by LEGO.com's bot protection even with a
# spoofed browser User-Agent — confirmed from a sandboxed environment with a
# manual curl sending a full browser UA plus matching Accept/Accept-Language
# headers (issue #15). It isn't a UA sniff a header can talk past; a real
# browser context is required. USER_AGENT is still set explicitly below so
# the headless Chromium instance presents as an ordinary desktop Chrome
# rather than its default "HeadlessChrome" UA string, which some bot
# protection treats as its own signal.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def construct_official_url(set_num: str) -> str:
    """Naively construct a LEGO.com product URL from a Rebrickable set_num.

    Not verified against a live request — that's resolve_official_link below.

    The `fr-fr` locale path is used rather than `en-us`: issue #15's
    investigation found `en-us` product pages 403 (bot protection), while
    `fr-fr` resolves — an interim workaround noted while the checker was
    still `urllib`-based, kept now that the checker is Playwright-based too
    since there's no reason to prefer the locale that's known to be blocked.
    """
    base_set_number = set_num.split("-")[0]
    return f"https://www.lego.com/fr-fr/product/{base_set_number}"


def _navigate_and_get_status(page: Page, url: str) -> int:
    """Real navigation via a Playwright Page, returning the main-frame
    response's HTTP status. Unlike urllib, Playwright doesn't raise on a
    non-2xx response — goto() only raises on a true navigation failure
    (timeout, DNS, connection refused, ...) — so every status (200, 403, 404,
    ...) comes back through the return value, not an exception.
    """
    response = page.goto(url, wait_until="domcontentloaded", timeout=15000)
    if response is None:
        raise RuntimeError(f"navigating to {url} produced no response")
    return response.status


@contextmanager
def _launch_chromium_page() -> Iterator[Page]:
    """One headless Chromium browser + page, closed on exit. Shared by
    fetch_status_code (a fresh one per call) and playwright_link_resolver (one
    reused across a whole batch) so the launch/teardown shape lives in one
    place.
    """
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            yield browser.new_page(user_agent=USER_AGENT)
        finally:
            browser.close()


def fetch_status_code(url: str) -> int:
    """Real check against `url` via a single-use headless Chromium instance.

    Correct on its own, but launches and closes a whole browser per call —
    fine for one-off use, wasteful for the weekly pipeline's ~1,000+ link
    checks in a single run. That path should use playwright_link_resolver
    below instead, which shares one browser/page across every check.
    """
    with _launch_chromium_page() as page:
        return _navigate_and_get_status(page, url)


def resolve_official_link(
    set_num: str, fetch: Callable[[str], int] = fetch_status_code
) -> tuple[str, str]:
    """set_num -> (official_url, official_url_status: ok | retired | unchecked).

    Wraps the network I/O boundary so it can be faked in tests. A 404 means
    LEGO.com no longer serves a page for this set (retired). Any other
    failure to reach LEGO.com — timeout, DNS, a 5xx, an unexpected exception
    — leaves the status `unchecked` rather than crashing the pipeline; a
    later run can re-check it. Every path that lands on 'unchecked' logs a
    warning first, so a future run's failure mode shows up in the weekly
    Action's own logs instead of being silently swallowed (issue #15).
    """
    url = construct_official_url(set_num)
    try:
        status_code = fetch(url)
    except Exception as error:
        logger.warning("Official link check for %s (%s) failed: %s", set_num, url, error)
        return url, "unchecked"
    if status_code == 200:
        return url, "ok"
    if status_code == 404:
        return url, "retired"
    logger.warning("Official link check for %s (%s) returned unexpected status %s", set_num, url, status_code)
    return url, "unchecked"


@contextmanager
def playwright_link_resolver() -> Iterator[Callable[[str], tuple[str, str]]]:
    """Context-managed real-browser link checker: one headless Chromium
    instance and page, launched once and reused for every resolve_official_link
    call made through the yielded callable, rather than relaunching a browser
    per set_num.

    Wire this in wherever many links get checked in one run (pipeline/run.py's
    __main__, which checks every owned + Candidate set — up to ~1,000+ in
    production, per issue #15). Callers checking only a handful of links can
    use resolve_official_link's plain default instead.
    """
    with _launch_chromium_page() as page:
        yield lambda set_num: resolve_official_link(
            set_num, fetch=lambda url: _navigate_and_get_status(page, url)
        )
