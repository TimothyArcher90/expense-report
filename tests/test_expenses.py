import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from report.expenses import Expense, ReportError, parse_row, read_expenses, summary

ROW = {"date": "2026-10-03", "description": "Taxi", "amount": "12.50", "currency": "usd"}


def write_file(text: str, suffix: str = ".csv") -> Path:
    f = tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return Path(f.name)


def write_xlsx(rows: list[list[str]]) -> Path:
    cell = '<c t="inlineStr"><is><t>{}</t></is></c>'
    cells = "".join("<row>" + "".join(cell.format(v) for v in r) + "</row>" for r in rows)
    path = write_file("", ".xlsx")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("xl/worksheets/sheet1.xml", f"<worksheet><sheetData>{cells}</sheetData></worksheet>")
    return path


HEAD = ["date", "description", "amount", "currency"]
ROWS = [["2026-10-03", "Taxi", "12.50", "USD"], ["2026-10-05", "Lunch", "9", "EUR"]]
TAXI = Expense(date(2026, 10, 3), "Taxi", Decimal("12.50"), "USD")
LUNCH = Expense(date(2026, 10, 5), "Lunch", Decimal("9"), "EUR")
JSON_TEXT = '[{"date":"2026-10-03","description":"Taxi","amount":12.50,"currency":"USD"},' + json.dumps(dict(zip(HEAD, ROWS[1]))) + "]"
XML_TEXT = "<r>" + "".join("<e>" + "".join(f"<{k}>{v}</{k}>" for k, v in zip(HEAD, r)) + "</e>" for r in ROWS) + "</r>"


class Formats(unittest.TestCase):
    def test_json(self) -> None:
        self.assertEqual(read_expenses(write_file(JSON_TEXT, ".JSON")), [TAXI, LUNCH])

    def test_xml(self) -> None:
        self.assertEqual(read_expenses(write_file(XML_TEXT, ".xml")), [TAXI, LUNCH])

    def test_xlsx(self) -> None:
        self.assertEqual(read_expenses(write_xlsx([HEAD, *ROWS])), [TAXI, LUNCH])

    def test_unsupported_extension(self) -> None:
        for suffix in (".txt", ".xls"):
            with self.assertRaisesRegex(ReportError, "unsupported"):
                read_expenses(write_file("x", suffix))

    def test_bad_amount_names_the_line(self) -> None:
        bad = [HEAD, ["2026-10-03", "Taxi", "x", "USD"]]
        for path in (write_file(json.dumps([dict(zip(*bad))]), ".json"), write_xlsx(bad)):
            with self.assertRaisesRegex(ReportError, "line 2"):
                read_expenses(path)

    def test_malformed_files(self) -> None:
        for text, suffix in (("[{", ".json"), ("<a>", ".xml"), ("not a zip", ".xlsx")):
            with self.assertRaises(ReportError):
                read_expenses(write_file(text, suffix))


class ParseRow(unittest.TestCase):
    def test_reads_a_row(self) -> None:
        self.assertEqual(parse_row(ROW, 2), Expense(date(2026, 10, 3), "Taxi", Decimal("12.50"), "USD"))

    def test_bad_date_names_the_line(self) -> None:
        with self.assertRaisesRegex(ReportError, "line 7"):
            parse_row({**ROW, "date": "03/10/2026"}, 7)

    def test_bad_amount(self) -> None:
        with self.assertRaises(ReportError):
            parse_row({**ROW, "amount": "twelve"}, 2)

    def test_bad_currency(self) -> None:
        with self.assertRaisesRegex(ReportError, "3-letter"):
            parse_row({**ROW, "currency": "dollars"}, 2)


class ReadAndSummarise(unittest.TestCase):
    def test_reads_a_file(self) -> None:
        path = write_file("date,description,amount,currency\n2026-10-03,Taxi,12.50,USD\n2026-10-05,Lunch,9,EUR\n")
        self.assertEqual([e.currency for e in read_expenses(path)], ["USD", "EUR"])

    def test_error_line_counts_the_header(self) -> None:
        path = write_file("date,description,amount,currency\n2026-10-03,Taxi,x,USD\n")
        with self.assertRaisesRegex(ReportError, "line 2"):
            read_expenses(path)

    def test_summary(self) -> None:
        expenses = [parse_row(ROW, 2), parse_row({**ROW, "date": "2026-09-30"}, 3)]
        self.assertEqual(summary(expenses), "2 expenses from 2026-09-30 to 2026-10-03")

    def test_summary_of_nothing(self) -> None:
        self.assertEqual(summary([]), "No expenses.")


class Cli(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "report", *args], capture_output=True, text=True)

    def test_prints_the_summary(self) -> None:
        out = self.run_cli("data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("expenses from", out.stdout)

    def test_reads_json(self) -> None:
        out = self.run_cli(str(write_file(JSON_TEXT, ".json")))
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("expenses from", out.stdout)

    def test_bad_file_exits_1(self) -> None:
        self.assertEqual(self.run_cli("missing.csv").returncode, 1)


if __name__ == "__main__":
    unittest.main()
