"""python3 -m report <file.csv|json|xlsx|xml>"""

from __future__ import annotations

import sys
from pathlib import Path

from report.expenses import ReportError, read_expenses, summary


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python3 -m report <file.csv|json|xlsx|xml>", file=sys.stderr)
        return 2
    try:
        expenses = read_expenses(Path(argv[0]))
    except (OSError, ReportError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(summary(expenses))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
