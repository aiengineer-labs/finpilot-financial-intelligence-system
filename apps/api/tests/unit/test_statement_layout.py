import pytest

from app.database.models import TransactionKind
from app.services.csv_ingestion import CSVColumnMapping, parse_csv
from app.services.statement_ingestion import (
    StatementKind,
    StatementValidationError,
    parse_statement,
)
from app.services.statement_layout import column_role, infer_date_format


def _ui_mapping() -> CSVColumnMapping:
    return CSVColumnMapping(
        date="Date",
        date_format="%d/%m/%Y",
        debit="Debit",
        credit="Credit",
        merchant="Merchant",
        description="Description",
        transaction_id="Transaction ID",
        currency="Currency",
        balance="Balance",
    )


def _parse(content: bytes, filename: str = "statement.csv"):  # type: ignore[no-untyped-def]
    return parse_statement(
        content, filename=filename, claimed_content_type="text/csv", mapping=_ui_mapping()
    )


def test_bank_export_with_preamble_and_split_columns_is_recognized() -> None:
    content = b"""Synthetic Bank Ltd
Account Statement for period 01/09/26 to 30/09/26
Account No,XXXXXXXX0001

Date,Narration,Chq./Ref.No.,Value Dt,Withdrawal Amt.,Deposit Amt.,Closing Balance
01/09/26,SALARY ACME PAYROLL,0000000000000000,01/09/26,0.00,"85,000.00","1,35,000.00"
03/09/26,UPI-GREEN HOMES RENT,0000000000000000,03/09/26,"30,000.00",0.00,"1,05,000.00"
,continued rent narration,,,,,
14/09/26,ATM WDL MG ROAD,0000000000000000,14/09/26,"2,000.00",,"1,03,000.00"
STATEMENT SUMMARY :-,,,,,,
"""
    result = _parse(content)

    assert result.statement_kind is StatementKind.DEPOSIT
    assert result.warnings == ["Recognized the statement columns automatically"]
    assert result.mapping.date_format == "%d/%m/%y"
    assert result.transactions.total_rows == 4
    rows = result.transactions.rows
    assert [row.amount_minor for row in rows] == [8_500_000, -3_000_000, -200_000]
    assert [row.balance_minor for row in rows] == [13_500_000, 10_500_000, 10_300_000]
    assert rows[1].description == "UPI-GREEN HOMES RENT continued rent narration"
    assert rows[0].transaction_date.isoformat() == "2026-09-01T00:00:00"
    # Evidence points at the original file line, not the canonical table row.
    assert result.source_evidence[rows[0].fingerprint] == {"format": "csv", "row": 6}
    assert len(result.transactions.errors) == 1


def test_card_export_signs_unmarked_charges_as_debits() -> None:
    content = """Synthetic Card Services
Credit Card Number,XXXX XXXX XXXX 0001
Transaction Date,Transaction Details,Amount (INR)
08-Jun-2025,UPI/Grocery Market,₹ 420.00
05-Jun-2025,Online Course LLP,"3,150.00"
11-Jun-2025,UPI PAYMENT RECEIVED,75.00 Cr
""".encode()
    result = _parse(content)

    assert result.statement_kind is StatementKind.CREDIT_CARD
    assert result.mapping.direction == "Direction"
    assert [row.amount_minor for row in result.transactions.rows] == [-42_000, -315_000, 7_500]
    assert all(row.balance_minor is None for row in result.transactions.rows)


def test_semicolon_export_with_direction_column_and_iso_dates() -> None:
    content = b"""Booking date;Description;Amount;Dr/Cr;Balance
2026-10-01;Payroll October;1.250,00;CR;5.000,00
"""
    # Decimal-comma locales are not silently reinterpreted: the row is rejected, not guessed.
    result = _parse(content)
    assert not result.transactions.rows
    assert result.transactions.errors

    content = b"""Booking date;Description;Amount;Dr/Cr;Balance
2026-10-01;Payroll October;1250.00;CR;5000.00
2026-10-02;Coffee Roasters;45.50;DR;4954.50
"""
    result = _parse(content)
    assert result.mapping.date_format == "%Y-%m-%d"
    assert [row.amount_minor for row in result.transactions.rows] == [125_000, -4_550]
    assert result.transactions.rows[0].kind is TransactionKind.INCOME


def test_channel_type_column_is_not_mistaken_for_direction() -> None:
    content = b"""Date,Description,Type,Amount
02/10/2026,Coffee Roasters,UPI,-45.50
03/10/2026,Refund from Store,NEFT,20.00
"""
    result = _parse(content)
    assert result.mapping.direction is None
    assert [row.amount_minor for row in result.transactions.rows] == [-4_550, 2_000]


