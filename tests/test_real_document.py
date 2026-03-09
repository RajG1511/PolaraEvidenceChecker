# tests/test_real_document.py

from pathlib import Path
from polara_checker.extraction import extract_text

def test_extract_evidence_quality_checker_doc():
    # The file sitting in your project root
    doc_path = Path(__file__).parent.parent / "PLR-EXP-001 Evidence Quality Checker.docx"

    assert doc_path.exists(), f"Document not found at {doc_path}"

    result = extract_text(doc_path)

    # Basic sanity checks
    assert len(result) > 500, "Expected substantial content from this document"
    assert "SOC 2" in result or "soc 2" in result.lower(), "Expected SOC 2 mentions"
    assert "CC6" in result or "CC7" in result or "CC8" in result, "Expected control IDs"

    # Print a preview so you can visually inspect the output
    print("\n--- First 1000 characters of extracted text ---")
    print(result[:1000])
    print("\n--- Last 500 characters ---")
    print(result[-500:])
    print(f"\n--- Total length: {len(result)} characters ---")