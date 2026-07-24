import csv

from pipeline.build_ldraw_crosswalk import (
    build_colors_crosswalk,
    build_parts_crosswalk,
    fetch_ldraw_crosswalks,
    list_ldraw_part_ids,
    match_colors,
    match_parts,
    normalize_color_name,
    parse_ldconfig_colors,
    strip_decoration_suffix,
)

FAKE_LDCONFIG = """\
0 // LDraw Solid Colours
0                              // LEGOID  26 - Black
0 !COLOUR Black                CODE     0   VALUE #1B2A34   EDGE #808080
0                              // LEGOID  23 - Bright Blue
0 !COLOUR Blue                 CODE     1   VALUE #1E5AA8   EDGE #333333
0 !COLOUR Trans_Red            CODE    36   VALUE #CA1F08   EDGE #671710 ALPHA 128
0 !COLOUR Light_Grey           CODE     7   VALUE #8A928D   EDGE #333333
"""


def test_normalize_color_name_treats_hyphens_and_underscores_as_spaces():
    assert normalize_color_name("Trans-Red") == normalize_color_name("Trans_Red") == "trans red"


def test_normalize_color_name_treats_gray_and_grey_as_equivalent():
    assert normalize_color_name("Light Gray") == normalize_color_name("Light_Grey") == "light grey"


def test_normalize_color_name_collapses_repeated_whitespace_and_case():
    assert normalize_color_name("  BLUE  ") == "blue"


def test_parse_ldconfig_colors_extracts_code_by_normalized_name():
    colors = parse_ldconfig_colors(FAKE_LDCONFIG)

    assert colors == {"black": 0, "blue": 1, "trans red": 36, "light grey": 7}


def test_parse_ldconfig_colors_ignores_legoid_comment_lines():
    # The `// LEGOID nn - Name` lines aren't `!COLOUR` definitions and use a
    # different (real LEGO catalog) numbering system entirely — parsing them
    # as if they were colour codes would silently produce wrong crosswalk rows.
    colors = parse_ldconfig_colors(FAKE_LDCONFIG)

    assert "26" not in colors
    assert all(isinstance(code, int) for code in colors.values())


def test_match_colors_matches_by_normalized_name():
    rebrickable_colors = [
        {"id": 0, "name": "Black"},
        {"id": 1, "name": "Blue"},
        {"id": 7, "name": "Light Gray"},
        {"id": 36, "name": "Trans-Red"},
    ]
    ldraw_colors_by_name = parse_ldconfig_colors(FAKE_LDCONFIG)

    assert match_colors(rebrickable_colors, ldraw_colors_by_name) == {0: 0, 1: 1, 7: 7, 36: 36}


def test_match_colors_omits_a_color_with_no_ldraw_name_match():
    rebrickable_colors = [{"id": 85, "name": "Dark Purple"}]
    ldraw_colors_by_name = parse_ldconfig_colors(FAKE_LDCONFIG)

    assert match_colors(rebrickable_colors, ldraw_colors_by_name) == {}


def test_build_colors_crosswalk_returns_sorted_crosswalk_rows():
    rebrickable_colors = [
        {"id": 36, "name": "Trans-Red"},
        {"id": 0, "name": "Black"},
        {"id": 85, "name": "Dark Purple"},
    ]

    rows = build_colors_crosswalk(rebrickable_colors, FAKE_LDCONFIG)

    assert rows == [
        {"color_id": 0, "ldraw_color_id": 0},
        {"color_id": 36, "ldraw_color_id": 36},
    ]


def test_strip_decoration_suffix_removes_known_print_and_pattern_suffixes():
    assert strip_decoration_suffix("3069bpb1234") == "3069b"
    assert strip_decoration_suffix("26603pr0097") == "26603"
    assert strip_decoration_suffix("7182pat0001") == "7182"
    assert strip_decoration_suffix("44302c01") == "44302"


def test_strip_decoration_suffix_leaves_plain_part_numbers_unchanged():
    assert strip_decoration_suffix("3001") == "3001"
    assert strip_decoration_suffix("3068b") == "3068b"


def test_list_ldraw_part_ids_reads_dat_filenames_from_the_given_directory(tmp_path):
    (tmp_path / "3001.dat").write_text("")
    (tmp_path / "3068b.dat").write_text("")
    (tmp_path / "readme.txt").write_text("")

    assert list_ldraw_part_ids(tmp_path) == {"3001", "3068b"}


