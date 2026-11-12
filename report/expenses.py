"""Read expenses from a CSV file (date,description,amount,currency) and summarise them."""

from __future__ import annotations

import csv
import json
import xml.etree.ElementTree as ET
import zipfile
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


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def read_json_rows(path: Path) -> list[dict[str, str]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"), parse_float=Decimal)
    except ValueError as exc:
        raise ReportError(f"invalid JSON ({exc})") from exc
    if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
        raise ReportError("JSON must be a list of objects")
    return [{k: str(v) for k, v in r.items()} for r in data]


def read_xml_rows(path: Path) -> list[dict[str, str]]:
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ReportError(f"invalid XML ({exc})") from exc
    return [{c.tag: (c.text or "") for c in item} for item in root]


def read_xlsx_rows(path: Path) -> list[dict[str, str]]:
    try:
        with zipfile.ZipFile(path) as z:
            shared = []
            if "xl/sharedStrings.xml" in z.namelist():
                si = ET.fromstring(z.read("xl/sharedStrings.xml")).findall("{*}si")
                shared = ["".join(s.itertext()) for s in si]
            sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
    except (zipfile.BadZipFile, KeyError, ET.ParseError) as exc:
        raise ReportError(f"invalid xlsx ({exc})") from exc
    rows = [[_cell(c, shared) for c in r.findall("{*}c")] for r in sheet.findall(".//{*}row")]
    return [dict(zip(rows[0], r)) for r in rows[1:]]


def _cell(cell: ET.Element, shared: list[str]) -> str:
    if cell.get("t") == "inlineStr":
        return "".join(cell.itertext())
    v = cell.findtext("{*}v") or ""
    return shared[int(v)] if cell.get("t") == "s" else v


READERS = {".csv": read_csv_rows, ".json": read_json_rows, ".xml": read_xml_rows, ".xlsx": read_xlsx_rows}


def read_expenses(path: Path) -> list[Expense]:
    """Lee gastos según la extensión del archivo."""
    reader = READERS.get(path.suffix.lower())
    if reader is None:
        raise ReportError(f"unsupported file format {path.suffix!r}")
    return [parse_row(row, n) for n, row in enumerate(reader(path), start=2)]


def summary(expenses: list[Expense]) -> str:
    if not expenses:
        return "No expenses."
    days = sorted(e.day for e in expenses)
    return f"{len(expenses)} expenses from {days[0].isoformat()} to {days[-1].isoformat()}"
