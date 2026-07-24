"""Frontend integration tests: drive the real static site (site/) over real
HTTP with Playwright, against a fixture-built SQLite DB (see conftest.py's
site_url fixture). See docs/agents/frontend-testing.md for how this harness
works and what it can't catch.
"""

import re

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
    [
        "/index.html",
        "/collection.html",
        "/figurines.html",
        "/discover.html",
        "/similarity.html",
        "/themes.html",
        "/box.html?set_num=75192-1",
    ],
)
def test_page_loads_without_console_errors(page: Page, site_url: str, console_errors: list[str], path: str):
    page.goto(f"{site_url}{path}")
    expect(page.locator(".loading")).to_have_count(0)

    assert console_errors == []


def test_home_page_lists_owned_boxes_by_set_num_with_links_to_box_detail(page: Page, site_url: str):
    page.goto(f"{site_url}/index.html")

    boxes = page.locator("#owned-boxes .box")
    expect(boxes).to_have_count(2)

    # sets.set_num ASC — 10281-1 (Bonsai Tree) before 75192-1 (Millennium
    # Falcon), independent of date_acquired (which is blank for the real
    # collection today — see issue #15).
    expect(boxes.nth(0)).to_contain_text("Bonsai Tree")
    expect(boxes.nth(1)).to_contain_text("Millennium Falcon")

    # set_num shown as a visible column (issue #15) — a cheap, always-available
    # proxy for the official link, independent of official_url_status.
    expect(boxes.nth(0).locator(".box-set-num")).to_have_text("10281-1")
    expect(boxes.nth(1).locator(".box-set-num")).to_have_text("75192-1")

    falcon_link = boxes.nth(1).locator("a.box-name")
    expect(falcon_link).to_have_attribute("href", "box.html?set_num=75192-1")

    # 75192-1 has an uploaded photo (see tests/fixtures/owned_box_photos.csv);
    # 10281-1 doesn't, so it falls through to its LDraw procedural render
    # instead of the no-photo placeholder (see test_pipeline.py's
    # test_set_renders_falls_through_to_ldraw_procedural_for_an_owned_box_without_a_photo).
    expect(boxes.nth(1).locator("img.box-photo")).to_have_attribute(
        "src", "assets/owned-photos/75192-1/falcon.jpg"
    )
    expect(boxes.nth(0).locator("img.box-photo")).to_have_attribute(
        "src", re.compile(r"^assets/ldraw-renders/10281-1/")
    )
    expect(boxes.nth(0).locator(".box-photo-placeholder")).to_have_count(0)

    falcon_link.click()
    expect(page.locator("#box-name")).to_have_text("Millennium Falcon")


def test_box_detail_page_shows_full_contents_and_official_link(page: Page, site_url: str):
    page.goto(f"{site_url}/box.html?set_num=75192-1")

    expect(page.locator("#box-name")).to_have_text("Millennium Falcon")
    expect(page.locator("#box-meta")).to_have_text("75192-1 · 2017")
    expect(page.locator("#box-photo img.box-detail-photo")).to_have_attribute(
        "src", "assets/owned-photos/75192-1/falcon.jpg"
    )
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


def test_box_detail_page_shows_the_procedural_render_and_its_coverage_when_no_photo_is_uploaded(
    page: Page, site_url: str
):
    # 10281-1 is owned but has no row in tests/fixtures/owned_box_photos.csv,
    # so it falls through to set_renders.image_source 'ldraw_procedural' (see
    # test_set_renders_falls_through_to_ldraw_procedural_for_an_owned_box_without_a_photo
    # in test_pipeline.py for the exact 37.5% render_coverage_pct math).
    page.goto(f"{site_url}/box.html?set_num=10281-1")

    expect(page.locator("#box-photo img.box-detail-photo")).to_have_attribute(
        "src", re.compile(r"^assets/ldraw-renders/10281-1/")
    )
    expect(page.locator("#box-photo-caption .render-caption")).to_have_text(
        "Procedural LDraw render — 37.5% of parts resolved"
    )


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

    # tests/fixtures/ldraw_parts_crosswalk.csv maps 3001 -> ldraw_part_id
    # "3001" (issue #15: parts.ldraw_part_id is in the schema but wasn't
    # displayed on this page).
    expect(black_brick.locator("td").nth(1)).to_have_text("3001")


def test_discover_page_ranks_candidate_sets_by_buildability_with_a_link_to_its_official_page(
    page: Page, site_url: str
):
    page.goto(f"{site_url}/discover.html")

    # Under the default owned_themes scope, 21331-1 (Ship in a Bottle) is the
    # only Candidate — it shares 10281-1's theme but isn't itself owned.
    candidates = page.locator("#discover-list .box")
    expect(candidates).to_have_count(1)
    expect(candidates.nth(0)).to_contain_text("Ship in a Bottle")
    expect(candidates.nth(0)).to_contain_text("45.0%")
    expect(candidates.nth(0).locator(".box-set-num")).to_have_text("21331-1")

    official_link = candidates.nth(0).locator("a.box-link")
    expect(official_link).to_have_attribute("href", "https://www.lego.com/en-us/product/21331")


