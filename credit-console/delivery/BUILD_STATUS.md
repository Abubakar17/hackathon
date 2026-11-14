**Commercial loan evidence-to-decision project — working canvas**

Status: working local prototype, 14 November 2026. Built sequentially in this chat. User requested placement in C:\Users\camil\OneDrive\Documentos\GitHub\hackathon; the implementation is credit-console/. Full plan: outputs/PROJECT_PLAN.md. No public push or platform submission was made.

**Q1 — Problem.** [declared] The team targets commercial underwriters reconciling financial evidence. [unverified] Significant time loss and willingness to pay; no verified Italian manual-review-time baseline is claimed.

**Q2 — Focus.** [proposed] One Italian small-company EUR term loan; evidence extraction, scoped financial-policy checks, abstention and a replayable record. Final credit approval remains outside the prototype.

**Q3 — Value proposition.** [proposed] Prepare a source-linked assessment that applies the lender's reviewed policy and identifies evidence gaps. Test with three practitioners; require two recent concrete pain examples and one policy owner willing to scope a pilot. Technical stop: any incomplete/contradictory test case produces PASS_POLICY_CHECKS.

**Q4 — Demonstrable claims.** [verified on synthetic fixtures] Matched rule and version visible; missing evidence produces abstention; frozen facts/model replay the same semantic result; exported DMN 1.5 executes in @smarthorizon-labs/dmn 0.1.0. PDF upload, explicit reviewer acceptance and three ISTAT market comparison charts work. Market differentiation against incumbents is unverified.

**Q5 — Failure points.** [risks] No lender policy; no permissioned packets; engine incompatibility; extraction error; network/credit failure; single-machine setup. Mitigations, owners and deadlines are in the full plan. Responsibilities are handled in this chat.

**Q6 — Build order.** [completed] Schema/policy → actual DMN execution → labelled synthetic fixtures → PDF/text extraction and evidence → validation/metrics → decision records/UI → 20-case checks → browser workflow checks. Optional AI extraction is implemented but not validated against a live provider; no key was supplied. Offline extraction is deliberately limited to explicit labels.

**Q7 — Audience.** [hypothesis] User: commercial credit analyst. Buyer/policy owner: bank credit-risk function. Bottom-up buyer count, access to ten prospects and pricing evidence: MISSING — needed before market claims. First-week contacts should come through introductions to banking credit/risk practitioners; none has been secured in this session.

**Q8 — Advantage.** [proposed] Future defensibility comes from approved policy mappings, permissioned cases and a measured correction/evidence benchmark. Extraction models and the DMN engine are commodities. No established moat claimed.

**Policy basis.** [verified by source read] EBA/GL/2020/06 §5.1, §5.2.5, §4.3, §5.3 and enterprise annexes; Bank of Italy Circular 285 Part I, Title IV, Chapter 3, Annex A.2. Two labelled demo policies provide illustrative thresholds; the regulatory-only policy remains unconfigured and abstains. No numerical threshold is attributed to regulation.

**Event.** [organiser guide] Decision-models Gate 2 weights: feasibility 16, financial sustainability 17, quality 15, proposal fidelity 10, selling story 11, adoption 13, real demo 18. Delivery 16:45 Rome/Berlin; three-minute demo within five-minute slot. Phase-II selection, submitted materials, model credits and live platform status: not verified; no Control8 tools available in this session.

**Verification log.** Official rulebook PDFs and ISTAT 2024 table page 2 were read and stored. Observed 20/20 benchmark checks, including 10/10 abstention cases and zero unsafe passes; all 12 integration tests and the browser workflow passed. The benchmark is included in one integration test, so counts are not independent. These observations apply to the defined synthetic offline cases, not real packets or live AI. Local hashed records are not immutable storage. Legal grounding does not establish a complete bank approval policy or extraction accuracy.

**Cut list.** Login/payments, multi-tenancy, autonomous policy interpretation, bank integrations, broad lending-product coverage, unsupported OCR and production immutability claims.

**Next action.** Rehearse the supplied complete / missing / conflicting PDF cases and market comparison; obtain a lender-approved policy and permissioned packets before claiming real-world underwriting performance. No verified manual-review time or loan market revenue is claimed.