def test_match_parts_matches_an_exact_filename_hit():
    assert match_parts(["3001"], {"3001", "3068b"}) == {"3001": "3001"}


def test_match_parts_falls_back_to_the_decoration_stripped_base_part():
    # 3069bpb1234 (a printed 1x2 tile) has no LDraw file of its own, but this
    # project's render only resolves (part, colour) — it never models prints —
    # so the plain 3069b tile is what it would actually render as.
    assert match_parts(["3069bpb1234"], {"3069b"}) == {"3069bpb1234": "3069b"}


def test_match_parts_omits_a_part_missing_from_ldraw_even_after_stripping():
    assert match_parts(["9999999"], {"3001"}) == {}


def test_match_parts_does_not_fabricate_a_base_id_that_is_not_a_real_ldraw_file():
    # 26603pr0097's stripped base (26603) isn't itself a real LDraw part in
    # this fake universe — the row must be dropped, not guessed at.
    assert match_parts(["26603pr0097"], {"3001"}) == {}


def test_build_parts_crosswalk_returns_sorted_crosswalk_rows():
    rows = build_parts_crosswalk(["3068b", "3069bpb1234", "9999999"], {"3001", "3068b", "3069b"})

    assert rows == [
        {"part_num": "3068b", "ldraw_part_id": "3068b"},
        {"part_num": "3069bpb1234", "ldraw_part_id": "3069b"},
    ]


def _fake_csv_bytes(rows: list[dict], fieldnames: list[str]) -> bytes:
    # fetch_and_gunzip (this module's default `fetch`) already returns
    # decompressed bytes — the fake here mirrors that contract, not the raw
    # gzip stream over the wire.
    import io as _io

    buffer = _io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def test_fetch_ldraw_crosswalks_writes_both_csvs_from_a_fake_fetch_and_a_real_ldraw_dir(tmp_path):
    ldraw_dir = tmp_path / "ldraw"
    (ldraw_dir / "parts").mkdir(parents=True)
    (ldraw_dir / "LDConfig.ldr").write_text(FAKE_LDCONFIG)
    (ldraw_dir / "parts" / "3001.dat").write_text("")
    (ldraw_dir / "parts" / "3068b.dat").write_text("")

    fake_colors_csv = _fake_csv_bytes(
        [{"id": "0", "name": "Black"}, {"id": "85", "name": "Dark Purple"}], ["id", "name"]
    )
    fake_parts_csv = _fake_csv_bytes(
        [{"part_num": "3068b"}, {"part_num": "3069bpb1234"}, {"part_num": "9999999"}], ["part_num"]
    )

    def fake_fetch(url: str, api_token: str | None) -> bytes:
        if url.endswith("colors.csv.gz"):
            return fake_colors_csv
        if url.endswith("parts.csv.gz"):
            return fake_parts_csv
        raise AssertionError(f"unexpected url: {url}")

    data_dir = tmp_path / "data"
    fetch_ldraw_crosswalks(ldraw_dir, data_dir, fetch=fake_fetch)

    assert (data_dir / "ldraw_colors_crosswalk.csv").read_text() == "color_id,ldraw_color_id\n0,0\n"
    assert (data_dir / "ldraw_parts_crosswalk.csv").read_text() == "part_num,ldraw_part_id\n3068b,3068b\n"


def test_fetch_ldraw_crosswalks_passes_the_api_token_through_to_fetch(tmp_path):
    ldraw_dir = tmp_path / "ldraw"
    (ldraw_dir / "parts").mkdir(parents=True)
    (ldraw_dir / "LDConfig.ldr").write_text(FAKE_LDCONFIG)

    received_tokens = []

    def fake_fetch(url: str, api_token: str | None) -> bytes:
        received_tokens.append(api_token)
        if url.endswith("colors.csv.gz"):
            return _fake_csv_bytes([], ["id", "name"])
        return _fake_csv_bytes([], ["part_num"])

    fetch_ldraw_crosswalks(ldraw_dir, tmp_path / "data", fetch=fake_fetch, api_token="secret-token")

    assert received_tokens == ["secret-token", "secret-token"]
