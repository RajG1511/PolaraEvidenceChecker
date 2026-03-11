# Evaluation Report — Evidence Quality Checker (PLR-EXP-001)

> **Run date:** March 2026  
> **Test suite size:** 88 evidence documents  
> **Result:** ✅ 88/88 passed (0 failed, 0 errors)  
> **LLM adjudication:** 21/88 (23.9%)  
> **Repository:** `polara-evidence-checker`

---

## TL;DR
The Evidence Quality Checker correctly matched the **expected verdict** for **all 88 test documents** across the covered SOC 2 controls. Most cases were resolved deterministically; the system escalated only borderline cases to an LLM adjudicator as designed.

---

## What This Evaluates
This evaluation measures whether the service returns the correct **verdict** for each document/control pair:

- `sufficient`
- `insufficient`
- `uncertain` (not observed in this test run)

Each test case is a document that has:
- a **mapped SOC 2 control** (e.g., `CC6.1`)
- an **expected verdict**
- the program’s **predicted verdict**
- whether the LLM adjudicator was used

---

## Summary Metrics

| Metric | Value |
|---|---:|
| Total files | 88 |
| Passed | 88 |
| Failed | 0 |
| Errors | 0 |
| Accuracy | 100% |
| LLM-adjudicated | 21 (23.9%) |
| Deterministic-only | 67 (76.1%) |

---

## Performance (Latency)
Observed runtimes from the test output logs.

| Path | Typical runtime |
|---|---:|
| Deterministic scoring | ~2.2–3.1s |
| With LLM adjudication | ~3.5–5.0s |

Notes:
- Deterministic runs cluster around ~2–3 seconds per file.
- LLM-adjudicated runs cluster around ~4–5 seconds per file (as expected for an external model call).

---

## LLM Adjudication Details (21 Files)
These files fell into the uncertainty band and were routed to the LLM adjudicator. All were correctly classified.

### Sufficient (5)
| File | Control | Score | Time |
|---|---|---:|---:|
| `29_CC2.3_sufficient_external_security_communications_procedure.pdf` | CC2.3 | 0.3941 | 4.99s |
| `31_CC3.3_sufficient_fraud_risk_assessment_register.pdf` | CC3.3 | 0.3971 | 4.13s |
| `33_CC3.4_sufficient_change_risk_impact_assessment.pdf` | CC3.4 | 0.3428 | 4.84s |
| `39_CC6.4_sufficient_restricted_physical_access_procedure.pdf` | CC6.4 | 0.3903 | 4.41s |
| `41_CC6.5_sufficient_asset_decommissioning_sanitization_record.pdf` | CC6.5 | 0.4326 | 4.02s |

### Insufficient (16)
| File | Control | Score | Time |
|---|---|---:|---:|
| `06_CC7.3_insufficient_jira_incidents_board.pdf` | CC7.3 | 0.4921 | 4.56s |
| `08_CC8.1_insufficient_commit_log_only.pdf` | CC8.1 | 0.4439 | 4.23s |
| `10_CC6.8_insufficient_requirements_txt_only.pdf` | CC6.8 | 0.2782 | 4.70s |
| `12_CC6.7_insufficient_encryption_at_rest_policy.pdf` | CC6.7 | 0.2927 | 4.71s |
| `19_CC7.1_insufficient_outdated_scan.pdf` | CC7.1 | 0.3351 | 4.29s |
| `22_CC1.2_insufficient_management_roadmap_sync.pdf` | CC1.2 | 0.4469 | 4.51s |
| `22_CC1.3_insufficient_team_directory.pdf` | CC1.3 | 0.2492 | 3.50s |
| `25_CC2.2_insufficient_slack_directory.pdf` | CC2.2 | 0.2712 | 3.82s |
| `26_CC1.5_insufficient_recognition_awards.pdf` | CC1.5 | 0.3280 | 4.03s |
| `28_CC2.2_insufficient_all_hands_reminder.pdf` | CC2.2 | 0.2468 | 3.86s |
| `30_CC4.2_insufficient_jira_backlog.pdf` | CC4.2 | 0.2794 | 3.76s |
| `34_CC3.4_insufficient_release_notes.pdf` | CC3.4 | 0.2747 | 3.94s |
| `34_CC9.1_insufficient_infra_notes.pdf` | CC9.1 | 0.3137 | 3.89s |
| `36_CC4.2_insufficient_engineering_bug_backlog.pdf` | CC4.2 | 0.3645 | 4.40s |
| `38_CC5.2_insufficient_architecture_overview.pdf` | CC5.2 | 0.2774 | 4.08s |
| `44_CC9.1_insufficient_backup_configuration_summary.pdf` | CC9.1 | 0.4250 | 3.84s |

---

## Notable Behaviors Observed
These patterns are **desired** and match the intended design of the checker.

- **Mismatch detection**: The system correctly flags documents that are “about security” but wrong for the control (e.g., encryption-at-rest evidence for encryption-in-transit).
- **Specificity vs. vagueness**: Documents that mention the topic without demonstrating enforcement/process/configuration trend toward `insufficient` (often requiring LLM adjudication).
- **Adjacency traps**: Operational artifacts (Jira backlogs, engineering bug queues, infra notes) are frequently adjacent to the right control but still insufficient as audit evidence; these are handled correctly.

---

## How To Reproduce
Below are placeholders you can adapt to your repo. The exact command depends on your harness.

```bash
# Example (replace with your actual test runner)
python -m polara_checker.tests.run_suite --path ./tests/fixtures --format text