"""
PLG App — AI prompt templates.
All prompts used across the pipeline are stored here.
See PRD Sections 8.1 – 8.4.
"""

# ─── 8.1 Lead Qualification (Claude) ────────────────────────────

LEAD_QUALIFICATION_PROMPT = """You are a B2B lead qualification expert. Your job is to score candidate companies on how well they match the target buyer profile of a marketing/advertising agency.

TARGET AGENCY PROFILE:
{target_icp_json}

CANDIDATE COMPANIES (batch of up to 25):
{candidates_json}

QUALIFICATION RULES:
1. Score each candidate 0–100 on relevance to the target's ICP.
2. Score HIGHER for candidates that perfectly match the "ideal_customer_size" and "industries_served".
3. Score LOWER (or zero) for candidates that explicitly contradict the ICP or are completely irrelevant.

For each candidate, output:
{{
  "company_name": "...",
  "relevance_score": 0-100,
  "why_qualified": "1 sentence — what makes them a buyer",
  "buying_intent_signals": ["signal 1", "signal 2"]
}}

Return a JSON array. No prose, no markdown fences."""


# ─── 8.2 Reply Generation (Claude) ──────────────────────────────

REPLY_GENERATION_PROMPT = """You are writing a warm, personalised reply to a prospect who responded positively to our outreach.

REPLY FORMAT TEMPLATE (use this structure exactly):
{user_provided_template}

CONTEXT:
- Prospect's reply: {prospect_message}
- Prospect's company: {company_name}
- Prospect's name: {lead_name}
- Personalised lead list URL: {google_sheet_url}
- Their niche: {their_niche}

GUIDELINES:
- Reference their specific business naturally — show you actually understand what they do.
- Position the lead list as a value-first gift, not a sales pitch.
- Conversational tone, under 100 words.
- End with a clear, low-friction CTA (e.g. propose a 15-min call).
- Do NOT mention AI, automation, or "I noticed you replied".

OUTPUT: Just the final reply text. No preamble, no signoff like "Hope this helps!", no markdown."""


# ─── Reply Template (user-provided) ─────────────────────────────

REPLY_TEMPLATE = """Hey {lead_name},

Here's the GSheet - {sheet_url} (this will be a hyperlink) now go and win from this!

Also, If you wanna know how we guarantee 10 clients in 90 days to {their_niche} marketing agency owners like you with our AI systems - here's how we do it:

<a href="{loom_url}">
  <img src="{thumbnail_gif}"
       alt="Watch video"
       style="max-width:100%; border-radius:8px;" />
</a>

{social_proof}

Best,
Adi"""


# ─── 8.3 Sentiment Classification (Gemini) ──────────────────────

SENTIMENT_CLASSIFICATION_PROMPT = """Classify the sentiment of the following email reply as one of: positive, neutral, negative.

A "positive" reply expresses interest, asks for more info, or wants to schedule a call.
A "neutral" reply asks a clarifying question without commitment, or asks to be contacted later.
A "negative" reply declines, unsubscribes, or expresses irritation.

REPLY:
{reply_text}

Output exactly one word: positive, neutral, or negative."""


# ─── 8.4 ICP Extraction (Claude) ────────────────────────────────

ICP_EXTRACTION_PROMPT = """Read the following website content (homepage + about page) and extract the agency's ideal customer profile and past clients.

CONTENT:
{scraped_text}

Output strict JSON:
{{
  "services_provided": ["service 1", "service 2"],
  "niche": "1 sentence describing exactly what they do and for whom",
  "past_clients": ["client1.com", "client2.com"] (if you can find domains or names of case studies/clients. If none found, infer 10 example domains of perfect ideal clients they WOULD serve.)
}}

No prose, no markdown fences. Just the raw JSON object."""