def test_similarity_page_ranks_each_sets_matches_independent_of_ownership(page: Page, site_url: str):
    page.goto(f"{site_url}/similarity.html")

    # Under the default owned_themes scope the materialized universe is
    # 75192-1, 10281-1 (both owned) and 21331-1 (a Candidate, not owned) —
    # Similarity gets a row for all three alike, unlike Discover/Buildability
    # which only ranks Candidates.
    rows = page.locator("#similarity-list .similarity-set")
    expect(rows).to_have_count(3)

    # Filtered on .box-name specifically, not the row's full text — "Millennium
    # Falcon" also appears inside 10281-1's and 21331-1's own matches lists.
    falcon_row = rows.filter(has=page.locator(".box-name", has_text="Millennium Falcon"))

    # set_num shown as a visible column on the anchor and each match (issue #15).
    expect(falcon_row.locator(".box-set-num").first).to_have_text("75192-1")

    falcon_matches = falcon_row.locator(".similarity-matches li")
    expect(falcon_matches).to_have_count(2)
    # 75192-1 vs 21331-1: min(4,10)+min(10,5)+min(0,5) = 9, over max(10,5)+
    # max(4,10)+max(0,5) = 25 -> 36.0%, the closer match than 10281-1's 22.7%.
    expect(falcon_matches.nth(0)).to_contain_text("Ship in a Bottle")
    expect(falcon_matches.nth(0)).to_contain_text("36.0%")
    expect(falcon_matches.nth(0).locator(".box-set-num")).to_have_text("21331-1")
    expect(falcon_matches.nth(1)).to_contain_text("Bonsai Tree")
    expect(falcon_matches.nth(1)).to_contain_text("22.7%")
    expect(falcon_matches.nth(1).locator(".box-set-num")).to_have_text("10281-1")


def test_similarity_scope_is_independent_of_the_buildability_floor(page: Page, site_url_with_floors: str):
    """Regression for issue #15: Similarity only has its own part-count and
    score floors, not Buildability's coverage_pct floor. With
    min_buildability_coverage_pct=50 (see conftest.py's site_url_with_floors),
    21331-1's 45% coverage drops it out of buildability.csv entirely — so it
    must not disappear from Similarity too, since it still clears
    min_candidate_num_parts (962) and has a ~36% score against 75192-1,
    above min_similarity_score_pct=30.
    """
    page.goto(f"{site_url_with_floors}/discover.html")
    expect(page.locator("#discover-list .box")).to_have_count(0)

    page.goto(f"{site_url_with_floors}/similarity.html")
    rows = page.locator("#similarity-list .similarity-set")
    # 10281-1 (Bonsai Tree) clears neither pairing's score under
    # min_similarity_score_pct=30 (its only two possible matches, 22.7% vs
    # Falcon and its own score vs Ship, both fall below the floor) — it has
    # zero qualifying matches left, so its row is hidden entirely rather than
    # rendered with just the "No similar Sets yet." empty state (issue #15).
    expect(rows).to_have_count(2)
    expect(rows.filter(has=page.locator(".box-name", has_text="Bonsai Tree"))).to_have_count(0)

    ship_row = rows.filter(has=page.locator(".box-name", has_text="Ship in a Bottle"))
    expect(ship_row).to_have_count(1)

    falcon_row = rows.filter(has=page.locator(".box-name", has_text="Millennium Falcon"))
    falcon_matches = falcon_row.locator(".similarity-matches li")
    # Only the ~36% match to Ship in a Bottle clears the 30% score floor —
    # the ~22.7% match to Bonsai Tree (see the unfiltered similarity test
    # above) is dropped.
    expect(falcon_matches).to_have_count(1)
    expect(falcon_matches.nth(0)).to_contain_text("Ship in a Bottle")


def test_themes_page_groups_owned_and_candidate_sets_by_theme(page: Page, site_url: str):
    page.goto(f"{site_url}/themes.html")

    # Under the default owned_themes scope: 75192-1 (Star Wars, owned) and
    # 10281-1 (Icons, owned) plus 21331-1 (Icons, Candidate) are in the
    # universe; 42100-1 (Technic) has no owned Box in its theme, so its
    # theme doesn't appear at all (mirrors test_scope.py's exclusion case).
    groups = page.locator("#themes-list .theme-group")
    expect(groups).to_have_count(2)
    expect(page.locator("#themes-list")).not_to_contain_text("Technic")

    star_wars = groups.filter(has=page.locator(".theme-name", has_text="Star Wars"))
    star_wars_sets = star_wars.locator(".box")
    expect(star_wars_sets).to_have_count(1)
    expect(star_wars_sets.nth(0)).to_contain_text("Millennium Falcon")
    expect(star_wars_sets.nth(0).locator(".box-owned-badge")).to_have_text("Owned")
    expect(star_wars_sets.nth(0).locator(".box-set-num")).to_have_text("75192-1")
    falcon_link = star_wars_sets.nth(0).locator("a.box-name")
    expect(falcon_link).to_have_attribute("href", "box.html?set_num=75192-1")

    icons = groups.filter(has=page.locator(".theme-name", has_text="Icons"))
    icons_sets = icons.locator(".box")
    expect(icons_sets).to_have_count(2)

    bonsai = icons_sets.filter(has_text="Bonsai Tree")
    expect(bonsai.locator(".box-owned-badge")).to_have_text("Owned")

    # 21331-1 is a Candidate, not owned — shown with its Buildability score
    # and no link to box.html (box.html 404s for non-owned set_nums).
    ship = icons_sets.filter(has_text="Ship in a Bottle")
    expect(ship.locator(".buildability-score")).to_contain_text("45.0%")
    expect(ship.locator("a.box-name")).to_have_count(0)
    expect(ship.locator(".box-set-num")).to_have_text("21331-1")


def test_figurines_page_lists_minifigs_summed_across_boxes(page: Page, site_url: str):
    page.goto(f"{site_url}/figurines.html")

    figurines = page.locator("#figurines .minifig")
    expect(figurines).to_have_count(2)

    # fig-000001 (Han Solo) is owned by both 75192-1 and 10281-1 — the
    # Figurines page sums across Boxes the same way the Collection page
    # sums parts, so this is 2, not two separate rows of 1.
    expect(figurines.filter(has_text="Han Solo")).to_contain_text("×2")
    expect(figurines.filter(has_text="Luke Skywalker")).to_contain_text("×1")
