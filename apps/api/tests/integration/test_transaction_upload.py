import json
from io import BytesIO
from pathlib import Path

from httpx import AsyncClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

GOLDEN_CSV = Path("../../evaluation/datasets/phase2_golden.csv").read_bytes()


def _statement_pdf(*lines: str) -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject(
                {NameObject("/F1"): writer._add_object(font)}
            )
        }
    )
    operations = ["BT", "/F1 8 Tf", "40 750 Td"]
    for index, line in enumerate(lines):
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        if index:
            operations.append("0 -14 Td")
        operations.append(f"({escaped}) Tj")
    operations.append("ET")
    stream = DecodedStreamObject()
    stream.set_data("\n".join(operations).encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


async def _identity(client: AsyncClient, email: str, household: str) -> tuple[str, str]:
    registered = await client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "correct-horse-battery-staple",
            "household_name": household,
        },
    )
    token = registered.json()["access_token"]
    me = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    return token, me.json()["tenants"][0]["id"]


async def test_upload_is_idempotent_scoped_and_correctable(client: AsyncClient) -> None:
    token_a, tenant_a = await _identity(client, "csv-a@example.com", "CSV Alpha")
    token_b, tenant_b = await _identity(client, "csv-b@example.com", "CSV Beta")
    headers_a = {"Authorization": f"Bearer {token_a}", "X-Tenant-ID": tenant_a}
    headers_b = {"Authorization": f"Bearer {token_b}", "X-Tenant-ID": tenant_b}
    account_response = await client.post(
        "/api/v1/accounts",
        headers=headers_a,
        json={"name": "Current", "currency": "INR", "external_reference": "current"},
    )
    account_id = account_response.json()["id"]
    mapping = {
        "date": "Date",
        "date_format": "%d/%m/%Y",
        "debit": "Debit",
        "credit": "Credit",
        "merchant": "Merchant",
        "description": "Description",
        "transaction_id": "Transaction ID",
        "currency": "Currency",
        "balance": "Balance",
    }
    first = await client.post(
        f"/api/v1/accounts/{account_id}/transaction-uploads",
        headers=headers_a,
        data={"mapping": json.dumps(mapping)},
        files={"file": ("golden.csv", GOLDEN_CSV, "text/csv")},
    )
    assert first.status_code == 200, first.text
    assert first.json()["accepted_rows"] == 5
    assert first.json()["duplicate_rows"] == 1
    assert first.json()["rejected_rows"] == 1
    assert first.json()["source_format"] == "csv"
    assert first.json()["detected_content_type"] == "text/csv"
    assert not first.json()["replayed"]

    provenance = await client.get(
        f"/api/v1/transaction-uploads/{first.json()['id']}", headers=headers_a
    )
    assert provenance.status_code == 200
    assert provenance.json()["parser_name"] == "python-csv"

    replay = await client.post(
        f"/api/v1/accounts/{account_id}/transaction-uploads",
        headers=headers_a,
        data={"mapping": json.dumps(mapping)},
        files={"file": ("renamed.csv", GOLDEN_CSV, "text/csv")},
    )
    assert replay.status_code == 200
    assert replay.json()["id"] == first.json()["id"]
    assert replay.json()["replayed"]

    mismatched_replay = await client.post(
        f"/api/v1/accounts/{account_id}/transaction-uploads",
        headers=headers_a,
        data={"mapping": json.dumps(mapping)},
        files={"file": ("renamed.pdf", GOLDEN_CSV, "application/pdf")},
    )
    assert mismatched_replay.status_code == 422
    assert mismatched_replay.json()["detail"]["code"] == "FILE_TYPE_MISMATCH"

    page = await client.get("/api/v1/transactions", headers=headers_a)
    assert page.status_code == 200
    assert page.json()["total"] == 5
    transfer = next(item for item in page.json()["items"] if item["kind"] == "transfer")
    assert transfer["is_excluded_from_cashflow"]

    corrected = await client.patch(
        f"/api/v1/transactions/{page.json()['items'][0]['id']}/category",
        headers=headers_a,
        json={"category": "household_supplies", "reason": "User verified receipt"},
    )
    assert corrected.status_code == 200
    assert corrected.json()["classification_method"] == "human"

    cross_tenant = await client.post(
        f"/api/v1/accounts/{account_id}/transaction-uploads",
        headers=headers_b,
        data={"mapping": json.dumps(mapping)},
        files={"file": ("golden.csv", GOLDEN_CSV, "text/csv")},
    )
    assert cross_tenant.status_code == 404
    hidden_provenance = await client.get(
        f"/api/v1/transaction-uploads/{first.json()['id']}", headers=headers_b
    )
    assert hidden_provenance.status_code == 404


async def test_pdf_upload_is_validated_and_imported(client: AsyncClient) -> None:
    token, tenant = await _identity(client, "pdf@example.com", "PDF Household")
    headers = {"Authorization": f"Bearer {token}", "X-Tenant-ID": tenant}
    account = await client.post(
        "/api/v1/accounts",
        headers=headers,
        json={"name": "Current", "currency": "INR", "external_reference": "pdf-current"},
    )
    account_id = account.json()["id"]
    mapping = {
        "date": "Date",
        "date_format": "%d/%m/%Y",
        "debit": "Debit",
        "credit": "Credit",
        "merchant": "Merchant",
        "description": "Description",
        "transaction_id": "Transaction ID",
        "currency": "Currency",
        "balance": "Balance",
    }
    pdf = _statement_pdf(
        "Date,Debit,Credit,Merchant,Description,Transaction ID,Currency,Balance",
        "01/10/2026,,100000.00,ACME Payroll,October salary,pdf-001,INR,150000.00",
        "02/10/2026,30000.00,,Green Homes Rent,Monthly rent,pdf-002,INR,120000.00",
    )
    response = await client.post(
        f"/api/v1/accounts/{account_id}/transaction-uploads",
        headers=headers,
        data={"mapping": json.dumps(mapping)},
        files={"file": ("statement.pdf", pdf, "application/pdf")},
    )
    assert response.status_code == 200, response.text
    assert response.json()["source_format"] == "pdf"
    assert response.json()["detected_content_type"] == "application/pdf"
    assert response.json()["page_count"] == 1
    assert response.json()["accepted_rows"] == 2

    renamed = await client.post(
        f"/api/v1/accounts/{account_id}/transaction-uploads",
        headers=headers,
        data={"mapping": json.dumps(mapping)},
        files={"file": ("malware.pdf", GOLDEN_CSV, "application/pdf")},
    )
    assert renamed.status_code == 422
    assert renamed.json()["detail"]["code"] == "FILE_TYPE_MISMATCH"
