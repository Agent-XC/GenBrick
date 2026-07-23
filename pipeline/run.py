from collections.abc import Callable
from pathlib import Path

from pipeline.intermediate import raw_to_intermediate
from pipeline.ldraw import render_with_ldview as _render_with_ldview
from pipeline.links import resolve_official_link as _resolve_official_link
from pipeline.omr import fetch_omr_model_bytes as _fetch_omr_model_bytes
from pipeline.primary import intermediate_to_primary
from pipeline.publish import publish_to_site
from pipeline.reporting import primary_to_reporting
from pipeline.scope import load_render_candidates, load_universe_scope


def run_pipeline(
    raw_dir: Path,
    owned_sets_path: Path,
    owned_box_photos_path: Path,
    ldraw_parts_crosswalk_path: Path,
    ldraw_colors_crosswalk_path: Path,
    ldraw_omr_crosswalk_path: Path,
    render_dir: Path,
    intermediate_dir: Path,
    primary_dir: Path,
    db_path: Path,
    resolve_official_link: Callable[[str], tuple[str, str]] = _resolve_official_link,
    render: Callable[[Path, Path], None] = _render_with_ldview,
    fetch_omr_model: Callable[[str], bytes] = _fetch_omr_model_bytes,
    universe_scope: str = "owned_themes",
    render_candidates: bool = False,
) -> None:
    raw_to_intermediate(raw_dir, intermediate_dir)
    intermediate_to_primary(
        intermediate_dir,
        owned_sets_path,
        owned_box_photos_path,
        ldraw_parts_crosswalk_path,
        ldraw_colors_crosswalk_path,
        ldraw_omr_crosswalk_path,
        render_dir,
        primary_dir,
        resolve_official_link=resolve_official_link,
        render=render,
        fetch_omr_model=fetch_omr_model,
        universe_scope=universe_scope,
        render_candidates=render_candidates,
    )
    primary_to_reporting(primary_dir, db_path)


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    db_path = repo_root / "data" / "08_reporting" / "lego.sqlite"
    run_pipeline(
        raw_dir=repo_root / "data" / "01_raw",
        owned_sets_path=repo_root / "data" / "owned_sets.txt",
        owned_box_photos_path=repo_root / "data" / "owned_box_photos.csv",
        ldraw_parts_crosswalk_path=repo_root / "data" / "ldraw_parts_crosswalk.csv",
        ldraw_colors_crosswalk_path=repo_root / "data" / "ldraw_colors_crosswalk.csv",
        ldraw_omr_crosswalk_path=repo_root / "data" / "ldraw_omr_crosswalk.csv",
        render_dir=repo_root / "site" / "assets" / "ldraw-renders",
        intermediate_dir=repo_root / "data" / "02_intermediate",
        primary_dir=repo_root / "data" / "03_primary",
        db_path=db_path,
        universe_scope=load_universe_scope(repo_root / "config" / "scope.json"),
        render_candidates=load_render_candidates(repo_root / "config" / "scope.json"),
    )
    publish_to_site(db_path, repo_root / "site" / "data")
