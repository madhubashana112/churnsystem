# Churn AI — Project Brief

**Domain-adaptive churn prediction for SaaS, Telecom and FinTech.**

| | |
|---|---|
| **Live prototype** | https://churnsystem-two.vercel.app |
| **Source** | https://github.com/madhubashana112/churnsystem |
| **Stack** | FastAPI · pandas · Qwen-Max (Alibaba Model Studio) · Vercel |
| **Try it in 30 seconds** | Open the live URL → name a workspace → pick a vertical → **Run the sample** |

---

## 01. Problem

Churn analytics is sold per vertical, and every deployment starts with the same
unpaid work: a data engineer sits with the customer's tables and hand-writes a
mapping. Which column is the customer id? Which table is the event log? Which
columns are noise?

That mapping is the reason a churn tool takes weeks to onboard rather than
minutes, and it has to be redone for every customer, because no two schemas
agree. A telecom operator has `subscriber_id`, CDRs and recharges; a SaaS vendor
has `user_id`, an event log and invoices. The churn *logic* differs too — a
prepaid subscriber asking for a porting code and a SaaS account whose invoices
keep failing are both leaving, for entirely unrelated reasons.

So teams either buy three separate tools, or buy one and accept that it
understands none of their verticals well.

## 02. Solution

Upload your raw tables as they are. No pre-joining, no mapping config.

1. **Schema discovery** — the platform reads a sample of each file and works out
   the join key, classifies every table (dimension, time-series event,
   transactional, unstructured text) and marks the noise columns to discard.
2. **Feature synthesis** — it flattens the tables into one row per customer,
   deriving recency, rolling 7-day and 30-day activity windows, an activity
   velocity comparing the last week against the prior month, failure rates from
   status columns, and a churn-intent score mined from free text. 28–44 features
   per customer, none of them hand-specified.
3. **Sector scoring** — a vertical-specific core scores each customer and returns
   the drivers behind the score.
4. **Retention playbook** — every at-risk customer arrives with a channel, an
   action type and a ready-to-send message.

Two design decisions carry the product:

**The feature layer never learns about verticals.** It sees a schema, not an
industry. Sector knowledge lives in a separate enrichment step and in the scoring
cores, so adding a fourth vertical means adding one file, not editing the parser.

**It runs with or without a model.** Every AI call has a deterministic local
fallback, so the platform is never a blank screen when a key is missing, a quota
is hit or the provider is down. The dashboard always names which engine produced
the numbers you are looking at.

## 03. AI usage

**Alibaba Qwen-Max** does the two jobs that need judgment rather than arithmetic:

- **Schema resolution** — given a five-row sample of each uploaded file, it
  returns the join key, each table's role, its timestamp column and its noise
  columns. This is the step that would otherwise be a human data engineer.
- **Sector churn scoring** — three prompt-specialised cores (SaaS, Telecom,
  FinTech) score each customer and explain the result in that vertical's own
  terms: `primary_drivers` for SaaS, `root_cause` and a regional network flag for
  Telecom, `dormancy_type` for FinTech.

Everything numeric stays in pandas. The model is used where language and
judgment help, not as a calculator.

**The offline engine.** Because a demo that dies without an API key is not a
demo, both AI steps have a deterministic counterpart:

- `HeuristicSchemaResolver` classifies tables from column names and cardinality.
- `LocalChurnCore` reads what each synthesized feature *means* — recency,
  engagement volume, grievance volume, failure counts, monetary value — and ranks
  every customer against the rest of the cohort.

`auto` mode tries Qwen and falls back automatically, reporting why. `qwen` mode
surfaces errors instead of hiding them. `local` never calls out. After a failure,
Qwen is skipped for two minutes so repeat requests do not pay for a call already
known to fail.

## 04. Impact

**Onboarding goes from weeks to one upload.** The mapping step that normally
requires a data engineer is done by the platform.

**Measured accuracy.** The bundled datasets contain a known churning cohort
(25 of 100 customers per vertical), so the engine's output can be scored against
ground truth. Running fully offline, with no model call:

| Sector | Features/customer | AUC | True churners in the top 25 | Scoring time |
|---|---|---|---|---|
| SaaS | 28 | 0.975 | 22 / 25 | 0.07s |
| Telecom | 34 | 0.962 | 20 / 25 | 0.06s |
| FinTech | 44 | 0.961 | 20 / 25 | 0.09s |

A retention team working the top 25 accounts reaches 80–88% of the customers who
were actually about to leave.

**The drivers are the deliverable, not the score.** A probability tells a
retention agent nothing actionable. Each account arrives with its top drivers —
*"Long gap since the last recharge record (worst decile in the cohort)"* — and a
playbook naming the channel, the action and the message to send.

**Honest about provenance.** Every result is labelled with the engine that
produced it, and a fallback is announced rather than passed off as a model
result.

**Engineering quality.** 56 tests, none touching the network. Feature tests
assert hand-computed values (velocity `10 / (20/4.286) = 2.14`, a 0.5 epsilon
floor to stop divide-by-zero, `0.3` failure rate) rather than checking generated
data against itself.

## 05. Roadmap

**Near term — make it a product rather than a session**
- Postgres behind the existing repository interfaces, replacing in-memory
  storage. The interfaces already exist; only the implementations change.
- Authentication and real multi-tenant isolation.
- Persist multiple analysis runs per tenant so churn can be tracked over time,
  not just measured once.

**Medium term — close the loop**
- Push playbooks into the channels they name (Twilio for SMS, SendGrid for
  email, webhooks for in-app) and record what was sent.
- Measure whether interventions worked, and feed that back into scoring — the
  step that turns a prediction tool into a retention tool.
- Scheduled re-scoring with alerting on tier changes.

**Longer term — beyond three verticals**
- A supervised model trained on each tenant's own outcomes once enough
  intervention history exists, with the current engine as the cold-start.
- Self-serve vertical definition, so a new industry is configuration rather than
  code.
- Explainability the compliance team can accept: per-feature contributions rather
  than ranked drivers, which matters in regulated FinTech deployments.

**Known gaps, stated plainly**
- Tenants and analysis results are in-memory; a restart clears them. The
  workspace id is self-describing so it survives, but stored runs do not.
- The Qwen path is implemented but unverified end-to-end, because the API key
  available during the build was rejected (401). The offline engine is what the
  live prototype demonstrates.
- The three sector cores are only reachable with a live key, so they are not yet
  covered by the test suite.
