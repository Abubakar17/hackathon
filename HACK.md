# HACK.md — Decision models in an AI brain for industry

> The team's single source of truth for the day. Updated by the team and by 8hack. Every fact carries
> a marker: `[verified: source]` · `[declared]` · `[unverified]`. An empty section says
> `MISSING — needed before <phase>`.

Team: <names> · Builder: … · Business owner: … · Researcher: … · Presenter: …
Clock: pitch at 16:45 · Video cutoff: 12:15 · Track: 4-decision-models · Credits left: $25 [declared] · Official rubric: SKILL.md §2a

## Selection criteria (written before the ideas)
1. Core decision loop demoable end-to-end today (input situation → constraint evaluation → auditable decision record + rationale).
2. Clear economic pain (cost of a wrong decision or audit failure > €50k/year [declared]).
3. Moat beyond a prompt: formal decision object with constraints, alternatives evaluated, and deterministic abstention (refusal when data missing).

## Shortlist and gate
| Idea | Potential | Readiness | Flags | Verdict |
|------|-----------|-----------|-------|---------|
| Messy Credit App -> DMN Ruling & Decision Pipeline | 85 | 80 | ok | BUILD IT |

Chosen: Messy Credit App to .dmn Ruling Engine — because DMN is the open enterprise decision standard, enabling auditable credit approvals with deterministic abstention. Overrides of the verdict, if any: none.

## The 8hack canvas

### Q1 · Problem
Commercial loan underwriters and credit risk officers lose 3–5 hours per application [declared] manually cross-referencing messy PDFs, tax filings, and bank statements; today they manually copy-paste into Excel scoring templates with no auditable trace of policy overrides.

### Q2 · Focus
We focus on step 3 (Application ingestion, policy constraint verification, and credit grant/deny ruling) for commercial B2B lending. We explicitly ignore: KYC identity verification, disbursement payments, and loan servicing.

### Q3 · UVP to test
For commercial credit officers who waste hours parsing messy loan packets under regulatory audit pressure, our pipeline extracts structured financial context and generates an executable .dmn decision model and auditable decision object — unlike black-box LLM copilots — because it decouples unstructured extraction from deterministic, standard-compliant decision logic.
Hypothesis: We believe underwriters will trust AI decisions only if backed by an executable OMG-standard DMN table and deterministic abstention on missing data.
Test today: Run 10 messy credit application files through the pipeline; check if .dmn rules and decision objects match ground-truth loan policies in >90% of cases. · Kill criterion (ex-ante): Pipeline hallucinates a ruling on missing mandatory financial metrics instead of returning ABSTAIN in >0 of test cases. · Result: pending

### Q4 · USPs
1. Messy PDF chaos → structured extraction → instantaneous credit triage · proof: live demo on messy application · vs manual Excel entry · angle: outcome
2. Black-box hallucination risk → OMG-standard .dmn XML export + Decision Object · proof: executable DMN file opens in standard DMN viewer · vs chat-only copilot · angle: proof
3. Regulatory audit liability → complete decision provenance & deterministic abstention · proof: missing tax return triggers ABSTAIN with cited missing items · vs blind LLM guess · angle: objection

### Q5 · Single points of failure
| # | Component | How it fails | L/M/H | Impact | Mitigation | Owner | By |
|---|-----------|--------------|-------|--------|------------|-------|----|
| D1 | PDF parsing / OCR | Garbled table extraction on scanned financial PDFs | M | demo | Pre-clean and cache 3 representative application packets | Tech | 12:00 |
| D2 | Invalid .dmn XML | Generated DMN file fails standard schema validation | M | demo | Strict DMN XML template / validator in pipeline | Tech | 14:00 |
| D3 | LLM latency / gateway | Slow generation during 3-min pitch demo | L | demo | Local fallback cached run ready to show immediately | Tech | 15:30 |
| V1 | Riskiest assumption | Underwriters reject generated DMN logic as untrustworthy | H | thesis | Expose decision rationale and editable rules in DMN | Product | 16:00 |

### Q6 · First things to build
| # | Build | Proves | Done when | Time box | Status |
|---|-------|--------|-----------|----------|--------|
| 1 | Walking skeleton | End-to-end flow: Raw credit application text → Decision Object + valid .dmn file | Script runs on sample applicant and emits valid .dmn | 30 min | done |
| 2 | Riskiest piece: Abstention & Constraints | Pipeline reliably rejects or abstains when Debt Service Coverage Ratio (DSCR) is missing/insufficient | 3 edge cases (Pass, Reject, Abstain) execute deterministically | 45 min | done |
| 3 | Check set (10 cases) | Accuracy across standard loan approval rules | `python test_pipeline.py` prints >= 9/10 passed | 30 min | pending |
| 4 | "Now possible" moment | Interactive DMN inspection: show the exact rule row triggered and the generated DMN XML | UI/CLI renders ruling table + audit trace | 30 min | pending |
| 5 | Fallbacks | Offline cached run | Demo functions with wifi disconnected | 15 min | pending |

Cut list: Multi-tenant auth, direct core-banking API integrations, custom OCR training.

### Q7 · Target audience
Segment: … (early adopter because …) · Bottom-up size: … [marker]
Persona — who: … · job: … · trigger: … · where: … · objection: …
Pains: … · Gains: … · Buyer vs user: …
Where we reach ten of them next week: …

### Q8 · Moat technologies
| Technology | Commodity / differentiator | Today (in the demo) | Target (hard to copy) | Measured by | Horizon |
|------------|----------------------------|---------------------|-----------------------|-------------|---------|
| … | … | … | … | … | … |
Copy test: …

## Landscape (as of <date>)
<landscape card, or a link to LANDSCAPE.md>

## Evidence log
| When | Who (role, real or proxy) | Verbatim quote or observation | Assumption: confirmed / refuted / unclear |
|------|---------------------------|-------------------------------|-------------------------------------------|

## Verification log
| When | What an agent produced | What a human checked, and how | What the agent got wrong, and how we caught it |
|---|---|---|---|
| 13:54 | Initial extractor & DMN pipeline | Ran 10-case check set and multi-line memos | Regex missed uppercase EUR due to .replace() order before .lower(); caught by check set, fixed immediately to achieve 10/10 PASS |


## Checkpoints
- 1st (13:58): works end-to-end (messy text -> DMN XML + Decision Object) · check set 10/10 passed (100%) · learned: DMN decision tables cleanly enforce non-negotiable lending covenants while deterministic abstention stops ungrounded hallucination · slipped: none · cut: direct banking API integration · question for mentor: "How should we present the DMN XML export to non-technical jurors in the first 90 seconds?"

- 2nd (feature freeze): …

## Pitch
Outline, demo script and Q&A sheet: …

## Next week
Experiment card: …
