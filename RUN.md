# Running the credit decision console

Needs Python 3.10+ and Flask.

```bash
pip install -r requirements.txt
python check_set.py     # 19 cases + 6 properties, offline, exits non-zero on any failure
python app.py           # console on http://localhost:5000
```

The AI agent needs `AI_GATEWAY_API_KEY` in `.env` (Vercel AI Gateway). Without it, or with
the wifi off, untick "Read the document with the AI agent": the rule-based extractor runs
offline and gives the same decisions on the three sample documents.

## Demo in five clicks

1. **Weak application**: declined by rule `R2_LowDSCR`. Show the quoted evidence for each input,
   the explanation written from the record, and the "what would change the result" line.
2. **Incomplete application**: no decision. The debt service is missing and the collateral
   figure is marked "pending - unverified" in the document, so it is not used.
3. **Clean application**: granted at 5.5% under `R5_Prime`, policy v1.
4. In the decision table, click the DSCR test of `R5_Prime`, type `>= 2.0`, press Enter.
   The policy becomes v2 with a new hash and the same case now lands on `R6_Standard`.
5. Press **Replay the earlier record**: under v1 it is identical to the original, under v2 it differs.
   Then **Reset policy to v1 rules**.

**Run check set** (top right) shows the cases and the properties behind the claims.
Decision records are appended to `runs/decisions.jsonl`; every policy version is kept in `runs/policies/`.
