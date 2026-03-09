"""
Quick sanity check for Phase 3 scoring.
Run from project root: python tests/sanity_check_phase3.py
"""

import json
from pathlib import Path
from polara_checker.scorer import scoreDocument

def load_control(control_id: str) -> dict:
    path = Path("controls") / f"{control_id}.json"
    with path.open() as f:
        return json.load(f)

# ── Test 1: Good CC6.7 document should score well ────────────────────────
print("\n── Test 1: Good transit-encryption doc vs CC6.7 ──")
ctrl = load_control("CC6.7")
good_doc = """
SSL Labs scan shows A+ rating. All endpoints enforce TLS 1.3.
Certificates auto-renewed via Let's Encrypt every 90 days.
HSTS enabled with max-age=31536000. Load balancer rejects TLS 1.0 and 1.1.
Internal APIs require mutual TLS authentication with client certificates.
"""
result = scoreDocument(good_doc, ctrl)
print(f"  Final score:      {result['score']}")
print(f"  Semantic:         {result['semantic_score']}")
print(f"  Keywords:         {result['keyword_score']}  matched={result['matched_keywords']}")
print(f"  Specificity:      {result['specificity_score']}")
print(f"  Mismatch penalty: {result['mismatch_penalty']}")
print(f"  Missing:          {result['missing_subcriteria']}")

# ── Test 2: Wrong doc (at-rest) for CC6.7 should get penalized ───────────
print("\n── Test 2: At-rest encryption doc vs CC6.7 (should be penalized) ──")
bad_doc = """
AES-256 encryption applied to all database tables and S3 buckets.
Encryption keys managed via AWS KMS and rotated annually.
All data at rest is encrypted before writing to disk.
"""
result2 = scoreDocument(bad_doc, ctrl)
print(f"  Final score:      {result2['score']}")
print(f"  Mismatch penalty: {result2['mismatch_penalty']}  reasons={result2['mismatch_reasons']}")
print(f"  → Penalty should reduce score vs raw semantic")

# ── Test 3: Vague policy vs CC7.3 (specificity should hurt it) ───────────
print("\n── Test 3: Vague incident policy vs CC7.3 ──")
ctrl73 = load_control("CC7.3")
vague_doc = """
The company has an incident response policy. Incidents are escalated
to the appropriate team. Post-mortems are conducted after major incidents.
We take security seriously and respond promptly to all events.
"""
result3 = scoreDocument(vague_doc, ctrl73)
print(f"  Final score:      {result3['score']}")
print(f"  Specificity:      {result3['specificity_score']}  (should be low)")

print("\nPhase 3 sanity check complete.")