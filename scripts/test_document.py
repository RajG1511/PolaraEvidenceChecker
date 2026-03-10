# scripts/test_document.py
# Quick manual test script — run from project root:
#   python scripts/test_document.py test_documents/sufficient/cc6_1_okta_access_policy.pdf CC6.1

import sys
import json
import requests
from pathlib import Path
from dotenv import load_dotenv
import os
import time

load_dotenv()

API_URL     = "http://localhost:8000/api/v1/check"
API_KEY     = os.environ.get("CHECKER_API_KEY", "")

# =============================================================================
# TEST COMMANDS — run from project root with uvicorn running on port 8000
# Usage: python scripts/test_document.py <file_path> <control_id>
#
# SUFFICIENT (expect verdict: SUFFICIENT)
# python scripts/test_document.py "test_documents/sufficient/01_CC6.1_sufficient_access_control_policy.pdf" CC6.1
# python scripts/test_document.py "test_documents/sufficient/03_CC6.2_sufficient_okta_mfa_report.pdf" CC6.2
# python scripts/test_document.py "test_documents/sufficient/05_CC7.3_sufficient_incident_response_plan.pdf" CC7.3
# python scripts/test_document.py "test_documents/sufficient/07_CC8.1_sufficient_branch_protection_and_ci.pdf" CC8.1
# python scripts/test_document.py "test_documents/sufficient/09_CC6.8_sufficient_snyk_vuln_dashboard.pdf" CC6.8
#
# INSUFFICIENT (expect verdict: INSUFFICIENT)
# python scripts/test_document.py "test_documents/insufficient/02_CC6.1_insufficient_vague_handbook_excerpt.pdf" CC6.1
# python scripts/test_document.py "test_documents/insufficient/04_CC6.2_insufficient_email_requesting_mfa.pdf" CC6.2
# python scripts/test_document.py "test_documents/insufficient/06_CC7.3_insufficient_jira_incidents_board.pdf" CC7.3
# python scripts/test_document.py "test_documents/insufficient/08_CC8.1_insufficient_commit_log_only.pdf" CC8.1
# python scripts/test_document.py "test_documents/insufficient/10_CC6.8_insufficient_requirements_txt_only.pdf" CC6.8
# python scripts/test_document.py "test_documents/insufficient/11_CC1.4_insufficient_pto_policy.pdf" CC1.4
# python scripts/test_document.py "test_documents/insufficient/12_CC6.7_insufficient_encryption_at_rest_policy.pdf" CC6.7
#
# NOTES:
#   - CC1.4 has no sufficient counterpart in this set
#   - CC6.7 has no sufficient counterpart in this set
#   - 12_CC6.7 is a good mismatch test — at-rest encryption uploaded for in-transit control
# =============================================================================

def test_document(file_path: str, control_id: str) -> None:
    path = Path(file_path)

    if not path.exists():
        print(f"File not found: {file_path}")
        sys.exit(1)

    print(f"\nFile:       {path.name}")
    print(f"Control:    {control_id}")
    print("-" * 50)

    start = time.time()
    with open(path, "rb") as f:
        response = requests.post(
            API_URL,
            headers={"X-API-Key": API_KEY},
            data={"control_id": control_id},
            files={"file": (path.name, f)},
        )

    elapsed = time.time() - start

    if response.status_code != 200:
        print(f"Error {response.status_code}: {response.text}")
        sys.exit(1)

    result = response.json()

    # Print a clean summary
    print(f"Verdict:    {result['verdict'].upper()}")
    print(f"Score:      {result['score']}")
    print(f"Adjudicated by LLM: {result['adjudicated']}")
    print(f"Time taken: {elapsed:.2f}s")

    if result.get("llm_reasoning"):
        print(f"LLM Reasoning: {result['llm_reasoning']}")

    print(f"\nSub-scores:")
    print(f"  Semantic:    {result['semantic_score']}")
    print(f"  Keywords:    {result['keyword_score']}")
    print(f"  Specificity: {result['specificity_score']}")
    print(f"  Mismatch:    {result['mismatch_penalty']}")
    

    if result["missing_subcriteria"]:
        print(f"\nMissing subcriteria:")
        for m in result["missing_subcriteria"]:
            print(f"  - {m}")

    if result["mismatch_reasons"]:
        print(f"\nMismatch signals:")
        for r in result["mismatch_reasons"]:
            print(f"  - {r}")

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python scripts/test_document.py <file_path> <control_id>")
        print("Example: python scripts/test_document.py test_documents/sufficient/cc6_1_okta.pdf CC6.1")
        sys.exit(1)

    test_document(sys.argv[1], sys.argv[2])