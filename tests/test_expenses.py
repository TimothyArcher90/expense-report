import io
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


def write_csv(text: str) -> Path:
    f = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
    f.write(text)
    f.close()
    return Path(f.name)


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
        path = write_csv("date,description,amount,currency\n2026-10-03,Taxi,12.50,USD\n2026-10-05,Lunch,9,EUR\n")
        self.assertEqual([e.currency for e in read_expenses(path)], ["USD", "EUR"])

    def test_error_line_counts_the_header(self) -> None:
        path = write_csv("date,description,amount,currency\n2026-10-03,Taxi,x,USD\n")
        with self.assertRaisesRegex(ReportError, "line 2"):
            read_expenses(path)

    def test_summary(self) -> None:
        expenses = [parse_row(ROW, 2), parse_row({**ROW, "date": "2026-09-30"}, 3)]
        self.assertEqual(summary(expenses), "2 expenses from 2026-09-30 to 2026-10-03")

    def test_summary_of_nothing(self) -> None:
        self.assertEqual(summary([]), "No expenses.")


def write_file(suffix: str, data: bytes) -> Path:
    f = tempfile.NamedTemporaryFile("wb", suffix=suffix, delete=False)
    f.write(data)
    f.close()
    return Path(f.name)


def make_xlsx() -> bytes:
    ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
    ss = "".join(f"<si><t>{s}</t></si>" for s in ["date", "description", "amount", "currency", "2026-10-03", "Taxi", "usd"])
    s = lambda i: f'<c t="s"><v>{i}</v></c>'
    i = lambda t: f'<c t="inlineStr"><is><t>{t}</t></is></c>'
    rows = [s(0) + s(1) + s(2) + s(3), s(4) + s(5) + "<c><v>12.5</v></c>" + s(6), i("2026-10-05") + i("Lunch") + "<c><v>9</v></c>" + i("EUR")]
    sheet = "".join(f"<row>{r}</row>" for r in rows)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("xl/sharedStrings.xml", f"<sst {ns}>{ss}</sst>")
        z.writestr("xl/worksheets/sheet1.xml", f"<worksheet {ns}><sheetData>{sheet}</sheetData></worksheet>")
    return buf.getvalue()


JSON = b'[{"date":"2026-10-03","description":"Taxi","amount":12.5,"currency":"usd"},{"date":"2026-10-05","description":"Lunch","amount":"9","currency":"EUR"}]'
XML = b"<expenses><expense><date>2026-10-03</date><description>Taxi</description><amount>12.5</amount><currency>usd</currency></expense><expense><date>2026-10-05</date><description>Lunch</description><amount>9</amount><currency>EUR</currency></expense></expenses>"
CSV = b"date,description,amount,currency\n2026-10-03,Taxi,12.5,usd\n2026-10-05,Lunch,9,EUR\n"


class Formats(unittest.TestCase):
    def test_all_formats_give_equal_lists(self) -> None:
        want = [Expense(date(2026, 10, 3), "Taxi", Decimal("12.5"), "USD"), Expense(date(2026, 10, 5), "Lunch", Decimal("9"), "EUR")]
        for suffix, data in [(".csv", CSV), (".json", JSON), (".xml", XML), (".xlsx", make_xlsx()), (".JSON", JSON)]:
            with self.subTest(suffix=suffix):
                self.assertEqual(read_expenses(write_file(suffix, data)), want)

    def test_unsupported_extension(self) -> None:
        with self.assertRaisesRegex(ReportError, "unsupported"):
            read_expenses(write_file(".txt", b"x"))

    def test_data_error_names_the_line(self) -> None:
        with self.assertRaisesRegex(ReportError, "line 2"):
            read_expenses(write_file(".json", JSON.replace(b"2026-10-05", b"nope")))

    def test_broken_files_raise_report_error(self) -> None:
        cases = [(".json", b""), (".json", b"[{"), (".json", b'{"a": 1}'), (".xml", b""), (".xml", b"<a>"),
                 (".xml", b"<r><expense/></r>"), (".xlsx", b""), (".xlsx", b"not a zip")]
        for suffix, data in cases:
            with self.subTest(suffix=suffix, data=data), self.assertRaises(ReportError):
                read_expenses(write_file(suffix, data))


class Cli(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "report", *args], capture_output=True, text=True)

    def test_prints_the_summary(self) -> None:
        out = self.run_cli("data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("expenses from", out.stdout)

    def test_bad_file_exits_1(self) -> None:
        self.assertEqual(self.run_cli("missing.csv").returncode, 1)

    def test_json_and_txt(self) -> None:
        out, bad = self.run_cli(str(write_file(".json", JSON))), self.run_cli(str(write_file(".txt", b"x")))
        self.assertIn("expenses from", out.stdout)
        self.assertEqual((out.returncode, bad.returncode, "Traceback" in bad.stderr), (0, 1, False))


if __name__ == "__main__":
    unittest.main()
