# loan4every1 · Credit decision console

Loan applications arrive as memos, emails and PDFs. An agent reads the document and fills the
inputs of a decision table. A rules engine, not the language model, applies the versioned rules
and returns the decision with the rule and the policy version that produced it. Cases the
policy does not cover, that lack required data, or whose documents contradict each other go to
a person. A credit officer signs off every case with Accept or Reject.

Hackathon prototype, track 4 (decision models). How to run and demo it: [RUN.md](RUN.md).

## How it works

| Step | File | What it does |
|---|---|---|
| Read | `ai_analyst.py`, `extractor.py` | Claude (via Vercel AI Gateway) proposes each input with a verbatim quote. Code keeps a value only if the quote is in the document and the number is in the quote. Figures the document marks as pending or unverified are not used. Offline fallback: a rule-based extractor. |
| Upload | `pdf_reader.py` | PDF, TXT and MD files are turned into one text document, each page under a separator naming its file. Nothing is stored. |
| Decide | `policy.py` | The policy is a DMN 1.3 decision table (hit policy FIRST). The engine parses that XML and evaluates its rows. Two gates run first: a figure the documents state with two different values means no decision, and so does a missing required input. |
| Record | `pipeline.py` | The record holds the inputs with their evidence, the derived ratios, every rule row checked, the rule that fired, the policy version and hash, an explanation in plain words and a counterfactual confirmed by re-running the table. |
| Review | `pipeline.py` | The officer accepts or rejects. The review is stored beside the record (`runs/reviews.jsonl`) with the rule and policy version it signs off. Overriding the engine, or deciding a case it abstained on, needs a note. |
| Replay | `pipeline.py` | A stored record is re-run from its frozen inputs, under its original policy version and under the current one. The language model is not in this path. |

The record id is a hash of the inputs and the policy hash, so the same inputs under the same
policy always give the same id.

## Limits of the prototype

- Text PDFs, TXT and pasted text only: no OCR, so scans are refused.
- A conflict is found when the same labelled figure appears with two values. Differently worded figures are not reconciled.
- The human review has no login; the reviewer name is typed in.
- The DMN file is executed by our own small engine, which supports comparisons, `true`/`false`
  and `-`. It has not been run in Camunda or another DMN engine.
- DSCR uses existing debt service only; the new loan's repayments are not added.
- The sample applicants, thresholds and rates are invented for the demo.
- Policy versions and records live in local files; there is no login or access control.
