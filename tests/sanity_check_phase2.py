"""
scripts/sanity_check_phase2.py

A quick human-readable sanity check for Phase 2.
Unlike the pytest tests, this prints actual scores so you can see
how the model is behaving, not just whether it passed a threshold.

Run from the project root:
    python scripts/sanity_check_phase2.py
"""

from polara_checker.embeddings import embedQuery, embedDocument, cosineSimilarity, best_chunk_similarity

RESET  = "\033[0m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"

def score_label(sim: float) -> str:
    if sim > 0.6:
        return f"{GREEN}STRONG{RESET}"
    elif sim > 0.4:
        return f"{YELLOW}MODERATE{RESET}"
    else:
        return f"{RED}WEAK{RESET}"

def print_sim(label: str, sim: float) -> None:
    bar_len = int(sim * 40)
    bar = "█" * bar_len + "░" * (40 - bar_len)
    print(f"  {label:<40} {sim:.3f}  [{bar}]  {score_label(sim)}")

def section(title: str) -> None:
    print(f"\n{BOLD}{'─' * 60}{RESET}")
    print(f"{BOLD}  {title}{RESET}")
    print(f"{BOLD}{'─' * 60}{RESET}")


# ---------------------------------------------------------------------------
# Check 1: Relevant vs irrelevant document for CC6.1 (Access Controls)
# ---------------------------------------------------------------------------
section("CHECK 1 — CC6.1 Access Controls: relevant vs irrelevant")
print("  Reference: RBAC policy with permission tiers and user roles\n")

ref_cc61 = embedQuery(
    "Role-based access control policy defining permission tiers and user roles"
)

pairs = [
    ("✓ RBAC policy with access reviews",
     "RBAC policy defining least privilege roles with quarterly access reviews "
     "and formal provisioning workflow requiring manager approval"),

    ("✓ IAM dashboard with role assignments",
     "IAM dashboard showing role assignments, permission levels per role, "
     "and access request workflow with manager approval gates"),

    ("✗ Physical badge/keycard access",
     "Badge reader installed at office entrance for physical building access. "
     "Employees must swipe keycard to enter the facility."),

    ("✗ PTO and vacation policy",
     "Employees accrue 20 days of PTO per year. Vacation requests must be "
     "submitted two weeks in advance via the HR portal."),
]

for label, text in pairs:
    sim = cosineSimilarity(embedDocument(text), ref_cc61)
    print_sim(label, sim)


# ---------------------------------------------------------------------------
# Check 2: Mismatch detection for CC6.7 (Encryption in Transit)
# ---------------------------------------------------------------------------
section("CHECK 2 — CC6.7 Encryption in Transit: right vs wrong encryption type")
print("  Reference: TLS certificate management and HTTPS enforcement\n")

ref_cc67 = embedQuery(
    "TLS 1.2 or 1.3 enforced on all endpoints with certificate management and HTTPS"
)

pairs = [
    ("✓ SSL Labs scan + TLS config",
     "SSL Labs scan showing A+ rating. Load balancer enforces TLS 1.3 with "
     "auto-renewed certificates via Let's Encrypt. HSTS enabled."),

    ("✓ Certificate management doc",
     "Certificate authority configuration with 90-day renewal cycle. "
     "All internal APIs require mutual TLS authentication."),

    ("✗ Encryption AT REST (wrong type)",
     "AES-256 encryption for database storage. Encryption keys managed via "
     "AWS KMS. All data at rest is encrypted before writing to disk."),

    ("✗ Browser padlock screenshot",
     "Screenshot showing green padlock icon in Chrome browser address bar "
     "when visiting the company website homepage."),
]

for label, text in pairs:
    sim = cosineSimilarity(embedDocument(text), ref_cc67)
    print_sim(label, sim)


# ---------------------------------------------------------------------------
# Check 3: best_chunk_similarity — needle in a haystack
# ---------------------------------------------------------------------------
section("CHECK 3 — Needle in a haystack (CC7.3 Incident Response)")
print("  One relevant chunk buried among irrelevant ones\n")

ref_cc73 = embedQuery(
    "Incident response plan with severity tiers, escalation matrix, and post-mortem process"
)

chunks = [
    "The company offers a generous benefits package including health and dental.",
    "Annual security awareness training is completed by all employees.",
    # The needle ↓
    "Incident response plan defines P1-P4 severity tiers with escalation matrix, "
    "on-call rotation via PagerDuty, and mandatory post-mortem within 48 hours.",
    "Pull requests require two approvals before merging to the main branch.",
    "Employees must use the company VPN when working remotely.",
]

print("  Individual chunk scores:")
for i, chunk in enumerate(chunks):
    sim = cosineSimilarity(embedDocument(chunk), ref_cc73)
    marker = " ← needle" if i == 2 else ""
    print_sim(f"  Chunk {i+1}{marker}", sim)

chunk_embeddings = embedDocument(chunks)
best = best_chunk_similarity(chunk_embeddings, ref_cc73)
print(f"\n  best_chunk_similarity: {BOLD}{best:.3f}{RESET}")
print(f"  {'✓ Needle found correctly' if best > 0.35 else '✗ Needle not found — check your model'}")


# ---------------------------------------------------------------------------
# Check 4: Cross-control confusion — same doc scored against two controls
# ---------------------------------------------------------------------------
section("CHECK 4 — Cross-control confusion")
print("  An encryption-at-rest doc scored against CC6.7 (transit) vs CC6.8 (vuln mgmt)\n")

at_rest_doc = embedDocument(
    "AES-256 encryption applied to all database tables and S3 buckets. "
    "Encryption keys rotated annually via AWS KMS. At-rest encryption "
    "verified in quarterly compliance review."
)

ref_transit    = embedQuery("TLS encryption in transit HTTPS certificate management")
ref_vuln_mgmt  = embedQuery("Vulnerability scanning CVE patching remediation SLA Snyk Dependabot")

sim_transit   = cosineSimilarity(at_rest_doc, ref_transit)
sim_vuln_mgmt = cosineSimilarity(at_rest_doc, ref_vuln_mgmt)

print_sim("CC6.7 Encryption in Transit (wrong control)", sim_transit)
print_sim("CC6.8 Vulnerability Management (also wrong)", sim_vuln_mgmt)
print(f"\n  Both should be low — at-rest encryption belongs to neither control.")

print(f"\n{BOLD}{'─' * 60}{RESET}")
print(f"{BOLD}  Sanity check complete.{RESET}")
print(f"{'─' * 60}\n")