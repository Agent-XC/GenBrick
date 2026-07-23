from pathlib import Path

from pipeline.intermediate import raw_to_intermediate
from pipeline.primary import intermediate_to_primary
from pipeline.publish import publish_to_docs
from pipeline.reporting import primary_to_reporting


def run_pipeline(
    raw_dir: Path,
    owned_sets_path: Path,
    intermediate_dir: Path,
    primary_dir: Path,
    db_path: Path,
) -> None:
    raw_to_intermediate(raw_dir, intermediate_dir)
    intermediate_to_primary(intermediate_dir, owned_sets_path, primary_dir)
    primary_to_reporting(primary_dir, db_path)


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    db_path = repo_root / "data" / "08_reporting" / "lego.sqlite"
    run_pipeline(
        raw_dir=repo_root / "data" / "01_raw",
        owned_sets_path=repo_root / "data" / "owned_sets.txt",
        intermediate_dir=repo_root / "data" / "02_intermediate",
        primary_dir=repo_root / "data" / "03_primary",
        db_path=db_path,
    )
    publish_to_docs(db_path, repo_root / "docs" / "data")
