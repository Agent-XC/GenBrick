import logging
import urllib.error
import urllib.request
from collections.abc import Callable

logger = logging.getLogger(__name__)

# LEGO.com's bot protection 403s a bare urllib request — Python's default
# "Python-urllib/x.y" User-Agent reads as a non-browser client. A
# browser-like User-Agent is enough to pass (see issue #15's investigation:
# every one of 12 owned Boxes resolved 'unchecked', and a manual curl from a
# similar non-browser context reproduced the 403).
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def construct_official_url(set_num: str) -> str:
    """Naively construct a LEGO.com product URL from a Rebrickable set_num.

    Not verified against a live request — that's resolve_official_link below.
    """
    base_set_number = set_num.split("-")[0]
    return f"https://www.lego.com/en-us/product/{base_set_number}"


def fetch_status_code(url: str) -> int:
    """Real HTTP HEAD request against `url`. Raises on a non-2xx/3xx response or
    a network failure — the two are told apart by resolve_official_link below.
    """
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status


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
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return url, "retired"
        logger.warning("Official link check for %s (%s) failed: HTTP %s", set_num, url, error.code)
        return url, "unchecked"
    except Exception as error:
        logger.warning("Official link check for %s (%s) failed: %s", set_num, url, error)
        return url, "unchecked"
    if status_code == 200:
        return url, "ok"
    logger.warning("Official link check for %s (%s) returned unexpected status %s", set_num, url, status_code)
    return url, "unchecked"
