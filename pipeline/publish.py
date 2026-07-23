import shutil
from pathlib import Path


def publish_to_site(db_path: Path, site_data_dir: Path) -> None:
    """Copy the reporting-layer SQLite DB to the Pages-served copy.

    Per docs/adr/0002-serve-pages-from-a-github-actions-artifact.md, GitHub
    Pages deploys the site/ directory as a build artifact — this is the
    "commit the updated data files" step from the weekly refresh
    (INITIAL_PROJECT_SPEC.md §5), run locally for now.
    """
    site_data_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(db_path, site_data_dir / db_path.name)
