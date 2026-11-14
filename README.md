# loan4every1 · Credit decision console

Loan applications arrive as memos, emails and PDFs. An agent reads the document and fills the
inputs of a decision table. A rules engine, not the language model, applies the versioned rules
and returns the decision with the rule and the policy version that produced it. Cases the
policy does not cover, that lack required data, or whose documents contradict each other go to
a person. A credit officer signs off every case with Accept or Reject.

Hackathon prototype, track 4 (decision models in an AI brain for industry), 14 November 2026.

## Demo video

▶ **[Watch the demo (Google Drive)](https://drive.google.com/file/d/1oARzXeQCChQMmPsUqQsWZFyLnFkVYiiG/view?usp=sharing)**

The pitch video is also in the repository: [`loan4every1-pitch.mp4`](loan4every1-pitch.mp4).

## Quick start

Needs Python 3.10+.

```bash
pip install -r requirements.txt   # flask, pypdf
python check_set.py               # 28 cases + 15 properties, offline
python app.py                     # console on http://localhost:5000
```

- The AI reader needs `AI_GATEWAY_API_KEY=...` in a `.env` file (Vercel AI Gateway). Without a key,
  or offline, untick "Read with the AI agent": the rule-based reader runs locally and gives the
  same decisions on all five samples.
- `PORT=5001 python app.py` (on Windows: `set PORT=5001` first) runs it on another port.
- Click-by-click demo script: [RUN.md](RUN.md).

## How it works

| Step | File | What it does |
|---|---|---|
| Read | `ai_analyst.py`, `extractor.py` | Claude (via Vercel AI Gateway) proposes each input with a verbatim quote. Code keeps a value only if the quote is in the document and the number is in the quote. Figures the document marks as pending or unverified are not used. Offline fallback: a rule-based extractor. |
| Upload | `pdf_reader.py` | PDF, TXT and MD files (up to 5, 4 MB each) are turned into one text document, each page under a separator naming its file. Nothing is stored. |
| Decide | `policy.py` | Two gates run before the decision table. First, a figure the documents state with two different values means no decision (`GATE_EVIDENCE_CONFLICT`). Then a missing required input means no decision (`GATE_INPUT_COMPLETENESS`). Otherwise the DMN decision table is evaluated row by row. |
| Record | `pipeline.py` | The record holds the inputs with their evidence, the derived ratios, every rule row checked, the rule that fired, the policy version and hash, an explanation in plain words and, for a case that was not granted, a counterfactual confirmed by re-running the table. |
| Review | `pipeline.py` | The officer accepts or rejects. The review is stored beside the record with the rule and policy version it signs off. Overriding the engine, or deciding a case it abstained on, needs a note. |
| Replay | `pipeline.py` | A stored record is re-run from its frozen inputs, under its original policy version and under the current one. The language model is not in this path. |

The record id is a hash of the inputs, any detected conflicts and the policy hash, so the same
inputs under the same policy always give the same id.

## The policy and how the DMN file is made

The policy is one DMN 1.3 decision table with hit policy **FIRST**: rows are tried top to bottom
and the first row that matches decides.

- **7 inputs:** DSCR (EBITDA ÷ annual debt service), loan-to-value (requested amount ÷ collateral
  value), years in business, tax returns verified, net equity, days past due, and leverage
  ((existing debt + requested amount) ÷ EBITDA). The ratios are calculated in Python from the
  quoted figures before the table runs. Net equity, days past due and existing debt are optional:
  a rule that needs one of them cannot fire without it, and the record lists it as "not checked".
- **12 rules**, in order: `R1_TaxUnverified`, `C1_PastDue90`, `C2_NegativeEquity`,
  `C3_DSCRBelowOne`, `R2_LowDSCR`, `R3_HighLTV`, `R4_ShortHistory`, `C4_ExceptionalLeverage`,
  `C5_Leveraged`, `R5_Prime` (granted, 5.5%), `R6_Standard` (granted, 7.2%) and `R7_Uncovered`
  (no rule covers the case: to a person).
- **5 rules cite a public source**, stored inside the `.dmn` file with the source, article, exact
  quote, link and a note on how far the source goes: CRR Article 178 (more than 90 days past due),
  the CNDCEC crisis indicators (negative equity, DSCR below 1) and the ECB guidance on leveraged
  transactions (leverage above 4 and above 6). The other 7 rules are the team's own demo thresholds
  and are shown as "no citation · the bank's own credit policy".

How the file is produced and used (`policy.py`):

1. The rules are written as a list in code (`BASE_RULES`).
2. `rules_to_dmn` writes that list out as DMN XML.
3. For every decision, `dmn_to_rules` reads the XML back and the engine evaluates those rows. The
   `.dmn` file you can download from the console is exactly what decided the case.
4. Each policy version is identified by the hash of its XML. Editing a cell of the table in the
   console creates a new version (the old one is kept for replay); if the edited rule had a
   citation, the citation is removed because the rule no longer says what the source says.

## Sample cases

| Button | Result |
|---|---|
| Clean | Granted at 5.5% under `R5_Prime` |
| Weak | Declined under `R2_LowDSCR` (DSCR 1.05) |
| Incomplete | No decision: annual debt service and collateral value are missing or marked unverified |
| Leveraged | To a person under `C5_Leveraged` (ECB guidance cited) |
| Conflicting | No decision: two documents give EBITDA as €520,000 and €410,000 |

Sample PDFs are in [`samples_pdf/`](samples_pdf) and linked in the console: a clean application,
and the conflicting packet as two PDFs to upload together. `samples_pdf/make_pdfs.py` regenerates
them from `samples.py` (needs reportlab).

## Tests

`python check_set.py` runs offline and exits non-zero on any failure. It currently passes
**28/28 cases and 15/15 properties**:

- the cases cover grants, denials, each cited rule, missing and unverified inputs, the gap between
  the deny and grant thresholds, Italian number formats, negative EBITDA, conflicting figures and
  the five demo samples;
- the properties check that the `.dmn` file round-trips, the same input gives the same record,
  replay is exact, a rule edit creates a new version and old versions still decide the same way,
  counterfactuals are confirmed by re-running, citations are complete, a conflict abstains, a PDF
  gives the same record as its text, unreadable files are refused, and reviews are tied to their
  record with a note required for overrides.

The console's "Run check set" button runs the same checks.

## Where things are written

- `runs/decisions.jsonl`: every decision record (append-only).
- `runs/reviews.jsonl`: every Accept / Reject review.
- `runs/policies/<hash>.dmn`: every policy version, so old records can be replayed.
- `delivery/decision_object.json` and `delivery/ruling.dmn`: overwritten with the latest decision
  and policy each time a case is decided.

`runs/` is git-ignored.

## Repository map

| Path | What it is |
|---|---|
| `app.py` | Flask server and API |
| `templates/index.html` | The console (single page) |
| `ai_analyst.py`, `extractor.py` | AI reader and offline rule-based reader |
| `pdf_reader.py` | PDF / TXT / MD upload |
| `policy.py` | Rules, DMN export and import, engine, policy versions |
| `pipeline.py` | Decision records, replay, human review |
| `samples.py`, `samples_pdf/` | Demo applications as text and as PDFs |
| `check_set.py` | Test cases and properties |
| `delivery/` | Pitch page, plan, abstract, video script, latest decision object and `.dmn` |
| `loan4every1-pitch.mp4` | Pitch video |
| `Economic Model.pdf` | Economic model |
| `HACK.md`, `ABSTRACT.md`, `VIDEOSCRIPT.md` | Hackathon canvas, abstract and video outline |
| `real_test/` | Earlier experiment (a Fannie Mae eligibility table and its results). No code in this version runs it. |

## Limits of the prototype

- Text PDFs, TXT and pasted text only: no OCR, so scans are refused.
- A conflict is found when the same labelled figure appears with two values. Differently worded figures are not reconciled.
- The human review has no login; the reviewer name is typed in.
- The DMN file is executed by our own small engine, which supports comparisons, `true`/`false`
  and `-`. It has not been run in Camunda or another DMN engine.
- DSCR uses existing debt service only; the new loan's repayments are not added.
- The sample applicants, thresholds and rates are invented for the demo.
- The AI reader is only used when a gateway key is present; the tests run on the offline reader.
- Policy versions and records live in local files; there is no login or access control.
