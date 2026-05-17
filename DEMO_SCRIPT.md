# Demo Script - SEC Signal Agent

## Before The Demo

1. Run `streamlit run app.py` and verify the dashboard loads.
2. Use **Pre-run Demo** for a stable walkthrough that does not require a live model call.
3. If using **Live Run**, confirm `ANTHROPIC_API_KEY` is set.
4. Refresh the saved output with `python demo_runner.py --all` when source excerpts or workflow metadata change.

## Opening

"This prototype monitors verified, pre-parsed public EDGAR excerpts and turns them into a ranked human-review queue. The primary public view is healthcare commercial, partnerships, operations, trust/security, and compliance review."

"The parser layer is intentionally scoped out. The demo focuses on the AI workflow layer: signal extraction, deterministic scoring and routing, evidence validation, review queue generation, and audit trace."

## Show The Dashboard

1. Open Streamlit in **Pre-run Demo** mode.
2. Point out the sidebar filters:
   - Corpus: Healthcare EDGAR / Other Industries EDGAR / All
3. Keep the default view on Healthcare EDGAR.
4. Walk through the ranked evidence packets.
5. Open Evidence Quotes and show that the packet is grounded in local excerpt text.
6. Open Audit Trace and show deterministic workflow steps.

"The output is not a clinical workflow and not an autonomous decision. It is a source-grounded review queue for the human who has to decide whether the signal changes diligence, account priority, messaging, or operational follow-up."

## Review Lanes

| Lane | Primary user | Job to be done | CTA | Deliverable |
| --- | --- | --- | --- | --- |
| Trust & Diligence | Trust/Security, Compliance, Quality reviewer | Stay ahead of partner diligence questions sparked by peer disclosures | Prepare diligence packet | 1-page packet with peer event summary, equivalent control posture placeholder, suggested Q&A |
| Commercial Signal | Partnerships, Commercial Strategy | Spot account openings from prospect filings | Generate partner brief | 1-page brief with trigger, account context, suggested outreach angle, draft message |

## Suggested Healthcare Examples

- **Teladoc Health:** privacy/security and healthcare regulatory obligations for trust review.
- **iRhythm Technologies or Dexcom:** reimbursement and payer exposure for commercial strategy review.
- **Alignment Healthcare:** Medicare Advantage and CMS contract exposure for quality/reporting review.
- **Doximity or Omada Health:** platform scale and workflow relevance for partnerships or product operations review.

## Live Run

1. Switch to **Live Run**.
2. Select a filing from the healthcare EDGAR core.
3. Click **Run Agent**.
4. Narrate the steps:
   - "First it extracts the trigger from the local SEC excerpt."
   - "Then it loads synthetic entity and workflow context."
   - "Scoring and review-lane assignment are deterministic Python controls."
   - "The final card includes evidence, source metadata, a recommended review action, and an audit trace."

## Architecture Walkthrough

"The important design choice is separation of responsibilities. The model handles language-heavy extraction and synthesis. Python owns orchestration, schemas, scoring, routing, fallbacks, and evidence checks."

"That makes the system easier to audit: the reviewer can see what text supported the signal, where it was routed, why it was prioritized, and what human action is recommended."

## Priority Buckets

| Bucket | Meaning | Action |
| --- | --- | --- |
| Hot | High-confidence, high-urgency item | Produce the lane-specific packet or brief this week |
| Warm | Relevant item with useful evidence | Review in weekly planning or corroborate with account context |
| Monitor | Weak, early, or lower-priority item | Track but do not produce a deliverable yet |
| Skip | Not actionable for the active workflow | Exclude from the default review queue |

## Production Next Steps

For a production-grade version, I would add:

- robust SEC parser with section extraction and XBRL handling;
- novelty detection across filing history;
- deduplication and staleness suppression;
- labeled evaluation sets for extraction, evidence matching, abstention, and routing;
- reviewer disposition capture;
- confidence calibration;
- stronger grounding and abstention logic.

## Backup Plans

- **API fails during live run:** switch to Pre-run Demo mode and explain that the saved output uses the same local corpus and deterministic controls.
- **Streamlit will not load:** run `python demo_runner.py --ticker TDOC` in terminal.
- **Question about hallucination:** point to the local excerpt text and evidence-quote match check.
- **Question about healthcare safety:** explain that the target user is commercial, partnerships, operations, trust/security, or compliance review; the system does not provide diagnosis, treatment, medication recommendations, cardiac prediction, emergency escalation, or patient-specific triage.
