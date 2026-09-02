"""Generate the README yardstick methodology table from the live registry."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

README_PATH = Path(__file__).resolve().parents[1] / "README.md"
sys.path.insert(0, str(README_PATH.parent))

from data.yardsticks import methodology_frame  # noqa: E402


START_MARKER = "<!-- YARDSTICK_TABLE_START -->"
END_MARKER = "<!-- YARDSTICK_TABLE_END -->"


def markdown_table() -> str:
    frame = methodology_frame()
    columns = list(frame.columns)

    def cell(value: object) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")

    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    lines.extend(
        "| " + " | ".join(cell(value) for value in row) + " |"
        for row in frame.itertuples(index=False, name=None)
    )
    return "\n".join(lines)


def write_readme(table: str) -> None:
    readme = README_PATH.read_text(encoding="utf-8")
    if START_MARKER not in readme or END_MARKER not in readme:
        raise RuntimeError("README yardstick table markers are missing")
    before, remainder = readme.split(START_MARKER, 1)
    _, after = remainder.split(END_MARKER, 1)
    updated = f"{before}{START_MARKER}\n{table}\n{END_MARKER}{after}"
    README_PATH.write_text(updated, encoding="utf-8")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--write", action="store_true",
        help="replace the marked table in README.md as well as printing it",
    )
    args = parser.parse_args()
    table = markdown_table()
    if args.write:
        write_readme(table)
    print(table)


if __name__ == "__main__":
    main()
