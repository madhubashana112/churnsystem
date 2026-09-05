# AI Usage Statement

> **⚠ THIS FILE IS A TEMPLATE — IT MUST BE COMPLETED BEFORE SUBMISSION.**
>
> Everything in `< ANGLE BRACKETS >` is a placeholder. This document describes
> how **you** used Qoder while building the solution, and only you know that.
> It was drafted with the structure and word count judges expect, but the
> factual claims have deliberately been left blank rather than invented —
> submitting a fabricated account of your own tooling would be worse than
> submitting nothing.
>
> Delete this box once the placeholders are filled.

---

## How Qoder was used

**Where it was used**

< Name the parts of the codebase you built with Qoder. Be specific — file or
module level is ideal. For example: the FastAPI route layer, the pandas feature
synthesis, the Jinja templates, the mock data generator. >

**What it was used for**

< Pick the ones that are true and drop the rest, then add detail:
  - scaffolding the Clean Architecture folder structure and interface stubs
  - generating the initial FastAPI routers and Pydantic models
  - writing the pandas aggregation logic
  - drafting the Qwen prompts for schema resolution and sector scoring
  - producing the HTML/CSS/JS for the dashboard
  - explaining or refactoring existing code
  - writing tests >

**How it changed the way we worked**

< One or two concrete sentences. Judges respond to specifics far more than to
adjectives. Something like: "Qoder produced the first version of the three
sector cores in one pass; they were near-identical by design, so we kept the
duplication and moved batching up into the use case rather than repeating it
three times." >

**What we did not use it for, and why**

< This paragraph is worth including — it shows judgment. Examples: the churn
scoring weights were hand-tuned against the labelled cohort because generated
thresholds did not separate the classes; the serverless statelessness fix was
designed by hand after observing the failure. >

**Roughly how much of the final code**

< An honest estimate, e.g. "about 60% of the initial scaffold, perhaps 25% of
the final committed code after review and rework." Judges are more sceptical of
"100% AI-generated" than of an honest split. >

---

## For accuracy, the record of this repository

So the statement above is consistent with what a judge can verify from the git
history, these are the facts we can attest to:

- The initial project scaffold — the folder structure, interface stubs and the
  first pass at the FastAPI layer — was **generated from a written spec by an AI
  coding tool**. The result was a working skeleton: 1,037 lines total, with most
  domain files under 15 lines, and the feature synthesizer doing only
  `groupby().size()` with the comment *"count rows for now"*.
- The substantive implementation in commits `e56d5c4` through `52daf2b` — the
  time-series and text features, the offline scoring engine, multi-sheet
  ingestion, the sector dashboards and the 56-test suite — was written with
  **Claude Code (Claude Opus 5)**, which is credited as co-author in those
  commit messages.
- **Alibaba Qwen-Max** is used *inside the product itself*, not as a development
  tool: schema resolution and sector churn scoring. See
  [PROJECT_BRIEF.md](PROJECT_BRIEF.md) §03.

< If Qoder was used at any of these stages, say so here and correct the above
to match. If Qoder was the tool that generated the initial scaffold, state that
plainly — it is a legitimate and substantial contribution. >

---

## A note on the product's own AI

Judges sometimes conflate the two, so it is worth separating them explicitly:

| | Tool | Role |
|---|---|---|
| **Development** | Qoder < + others as applicable > | Used by the team to write the code |
| **Runtime** | Alibaba Qwen-Max | Used by the deployed product to resolve schemas and score churn |

The runtime AI is described in full in [PROJECT_BRIEF.md](PROJECT_BRIEF.md), including
the deterministic offline engine that backs it when no API key is available.
