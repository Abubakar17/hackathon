# Your Credit Decision Console

Project location: `C:\Users\camil\OneDrive\Documentos\GitHub\hackathon\credit-console`

Open **http://127.0.0.1:8765**. To start it again, double-click **Start-Credit-Console.cmd** in the `hackathon` folder.

Start with **Complete packet → Evaluate packet**. The sample is fictional; all supplied financial limits are clearly labelled demo assumptions.

The six tabs provide:

- **Application review:** PDF/text upload, evidence quotes, coverage/leverage/collateral calculations and explanations.
- **Market comparison:** three charts against official ISTAT 2024 Italian business aggregates, grouped by company size. Enter the same year's figures and inspect the source table.
- **Rules & rulebooks:** EBA and Bank of Italy documents, relevant sections, formulas and implementation limits.
- **Records & replay:** save a decision bundle, export the executed DMN and reproduce the result from frozen evidence.
- **Verification:** run the 20 predefined checks and see their actual results.
- **Activity console:** `help`, `run missing`, `replay`, `verify` and `benchmark`.

For the abstention demo, select **Missing repayments** or **Conflicting statements**. For the review workflow, upload `credit-console/fixtures/complete-packet.pdf`; it pauses until you accept the extracted evidence.

The market data is real, official ISTAT data. It describes 2024, published in October 2026; it is a national size-based comparison, not a credit-risk score or a sector-matched average. The sample borrower and credit thresholds are synthetic. Live AI extraction is optional and needs your Gateway key; the tested offline workflow works immediately.

Observed verification: 20/20 benchmark cases, 10/10 specified abstention cases, all 12 integration tests and the browser workflow passed. This is a working prototype, not a validated bank approval system.

The repository's existing notes, runs and branch were preserved. No commit or push was made.
