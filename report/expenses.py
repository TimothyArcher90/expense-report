"""Read expenses from a CSV file (date,description,amount,currency) and summarise them."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path


@dataclass(frozen=True)
class Expense:
    day: date
    description: str
    amount: Decimal
    currency: str


class ReportError(ValueError):
    """A row the report cannot use; the message names its line in the file."""


def parse_row(row: dict[str, str], line: int) -> Expense:
    try:
        day = date.fromisoformat(row["date"].strip())
        amount = Decimal(row["amount"].strip())
    except (KeyError, AttributeError, ValueError, InvalidOperation) as exc:
        raise ReportError(f"line {line}: cannot read date or amount ({exc})") from exc
    currency = (row.get("currency") or "").strip().upper()
    if len(currency) != 3 or not currency.isalpha():
        raise ReportError(f"line {line}: currency must be a 3-letter code, got {currency!r}")
    return Expense(day, (row.get("description") or "").strip(), amount, currency)


def read_expenses(path: Path) -> list[Expense]:
    with path.open(newline="", encoding="utf-8") as f:
        return [parse_row(row, n) for n, row in enumerate(csv.DictReader(f), start=2)]


def totals_by_month(expenses: list[Expense]) -> dict[str, dict[str, Decimal]]:
    """Suma por mes (YYYY-MM) y moneda, con meses y monedas ordenados."""
    sums: dict[tuple[str, str], Decimal] = {}
    for e in expenses:
        key = (e.day.strftime("%Y-%m"), e.currency)
        sums[key] = sums.get(key, Decimal(0)) + e.amount
    result: dict[str, dict[str, Decimal]] = {}
    for (month, currency), total in sorted(sums.items()):
        result.setdefault(month, {})[currency] = total
    return result


def format_by_month(expenses: list[Expense]) -> str:
    """Texto con un bloque por mes y una línea por moneda."""
    if not expenses:
        return "No expenses."
    blocks = []
    for month, currencies in totals_by_month(expenses).items():
        lines = [f"  {currency} {total}" for currency, total in currencies.items()]
        blocks.append("\n".join([month, *lines]))
    return "\n\n".join(blocks)


def summary(expenses: list[Expense]) -> str:
    if not expenses:
        return "No expenses."
    days = sorted(e.day for e in expenses)
    return f"{len(expenses)} expenses from {days[0].isoformat()} to {days[-1].isoformat()}"
