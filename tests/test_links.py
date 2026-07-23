import urllib.error

import pytest

from pipeline.links import resolve_official_link


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
