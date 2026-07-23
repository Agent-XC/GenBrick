import gzip

import pytest

from pipeline.fetch_rebrickable import RAW_TABLE_NAMES, fetch_and_gunzip, fetch_rebrickable_dump


def test_fetch_rebrickable_dump_writes_every_raw_table_csv(tmp_path):
    def fake_fetch(url: str, api_token: str | None) -> bytes:
        table = url.rsplit("/", 1)[-1].removesuffix(".csv.gz")
        return f"fake csv for {table}".encode()

    fetch_rebrickable_dump(tmp_path, fetch=fake_fetch)

    for table in RAW_TABLE_NAMES:
        assert (tmp_path / f"{table}.csv").read_text() == f"fake csv for {table}"


def test_fetch_rebrickable_dump_creates_raw_dir_if_missing(tmp_path):
    raw_dir = tmp_path / "01_raw"
    assert not raw_dir.exists()

    fetch_rebrickable_dump(raw_dir, fetch=lambda url, api_token: b"data")

    assert raw_dir.is_dir()


def test_fetch_rebrickable_dump_requests_the_cdn_url_for_each_table(tmp_path):
    requested_urls = []

    def fake_fetch(url: str, api_token: str | None) -> bytes:
        requested_urls.append(url)
        return b"data"

    fetch_rebrickable_dump(tmp_path, fetch=fake_fetch)

    assert requested_urls == [
        f"https://cdn.rebrickable.com/media/downloads/{table}.csv.gz" for table in RAW_TABLE_NAMES
    ]


def test_fetch_rebrickable_dump_passes_the_api_token_through_to_fetch(tmp_path):
    received_tokens = []

    def fake_fetch(url: str, api_token: str | None) -> bytes:
        received_tokens.append(api_token)
        return b"data"

    fetch_rebrickable_dump(tmp_path, fetch=fake_fetch, api_token="secret-token")

    assert received_tokens == ["secret-token"] * len(RAW_TABLE_NAMES)


def test_fetch_rebrickable_dump_defaults_the_api_token_to_none(tmp_path):
    received_tokens = []

    def fake_fetch(url: str, api_token: str | None) -> bytes:
        received_tokens.append(api_token)
        return b"data"

    fetch_rebrickable_dump(tmp_path, fetch=fake_fetch)

    assert received_tokens == [None] * len(RAW_TABLE_NAMES)


class _FakeGzipResponse:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return gzip.compress(b"csv,bytes")


@pytest.mark.parametrize(
    "api_token,expected_header",
    [
        pytest.param("secret-token", "key secret-token", id="with-token"),
        pytest.param(None, None, id="without-token"),
    ],
)
def test_fetch_and_gunzip_sends_the_api_token_as_an_authorization_header_only_when_set(
    monkeypatch, api_token, expected_header
):
    import pipeline.fetch_rebrickable as fetch_rebrickable_module

    captured_requests = []

    def fake_urlopen(request, timeout):
        captured_requests.append(request)
        return _FakeGzipResponse()

    monkeypatch.setattr(fetch_rebrickable_module.urllib.request, "urlopen", fake_urlopen)

    result = fetch_rebrickable_module.fetch_and_gunzip(
        "https://cdn.rebrickable.com/media/downloads/sets.csv.gz", api_token=api_token
    )

    assert result == b"csv,bytes"
    assert captured_requests[0].get_header("Authorization") == expected_header


def test_fetch_and_gunzip_decompresses_the_response_body(monkeypatch):
    import pipeline.fetch_rebrickable as fetch_rebrickable_module

    monkeypatch.setattr(
        fetch_rebrickable_module.urllib.request, "urlopen", lambda request, timeout: _FakeGzipResponse()
    )

    result = fetch_and_gunzip("https://cdn.rebrickable.com/media/downloads/sets.csv.gz")

    assert result == b"csv,bytes"
