import urllib.error
import urllib.request
from collections.abc import Callable


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
    request = urllib.request.Request(url, method="HEAD")
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
    later run can re-check it.
    """
    url = construct_official_url(set_num)
    try:
        status_code = fetch(url)
    except urllib.error.HTTPError as error:
        return url, "retired" if error.code == 404 else "unchecked"
    except Exception:
        return url, "unchecked"
    return url, "ok" if status_code == 200 else "unchecked"
