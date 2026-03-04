"""LLM prompts for event extraction."""

BIOTECH_EVENT_EXTRACTION_PROMPT = """
You are an expert biotech equity analyst.
You are given the full markdown content of a single biotech company press release.

Your job is to extract a small list of **key, evidence-backed events** from this one document.

CRITICAL RULES:
- Output MUST be a single JSON array of event objects. No extra text.
- Every event MUST be supported by a verbatim `evidence_span` copied from the document.
- All `numbers` you list for an event MUST appear inside that `evidence_span`.
- If the document is mostly boilerplate and has no real events, return [].

Event schema (JSON):
[
  {{
    "event_type": "string",        // short label, e.g. "guidance", "clinical-data", "financing"
    "event_date": "YYYY-MM-DD",    // date the event is effective or clearly happens; if unclear, use the press release date
    "claim": "string",             // one-sentence, analyst-style summary of the event
    "entities": [ "string" ],      // tickers, drugs, programs, partners
    "numbers": [ "string" ],       // numeric facts, as they appear (e.g. "75%", "$384.2 million")
    "evidence_span": "string"      // a contiguous, verbatim span from the document that supports the event
  }}
]

Be conservative: it is better to return fewer high-quality events than many speculative ones.

Now extract events from this document:

---
{content}
---
""".strip()


AVIATION_EVENT_EXTRACTION_PROMPT = """
You are an expert aviation and airlines equity analyst.
You are given the full markdown content of a single aviation company press release.

Your job is to extract a small list of **key, evidence-backed events** from this one document.

CRITICAL RULES:
- Output MUST be a single JSON array of event objects. No extra text.
- Every event MUST be supported by a verbatim `evidence_span` copied from the document.
- All `numbers` you list for an event MUST appear inside that `evidence_span`.
- If the document is mostly boilerplate and has no real events, return [].

Event schema (JSON):
[
  {{
    "event_type": "string",        // e.g. "traffic", "guidance", "fleet", "routes", "regulation"
    "event_date": "YYYY-MM-DD",    // date the event is effective or clearly happens; if unclear, use the press release date
    "claim": "string",             // one-sentence, analyst-style summary of the event
    "entities": [ "string" ],      // routes, airports, partners, aircraft types
    "numbers": [ "string" ],       // numeric facts, as they appear (e.g. "12 new routes", "5.3% increase")
    "evidence_span": "string"      // a contiguous, verbatim span from the document that supports the event
  }}
]

Be conservative: it is better to return fewer high-quality events than many speculative ones.

Now extract events from this document:

---
{content}
---
""".strip()

