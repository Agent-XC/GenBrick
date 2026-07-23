"""Frontend integration tests: drive the real static site (site/) over real
HTTP with Playwright, against a fixture-built SQLite DB (see conftest.py's
site_url fixture). See docs/agents/frontend-testing.md for how this harness
works and what it can't catch.
"""

import pytest
from playwright.sync_api import Page, expect


@pytest.fixture
def console_errors(page: Page) -> list[str]:
    errors: list[str] = []
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    return errors


@pytest.mark.parametrize(
    "path",
    ["/index.html", "/collection.html", "/figurines.html", "/box.html?set_num=75192-1"],
)
def test_page_loads_without_console_errors(page: Page, site_url: str, console_errors: list[str], path: str):
    page.goto(f"{site_url}{path}")
    expect(page.locator(".loading")).to_have_count(0)

    assert console_errors == []


def test_home_page_lists_owned_boxes_newest_first_with_links_to_box_detail(page: Page, site_url: str):
    page.goto(f"{site_url}/index.html")

    boxes = page.locator("#owned-boxes .box")
    expect(boxes).to_have_count(2)

    # owned_boxes.date_acquired DESC — 75192-1 (2023-12-25) before 10281-1
    # (2022-06-01), even though 10281-1 sorts first alphabetically/by set_num.
    expect(boxes.nth(0)).to_contain_text("Millennium Falcon")
    expect(boxes.nth(1)).to_contain_text("Bonsai Tree")

    falcon_link = boxes.nth(0).locator("a.box-name")
    expect(falcon_link).to_have_attribute("href", "box.html?set_num=75192-1")

    falcon_link.click()
    expect(page.locator("#box-name")).to_have_text("Millennium Falcon")


def test_box_detail_page_shows_full_contents_and_official_link(page: Page, site_url: str):
    page.goto(f"{site_url}/box.html?set_num=75192-1")

    expect(page.locator("#box-name")).to_have_text("Millennium Falcon")
    expect(page.locator("#box-meta")).to_have_text("75192-1 · 2017")
    expect(page.locator("#box-official-link a")).to_have_text("Official page")
    expect(page.locator("#box-official-link a")).to_have_attribute(
        "href", "https://www.lego.com/en-us/product/75192"
    )

    minifigs = page.locator("#box-minifigs .minifig")
    expect(minifigs).to_have_count(2)
    expect(minifigs.filter(has_text="Han Solo")).to_contain_text("×1")
    expect(minifigs.filter(has_text="Luke Skywalker")).to_contain_text("×1")

    parts = page.locator("#box-parts tbody tr")
    expect(parts).to_have_count(2)
    # "4" alone would trivially match "Plate 2 x 4" too, so assert on the
    # quantity cell specifically rather than the row's full text.
    expect(parts.filter(has_text="Blue").locator("td").nth(2)).to_have_text("4")


def test_box_detail_page_reports_not_found_for_a_set_num_that_isnt_owned(page: Page, site_url: str):
    # 21331-1 exists in the catalog fixture but isn't in owned_sets.csv.
    page.goto(f"{site_url}/box.html?set_num=21331-1")

    expect(page.locator("#box-name")).to_have_text("Box not found")
    expect(page.locator("#box-meta")).to_contain_text("21331-1")


def test_box_detail_page_prompts_for_a_set_num_when_none_is_given(page: Page, site_url: str):
    page.goto(f"{site_url}/box.html")

    expect(page.locator("#box-name")).to_have_text("No set_num given")


def test_collection_page_lists_owned_brick_pool_summed_across_boxes(page: Page, site_url: str):
    page.goto(f"{site_url}/collection.html")

    rows = page.locator("#brick-pool tbody tr")
    expect(rows).to_have_count(3)

    # 3001/Black is owned by both 75192-1 (10) and 10281-1 (15) — the
    # Collection page pools them into one summed row, per Owned brick pool
    # semantics (issue #4), not two per-Box rows.
    black_brick = rows.filter(has_text="Black")
    expect(black_brick).to_contain_text("Brick 2 x 4")
    expect(black_brick).to_contain_text("25")


def test_figurines_page_lists_minifigs_summed_across_boxes(page: Page, site_url: str):
    page.goto(f"{site_url}/figurines.html")

    figurines = page.locator("#figurines .minifig")
    expect(figurines).to_have_count(2)

    # fig-000001 (Han Solo) is owned by both 75192-1 and 10281-1 — the
    # Figurines page sums across Boxes the same way the Collection page
    # sums parts, so this is 2, not two separate rows of 1.
    expect(figurines.filter(has_text="Han Solo")).to_contain_text("×2")
    expect(figurines.filter(has_text="Luke Skywalker")).to_contain_text("×1")
