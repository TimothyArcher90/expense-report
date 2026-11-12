import contextlib
import io
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from report.__main__ import main
from report.expenses import (
    Expense,
    ReportError,
    format_by_month,
    parse_row,
    read_expenses,
    summary,
    totals_by_month,
)

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


class Cli(unittest.TestCase):
    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "report", *args], capture_output=True, text=True)

    def test_prints_the_summary(self) -> None:
        out = self.run_cli("data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("expenses from", out.stdout)

    def test_bad_file_exits_1(self) -> None:
        self.assertEqual(self.run_cli("missing.csv").returncode, 1)


def exp(day: str, amount: str, currency: str = "USD") -> Expense:
    return parse_row({**ROW, "date": day, "amount": amount, "currency": currency}, 2)


class ByMonth(unittest.TestCase):
    def test_sums_with_decimal(self) -> None:
        totals = totals_by_month([exp("2026-01-01", "0.10"), exp("2026-01-09", "0.20")])
        self.assertEqual(totals, {"2026-01": {"USD": Decimal("0.30")}})

    def test_two_currencies_in_a_month(self) -> None:
        totals = totals_by_month([exp("2026-01-01", "5"), exp("2026-01-02", "7", "COP")])
        self.assertEqual(totals["2026-01"], {"COP": Decimal("7"), "USD": Decimal("5")})

    def test_months_chronological_across_years(self) -> None:
        totals = totals_by_month([exp("2026-01-01", "1"), exp("2025-12-31", "1"), exp("2025-03-01", "1")])
        self.assertEqual(list(totals), ["2025-03", "2025-12", "2026-01"])

    def test_currencies_alphabetical(self) -> None:
        totals = totals_by_month([exp("2026-01-01", "1"), exp("2026-01-02", "1", "COP"), exp("2026-01-03", "1", "EUR")])
        self.assertEqual(list(totals["2026-01"]), ["COP", "EUR", "USD"])

    def test_same_month_different_years_not_mixed(self) -> None:
        totals = totals_by_month([exp("2025-03-05", "1"), exp("2026-03-05", "2")])
        self.assertEqual(totals, {"2025-03": {"USD": Decimal("1")}, "2026-03": {"USD": Decimal("2")}})

    def test_format(self) -> None:
        text = format_by_month([exp("2026-02-01", "3"), exp("2026-01-01", "150000.00", "COP"), exp("2026-01-02", "42.50")])
        self.assertEqual(text, "2026-01\n  COP 150000.00\n  USD 42.50\n\n2026-02\n  USD 3")

    def test_format_empty(self) -> None:
        self.assertEqual(format_by_month([]), "No expenses.")


class ByMonthCli(unittest.TestCase):
    CSV = "date,description,amount,currency\n2026-01-03,A,1.50,USD\n2026-01-04,B,2,USD\n"

    def run_main(self, *args: str) -> tuple[int, str]:
        out = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
            code = main(list(args))
        return code, out.getvalue()

    def test_by_month_after_file(self) -> None:
        path = str(write_csv(self.CSV))
        self.assertEqual(self.run_main(path, "--by-month"), (0, "2026-01\n  USD 3.50\n"))

    def test_by_month_before_file(self) -> None:
        path = str(write_csv(self.CSV))
        self.assertEqual(self.run_main("--by-month", path), (0, "2026-01\n  USD 3.50\n"))

    def test_without_option_prints_summary(self) -> None:
        path = str(write_csv(self.CSV))
        self.assertEqual(self.run_main(path), (0, "2 expenses from 2026-01-03 to 2026-01-04\n"))

    def test_invalid_line_exits_1(self) -> None:
        path = str(write_csv("date,description,amount,currency\n2026-01-03,A,x,USD\n"))
        self.assertEqual(self.run_main(path, "--by-month"), (1, ""))

    def test_only_option_is_usage(self) -> None:
        self.assertEqual(self.run_main("--by-month"), (2, ""))


if __name__ == "__main__":
    unittest.main()
