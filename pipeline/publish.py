import shutil
from pathlib import Path


def publish_to_docs(db_path: Path, docs_data_dir: Path) -> None:
    """Copy the reporting-layer SQLite DB to the Pages-served copy.

    Per docs/adr/0001-serve-pages-from-docs-on-main.md, GitHub Pages serves
    /docs on main — this is the "commit the updated data files" step from the
    weekly refresh (INITIAL_PROJECT_SPEC.md §5), run locally for now.
    """
    docs_data_dir.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(db_path, docs_data_dir / db_path.name)