def test_unrecognized_csv_fails_with_a_stable_code() -> None:
    with pytest.raises(StatementValidationError) as failure:
        _parse(b"colour,size\nred,large\n")
    assert failure.value.code == "INVALID_CSV"
    assert "No transaction table" in str(failure.value)


def test_day_first_is_preferred_and_reported_when_ambiguous() -> None:
    detected = infer_date_format(["01/02/2026", "03/04/2026"])
    assert detected == ("%d/%m/%Y", True)
    detected = infer_date_format(["01/02/2026", "03/14/2026"])
    assert detected == ("%m/%d/%Y", False)
    assert infer_date_format(["not a date", "also not"]) is None


def test_column_roles_cover_common_bank_labels() -> None:
    assert column_role("Withdrawal Amount (INR )") == ("debit", 0)
    assert column_role("Deposit Amt.") == ("credit", 0)
    assert column_role("Debit/Credit") == ("direction", 0)
    assert column_role("Closing Balance") == ("balance", 0)
    assert column_role("Value Dt") == ("date", 1)
    assert column_role("Txn Date") == ("date", 0)
    assert column_role("Particulars") == ("details", 0)
    assert column_role("Chq./Ref.No.") is None


def test_money_parser_accepts_currency_marks_and_suffixes() -> None:
    mapping = CSVColumnMapping(
        date="date", date_format="%Y-%m-%d", signed_amount="amount", merchant="merchant",
        balance="balance",
    )
    content = """date,amount,merchant,balance
2026-01-01,"₹ 1,234.50 Dr",Cafe,"Rs.10,000.00 Cr"
2026-01-02,INR 99.00,Refund,9 000.00 Dr
2026-01-03 10:42:11,(15.00),Kiosk,
2026-01-04,12abc,Broken,
""".encode()
    result = parse_csv(content, mapping)
    assert [row.amount_minor for row in result.rows] == [-123_450, 9_900, -1_500]
    assert [row.balance_minor for row in result.rows] == [1_000_000, -900_000, None]
    assert result.rows[2].transaction_date.isoformat() == "2026-01-03T00:00:00"
    assert [error.row for error in result.errors] == [5]


@pytest.mark.parametrize(
    ("header", "first_row", "second_row"),
    [
        (
            "S No.,Value Date,Transaction Date,Cheque Number,Transaction Remarks,"
            "Withdrawal Amount (INR ),Deposit Amount (INR ),Balance (INR )",
            '1,01/08/2026,01/08/2026,-,UPI/Grocer/merchantbank,170.00,0.00,"50,830.00"',
            '2,02/08/2026,02/08/2026,-,NEFT-SALARY ACME,0.00,"25,000.00","75,830.00"',
        ),
        (
            "Txn Date,Value Date,Description,Ref No./Cheque No.,Debit,Credit,Balance",
            '1 Aug 2026,1 Aug 2026,TO TRANSFER-UPI/Grocer,TRANSFER TO 0001, 170.00,,"50,830.00"',
            '2 Aug 2026,2 Aug 2026,BY TRANSFER-NEFT SALARY ACME,0002,," 25,000.00","75,830.00"',
        ),
        (
            "Tran Date,CHQNO,PARTICULARS,DR,CR,BAL,SOL",
            "01-08-2026,,UPI/P2M/Grocer,170.00,,50830.00,0001",
            "02-08-2026,,NEFT/SALARY ACME,,25000.00,75830.00,0001",
        ),
        (
            "Sl. No.,Transaction Date,Value Date,Description,Chq / Ref No.,Amount,Dr / Cr,"
            "Balance,Dr / Cr",
            "1,01-08-2026,01-08-2026,UPI/Grocer,UPI-0001,170.00,DR,50830.00,CR",
            "2,02-08-2026,02-08-2026,NEFT SALARY ACME,NEFT-0002,25000.00,CR,75830.00,CR",
        ),
    ],
    ids=["icici", "sbi", "axis", "kotak"],
)
def test_common_bank_csv_exports_are_recognized(
    header: str, first_row: str, second_row: str
) -> None:
    preamble = "Account statement\nAccount Number,XXXXXXXX0001\n\n"
    content = f"{preamble}{header}\n{first_row}\n{second_row}\n"
    result = _parse(content.encode())

    assert result.statement_kind is StatementKind.DEPOSIT
    rows = result.transactions.rows
    assert [row.amount_minor for row in rows] == [-17_000, 2_500_000]
    assert [row.balance_minor for row in rows] == [5_083_000, 7_583_000]
    assert [row.transaction_date.date().isoformat() for row in rows] == [
        "2026-08-01",
        "2026-08-02",
    ]
    assert not result.transactions.errors
