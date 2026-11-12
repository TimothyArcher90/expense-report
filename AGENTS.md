# Expense report

A small command-line report over a CSV of expenses: `python3 -m report data/sample.csv`.
Standard library only.

## Commands
- Test: the TEST_CMD in factory.conf (must pass before any PR). There is no linter.

## Conventions
- Python 3.10+. Nothing outside the standard library is installed.
- Money is `Decimal`, never float. Dates are `datetime.date`.
- Every behaviour change gets a unittest in `tests/`, written BEFORE the implementation.
- Keep functions under 30 lines. Parsing lives in `report/expenses.py`, printing in `report/__main__.py`.
- Bad input raises `ReportError` naming the line; the CLI prints it and exits 1.

## Factory rules
- Phase state lives in `.factory/` as markdown files. Never put plan or review text in code comments.
- Only the paths in SCOPE (factory.conf) may change. Do not touch factory.sh, lib/, gates/, .claude/, data/ or this file.

## Estilo (regla de David)
- Docstrings y comentarios en español, una línea cada uno; los nombres de funciones y variables siguen en inglés.
