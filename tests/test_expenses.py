import subprocess
import sys
import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path

from report.expenses import Expense, ReportError, currency_totals, parse_row, read_expenses, summary

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


def exp(amount: str, cur: str) -> Expense:
    return parse_row({**ROW, "amount": amount, "currency": cur}, 2)


class CurrencyTotals(unittest.TestCase):
    def test_sums_per_currency_with_two_decimals(self) -> None:
        self.assertEqual(currency_totals([exp("4.20", "eur"), exp("6.80", "eur")]), ["EUR 11.00"])

    def test_sorted_by_code(self) -> None:
        lines = currency_totals([exp("1", "usd"), exp("2", "eur"), exp("3", "gbp")])
        self.assertEqual(lines, ["EUR 2.00", "GBP 3.00", "USD 1.00"])

    def test_no_mixing(self) -> None:
        self.assertEqual(len(currency_totals([exp("1", "usd"), exp("1", "eur")])), 2)

    def test_decimal_exact(self) -> None:
        self.assertEqual(currency_totals([exp("0.10", "eur"), exp("0.20", "eur")]), ["EUR 0.30"])

    def test_empty(self) -> None:
        self.assertEqual(currency_totals([]), [])


class Cli(unittest.TestCase):
    def test_prints_currency_totals_after_summary(self) -> None:
        path = write_csv(
            "date,description,amount,currency\n"
            "2026-10-01,A,4.20,EUR\n2026-10-02,B,6.80,EUR\n"
            "2026-10-03,C,38.50,EUR\n2026-10-04,D,92.40,EUR\n"
            "2026-10-05,E,210.00,GBP\n2026-10-06,F,485.00,USD\n"
        )
        out = self.run_cli(str(path))
        lines = out.stdout.splitlines()
        self.assertIn("expenses from", lines[0])
        self.assertEqual(lines[1:], ["EUR 141.90", "GBP 210.00", "USD 485.00"])

    def run_cli(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, "-m", "report", *args], capture_output=True, text=True)

    def test_prints_the_summary(self) -> None:
        out = self.run_cli("data/sample.csv")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("expenses from", out.stdout)

    def test_bad_file_exits_1(self) -> None:
        self.assertEqual(self.run_cli("missing.csv").returncode, 1)


if __name__ == "__main__":
    unittest.main()
