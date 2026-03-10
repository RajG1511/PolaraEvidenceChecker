# scripts/test_document.py
# Quick manual test script — run from project root:
#   python scripts/test_document.py test_documents/sufficient/01_CC6.1_sufficient_access_control_policy.pdf CC6.1

import sys
import re
import requests
from pathlib import Path
from dotenv import load_dotenv
import os
import time

load_dotenv()

API_URL = "http://localhost:8000/api/v1/check"
API_KEY = os.environ.get("CHECKER_API_KEY", "")

# Toggle this:
# False -> normal single-file mode
# True  -> run every PDF in test_documents/sufficient and test_documents/insufficient
TEST_ALL = True

TEST_DOCUMENTS_DIR = Path(__file__).parent.parent / "test_documents"


def extract_control_id_from_filename(filename: str) -> str | None:
    match = re.search(r"(CC\d+\.\d+)", filename, re.IGNORECASE)
    if match:
        return match.group(1).upper()
    return None


def expected_verdict_from_path(path: Path) -> str | None:
    parent_name = path.parent.name.lower()
    if parent_name == "sufficient":
        return "SUFFICIENT"
    if parent_name == "insufficient":
        return "INSUFFICIENT"
    return None


def call_checker(file_path: Path, control_id: str) -> dict:
    start = time.time()

    with open(file_path, "rb") as f:
        response = requests.post(
            API_URL,
            headers={"X-API-Key": API_KEY},
            data={"control_id": control_id},
            files={"file": (file_path.name, f)},
            timeout=120,
        )

    elapsed = time.time() - start

    if response.status_code != 200:
        return {
            "ok": False,
            "status_code": response.status_code,
            "error_text": response.text,
            "elapsed": elapsed,
            "file": file_path,
            "control_id": control_id,
        }

    result = response.json()
    result["ok"] = True
    result["elapsed"] = elapsed
    result["file"] = file_path
    result["control_id"] = control_id
    return result


def print_single_result(result: dict) -> None:
    path = result["file"]
    control_id = result["control_id"]

    print(f"\nFile:       {path.name}")
    print(f"Control:    {control_id}")
    print("-" * 50)

    if not result["ok"]:
        print(f"Error {result['status_code']}: {result['error_text']}")
        return

    print(f"Verdict:    {result['verdict'].upper()}")
    print(f"Score:      {result['score']}")
    print(f"Adjudicated by LLM: {result.get('adjudicated', False)}")
    print(f"Time taken: {result['elapsed']:.2f}s")

    if result.get("llm_reasoning"):
        print(f"LLM Reasoning: {result['llm_reasoning']}")

    print(f"\nSub-scores:")
    print(f"  Semantic:    {result.get('semantic_score')}")
    print(f"  Keywords:    {result.get('keyword_score')}")
    print(f"  Specificity: {result.get('specificity_score')}")
    print(f"  Mismatch:    {result.get('mismatch_penalty')}")

    if result.get("missing_subcriteria"):
        print(f"\nMissing subcriteria:")
        for m in result["missing_subcriteria"]:
            print(f"  - {m}")

    if result.get("mismatch_reasons"):
        print(f"\nMismatch signals:")
        for r in result["mismatch_reasons"]:
            print(f"  - {r}")


def test_document(file_path: str, control_id: str) -> None:
    path = Path(file_path)

    if not path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    result = call_checker(path, control_id)
    print_single_result(result)

    if not result["ok"]:
        sys.exit(1)


