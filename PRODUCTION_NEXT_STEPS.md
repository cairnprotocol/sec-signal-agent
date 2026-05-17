# Production Next Steps

What I would build next to take this from prototype to a hardened regulated-workflow system.

## Phase 1: Hardening (Weeks 1-2)

**SEC Parsing**
- Replace brute-force HTML stripping with structured section extraction
- Handle XBRL inline tagging, nested exhibits, and HTML table content
- Build section-aware chunking for filings that exceed context windows
- Add support for 10-K annual filings and proxy statements

**Entity Matching**
- Replace exact ticker match with CIK-to-entity lookup table
- Add fuzzy matching for subsidiary names and legal entity variations
- Build a human-verified seed mapping for the initial monitored universe
- Add "no match found" routing that flags unmatched high-signal filings for manual review

**Evaluation Harness**
- Label 50+ filings with expected trigger type, evidence, and urgency tier
- Build automated pass/fail scoring for trigger extraction accuracy
- Track precision and recall by trigger family
- Run evals on every prompt change before release

**Confidence Calibration**
- Calibrate confidence scores against human-review outcomes
- Add confidence thresholds per trigger family
- Build abstention logic: if confidence < threshold, suppress rather than surface

## Phase 2: Signal Quality (Weeks 3-6)

**Novelty Detection / Delta**
- Store prior filing extractions in SQLite
- Compare current trigger against prior triggers for the same entity
- Detect: new signal vs. changed signal vs. repeated signal
- Suppress repeated signals, escalate changed signals
- Track filing amendments (10-K/A, 8-K/A)

**Deduplication and Staleness**
- Filing fingerprint: CIK + form type + filing date + item number
- Dedup check before triggering the agent loop
- Time decay: reduce score for filings older than 30/60/90 days
- Mark alerts as stale when a reviewer has already dispositioned the evidence packet

**Multi-Section Synthesis**
- Cross-reference Item 1.05 disclosures with MD&A operational impact and Risk Factors
- Detect tone escalation between consecutive filings
- Correlate cyber 8-K disclosures with subsequent 10-Q financial disclosures

**Expanded Trigger Families**
- Leading indicators: capex changes, compliance pressure, data growth
- Board / leadership changes: new CISO, new CTO
- M&A triggers: acquisition integration, divestiture
- Regulatory pressure: consent decrees, enforcement actions

## Phase 3: Workflow Integration (Months 2-3)

**Review Queue Integration**
- Create evidence packets in a case-management or workflow queue
- Attach filing quotes, extraction metadata, score components, and audit trace
- Route by workflow category, review priority, and entity type
- Record reviewer disposition without allowing the model to take direct operational action

**Human-Review Feedback Loop**
- Reviewer disposition: useful / not useful / needs more context
- Track whether the signal led to a documented review outcome
- Feed quality signals back into deterministic scoring weights
- Build a signal quality report for operations leads

**Observability**
- Structured logging for every LLM call, including prompt version, response metadata, usage, and latency
- Alert on extraction failures, API errors, and score anomalies
- Dashboard for signal volume, distribution, and quality trends
- Cost tracking per filing processed

## Phase 4: Scale (Months 3-6)

**Full EDGAR Coverage**
- Nightly batch processing of all new 8-K, 10-K, and 10-Q filings
- Filter to the monitored entity universe
- Handle 500+ filings/day processing volume
- Queue-based architecture with retry and dead-letter handling

**Multi-Region**
- Support for international filings from comparable public sources
- Multi-language extraction for non-English filings
- Region-aware workflow routing and ownership rules

**Advanced Agent Capabilities**
- Multi-filing correlation, such as cyber 8-K to subsequent 10-Q impact
- Proactive public-source research beyond the filing
- Corroboration from earnings call transcripts and public news
- Integration with additional public regulatory signals

## Architecture Principles

These design decisions should be preserved:

1. **Python controller**: The LLM reasons; Python executes. Never give the LLM direct system access.
2. **Deterministic scoring**: Scores must be explainable and reproducible. LLM provides inputs; Python computes outputs.
3. **Deterministic routing**: Workflow route and intervention category follow explicit rules, not free-form LLM reasoning.
4. **Evidence grounding**: Every claim must cite specific filing text. No unsupported inferences.
5. **Visible reasoning**: Reviewers must be able to see why the agent reached its conclusion.
6. **Abstention over hallucination**: If the signal is weak, say so or suppress it. Never fabricate urgency.
7. **Bounded agent behavior**: Max iterations, explicit terminal actions, fallback emission.
