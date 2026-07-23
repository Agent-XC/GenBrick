import sqlite3
from pathlib import Path

import pytest

from pipeline.run import run_pipeline

FIXTURE_RAW = Path(__file__).parent / "fixtures" / "raw"
FIXTURE_OWNED_SETS = Path(__file__).parent / "fixtures" / "owned_sets.csv"


def _run(tmp_path, owned_sets_path=FIXTURE_OWNED_SETS):
    db_path = tmp_path / "lego.sqlite"
    run_pipeline(
        raw_dir=FIXTURE_RAW,
        owned_sets_path=owned_sets_path,
        intermediate_dir=tmp_path / "02_intermediate",
        primary_dir=tmp_path / "03_primary",
        db_path=db_path,
    )
    return db_path


def test_owned_boxes_are_seeded_from_owned_sets_csv(tmp_path):
    conn = sqlite3.connect(_run(tmp_path))
    rows = conn.execute(
        "SELECT set_num, date_acquired, notes FROM owned_boxes ORDER BY set_num"
    ).fetchall()
    conn.close()

    assert rows == [
        ("10281-1", "2022-06-01", ""),
        ("75192-1", "2023-12-25", "Holiday gift"),
    ]


def test_sets_table_carries_every_catalog_set_with_a_constructed_official_link(tmp_path):
    conn = sqlite3.connect(_run(tmp_path))
    rows = conn.execute(
        "SELECT set_num, name, year, official_url, official_url_status FROM sets ORDER BY set_num"
    ).fetchall()
    conn.close()

    assert rows == [
        ("10281-1", "Bonsai Tree", 2021, "https://www.lego.com/en-us/product/10281", "unchecked"),
        ("21331-1", "Ship in a Bottle", 2022, "https://www.lego.com/en-us/product/21331", "unchecked"),
        ("75192-1", "Millennium Falcon", 2017, "https://www.lego.com/en-us/product/75192", "unchecked"),
    ]


def test_themes_table_is_carried_through(tmp_path):
    conn = sqlite3.connect(_run(tmp_path))
    rows = conn.execute("SELECT id, name, parent_id FROM themes ORDER BY id").fetchall()
    conn.close()

    assert rows == [(1, "Star Wars", None), (158, "Icons", None)]


def test_owned_sets_seed_referencing_an_unknown_set_num_is_rejected(tmp_path):
    bad_owned_sets = tmp_path / "owned_sets.csv"
    bad_owned_sets.write_text("set_num,date_acquired,notes\n99999-1,2024-01-01,\n")

    with pytest.raises(ValueError, match="99999-1"):
        _run(tmp_path, owned_sets_path=bad_owned_sets)
