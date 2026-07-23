import csv
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path


def read_typed_csv(path: Path, types: Mapping[str, Callable[[str], object]]) -> list[dict]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        return [{col: cast(row[col]) for col, cast in types.items()} for row in reader]


def read_csv(path: Path) -> list[dict]:
    with path.open(newline="") as f:
        return list(csv.DictReader(f))


def write_csv(path: Path, fieldnames: Iterable[str], rows: Iterable[Mapping]) -> None:
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


def parse_int(value: str) -> int:
    return int(value)


def parse_optional_int(value: str) -> int | None:
    return int(value) if value.strip() else None


def parse_bool(value: str) -> bool:
    return value.strip().lower() == "true"


def parse_str(value: str) -> str:
    return value