def run_all_tests() -> None:
    sufficient_dir = TEST_DOCUMENTS_DIR / "sufficient"
    insufficient_dir = TEST_DOCUMENTS_DIR / "insufficient"

    all_files = []
    for folder in [sufficient_dir, insufficient_dir]:
        if folder.exists():
            all_files.extend(sorted(folder.glob("*.pdf")))

    if not all_files:
        print(f"No PDF files found under {TEST_DOCUMENTS_DIR}")
        sys.exit(1)

    failures = []
    llm_adjudicated = []
    errors = []
    passed = 0

    print(f"\nRunning {len(all_files)} test files...")
    print("=" * 80)

    for path in all_files:
        expected = expected_verdict_from_path(path)
        control_id = extract_control_id_from_filename(path.name)

        if expected is None:
            errors.append({
                "file": path.name,
                "reason": "Could not infer expected verdict from folder name."
            })
            print(f"[ERROR] {path.name} -> could not infer expected verdict")
            continue

        if control_id is None:
            errors.append({
                "file": path.name,
                "reason": "Could not extract control ID from filename."
            })
            print(f"[ERROR] {path.name} -> could not extract control ID")
            continue

        result = call_checker(path, control_id)

        if not result["ok"]:
            errors.append({
                "file": path.name,
                "reason": f"API error {result['status_code']}: {result['error_text']}"
            })
            print(f"[ERROR] {path.name} -> API error {result['status_code']}")
            continue

        actual = result["verdict"].upper()
        adjudicated = result.get("adjudicated", False)

        if adjudicated:
            llm_adjudicated.append({
                "file": path.name,
                "control_id": control_id,
                "expected": expected,
                "actual": actual,
                "score": result.get("score"),
                "elapsed": result["elapsed"],
            })

        if actual == expected:
            passed += 1
            print(
                f"[PASS] {path.name} | control={control_id} | "
                f"expected={expected} | got={actual} | "
                f"llm={adjudicated} | {result['elapsed']:.2f}s"
            )
        else:
            failures.append({
                "file": path.name,
                "control_id": control_id,
                "expected": expected,
                "actual": actual,
                "score": result.get("score"),
                "adjudicated": adjudicated,
                "elapsed": result["elapsed"],
                "missing_subcriteria": result.get("missing_subcriteria", []),
                "mismatch_reasons": result.get("mismatch_reasons", []),
                "llm_reasoning": result.get("llm_reasoning"),
            })
            print(
                f"[FAIL] {path.name} | control={control_id} | "
                f"expected={expected} | got={actual} | "
                f"llm={adjudicated} | {result['elapsed']:.2f}s"
            )

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total files:         {len(all_files)}")
    print(f"Passed:              {passed}")
    print(f"Failed:              {len(failures)}")
    print(f"Errors:              {len(errors)}")
    print(f"LLM adjudicated:     {len(llm_adjudicated)}")

    if llm_adjudicated:
        print("\nFiles adjudicated by LLM:")
        for item in llm_adjudicated:
            print(
                f"  - {item['file']} | control={item['control_id']} | "
                f"expected={item['expected']} | got={item['actual']} | "
                f"score={item['score']} | {item['elapsed']:.2f}s"
            )

    if failures:
        print("\nFailures:")
        for item in failures:
            print(
                f"  - {item['file']} | control={item['control_id']} | "
                f"expected={item['expected']} | got={item['actual']} | "
                f"score={item['score']} | llm={item['adjudicated']} | "
                f"{item['elapsed']:.2f}s"
            )

            if item["missing_subcriteria"]:
                print("    Missing subcriteria:")
                for sub in item["missing_subcriteria"]:
                    print(f"      - {sub}")

            if item["mismatch_reasons"]:
                print("    Mismatch reasons:")
                for reason in item["mismatch_reasons"]:
                    print(f"      - {reason}")

            if item["llm_reasoning"]:
                print(f"    LLM reasoning: {item['llm_reasoning']}")

    if errors:
        print("\nErrors:")
        for item in errors:
            print(f"  - {item['file']}: {item['reason']}")


if __name__ == "__main__":
    if TEST_ALL:
        run_all_tests()
    else:
        if len(sys.argv) != 3:
            print("Usage: python scripts/test_document.py <file_path> <control_id>")
            print("Example: python scripts/test_document.py test_documents/sufficient/01_CC6.1_sufficient_access_control_policy.pdf CC6.1")
            sys.exit(1)

        test_document(sys.argv[1], sys.argv[2])