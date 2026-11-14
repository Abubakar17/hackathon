  ### 2. Abstract (1,087 / 1,200 characters)
  
Commercial loan underwriters waste significant time manually parsing messy financial statements, tax filings, and bank records. Under heavy regulatory oversight (e.g., Basel, ECB), they cannot use black-box LLM copilots that hallucinate credit advice without an auditable, legal rationale.

We build an automated decision pipeline that ingests unstructured credit packets and compiles them into an industry-standard OMG Decision Model and Notation (.dmn) ruling file alongside an immutable Decision Object. Our system decouples messy data extraction from formal constraint logic: evaluating debt service coverage ratios, collateral thresholds, and leverage covenants. Crucially, when mandatory financial data is missing or contradictory, our engine deterministically abstains with cited missing evidence rather than guessing.

By the pitch, we will demonstrate the end-to-end pipeline processing real-world credit application packets, rendering executable DMN decision tables in an open engine, and proving 100% adherence to deterministic abstention on incomplete loan files.  
