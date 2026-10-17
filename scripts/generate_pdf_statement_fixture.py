"""Generate the deterministic text-PDF counterpart to the Phase 2 golden CSV."""

from io import BytesIO
from pathlib import Path

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "evaluation" / "datasets" / "phase2_golden.csv"
DESTINATION = ROOT / "evaluation" / "datasets" / "phase2_golden.pdf"


def _pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def main() -> None:
    lines = SOURCE.read_text(encoding="utf-8").splitlines()
    writer = PdfWriter()
    writer.add_metadata(
        {
            "/Title": "FinPilot Phase 2 Golden Statement",
            "/Author": "FinPilot synthetic evaluation",
        }
    )
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Courier"),
        }
    )
    font_reference = writer._add_object(font)
    for page_start in range(0, len(lines), 45):
        page = writer.add_blank_page(width=842, height=595)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font_reference})}
        )
        operations = ["BT", "/F1 6 Tf", "24 560 Td"]
        for index, line in enumerate(lines[page_start : page_start + 45]):
            if index:
                operations.append("0 -12 Td")
            operations.append(f"({_pdf_text(line)}) Tj")
        operations.append("ET")
        stream = DecodedStreamObject()
        stream.set_data("\n".join(operations).encode())
        page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    DESTINATION.write_bytes(output.getvalue())


if __name__ == "__main__":
    main()
