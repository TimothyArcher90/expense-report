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

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"


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


def read_csv(path: Path) -> list[Expense]:
    """Lee un CSV; el encabezado es la línea 1."""
    with path.open(newline="", encoding="utf-8") as f:
        return [parse_row(row, n) for n, row in enumerate(csv.DictReader(f), start=2)]


def read_json(path: Path) -> list[Expense]:
    """Lee una lista JSON de objetos con las claves del CSV."""
    try:
        items = json.loads(path.read_text(encoding="utf-8"))
        rows = [{k: str(v) for k, v in item.items()} for item in items]
    except (ValueError, AttributeError, TypeError) as exc:
        raise ReportError(f"cannot read json ({exc})") from exc
    return [parse_row(row, n) for n, row in enumerate(rows, start=1)]


def read_xml(path: Path) -> list[Expense]:
    """Lee un XML con elementos <expense> que tienen un subelemento por campo."""
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise ReportError(f"cannot read xml ({exc})") from exc
    rows = [{c.tag: c.text or "" for c in item} for item in root.iter("expense")]
    return [parse_row(row, n) for n, row in enumerate(rows, start=1)]


def cell_text(cell: ET.Element, shared: list[str]) -> str:
    """Devuelve el texto de una celda xlsx (compartida, inline o numérica)."""
    v, kind = cell.findtext(NS + "v", ""), cell.get("t")
    return "".join(cell.itertext()) if kind == "inlineStr" else shared[int(v)] if kind == "s" else v


def read_xlsx(path: Path) -> list[Expense]:
    """Lee la primera hoja de un xlsx; la fila 1 son los encabezados."""
    try:
        with zipfile.ZipFile(path) as z:
            sst = "xl/sharedStrings.xml"
            shared = ["".join(s.itertext()) for s in ET.fromstring(z.read(sst))] if sst in z.namelist() else []
            sheet = ET.fromstring(z.read("xl/worksheets/sheet1.xml"))
            table = [[cell_text(c, shared) for c in r] for r in sheet.iter(NS + "row")]
    except (zipfile.BadZipFile, KeyError, ET.ParseError, IndexError, ValueError) as exc:
        raise ReportError(f"cannot read xlsx ({exc})") from exc
    head, *body = table or [[]]
    return [parse_row(dict(zip(head, r)), n) for n, r in enumerate(body, start=2)]


READERS = {".csv": read_csv, ".json": read_json, ".xml": read_xml, ".xlsx": read_xlsx}


def read_expenses(path: Path) -> list[Expense]:
    reader = READERS.get(path.suffix.lower())
    if reader is None:
        raise ReportError(f"unsupported format {path.suffix!r}")
    return reader(path)


def summary(expenses: list[Expense]) -> str:
    if not expenses:
        return "No expenses."
    days = sorted(e.day for e in expenses)
    return f"{len(expenses)} expenses from {days[0].isoformat()} to {days[-1].isoformat()}"
