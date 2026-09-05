# Demo Video Script — 3:00 max

Record at **1440×900**, light theme (the default), browser zoom 100%.
Everything below is doable on the live URL with no setup:
**https://churnsystem-two.vercel.app**

Before recording: open a private/incognito window so `localStorage` is empty and
you land on onboarding.

Total scripted runtime **2:50**, leaving 10s of headroom.

---

## 0:00 – 0:25 · The problem

**Screen** — the landing page at https://churnsystem-two.vercel.app

> "Every churn tool starts the same way: a data engineer hand-writes a mapping
> from the customer's tables to the model. Which column is the customer id,
> which table is the event log, which columns are noise. That mapping is why
> onboarding takes weeks, and it has to be redone for every customer — because
> a telecom's `subscriber_id` and CDRs look nothing like a SaaS vendor's
> `user_id` and event log.
>
> Churn AI removes that step."

**Action** — scroll the left panel briefly so the three feature bullets are visible.

---

## 0:25 – 0:45 · Onboarding

**Action**
1. Type **Northwind Telecom** into Company name.
2. Click the **Telecom** card.
3. Click **Continue to dashboard**.

> "You tell it who you are and which vertical you're in. That's the entire
> configuration. Notice the URL — each vertical gets its own dashboard."

**Beat** — pause on `/dashboard/telecom` so the URL and the *Telecom retention
overview* heading are readable.

---

## 0:45 – 1:15 · Ingestion and schema discovery

**Action**
1. Point at the dropzone — mention CSV, Excel, multiple files.
2. Click **Run the sample** (uses the bundled Telecom dataset — 4 tables, ~2,900 rows).
3. While the progress panel steps through, narrate.

> "You upload your tables exactly as they are — no pre-joining, no mapping file.
> I'll use the bundled Telecom dataset: subscribers, call records, recharges and
> complaints.
>
> It's resolving the schema, synthesising features and scoring — four stages."

**Beat** — let the *Analysis complete* toast land.

---

## 1:15 – 1:40 · What it worked out on its own

**Action** — scroll to the **AI schema discovery** card.

> "It found the join key — `subscriber_id` — with no help. It classified every
> table: subscribers as the dimension, call records as a time-series event,
> recharges as transactional, complaints as unstructured text. And it discarded
> `sim_imsi_hash` as noise — an identifier that would only add spurious signal.
>
> Nobody configured any of that."

**Beat** — hold 2s on the four schema cards.

---

## 1:40 – 2:10 · The numbers, and why they're trustworthy

**Action** — scroll up to the KPI row, then the Telecom signals card.

> "100 subscribers scored. 67 at risk, 16 critical.
>
> And these are Telecom's own metrics, not generic ones — dropped-call rate for
> the at-risk cohort against the base, port-out enquiries, and the worst region.
> A SaaS workspace shows MRR at risk and login velocity instead."

**Action** — point at the amber **Local engine** badge in the top bar.

> "That badge matters. The Qwen API key we were issued is being rejected, so the
> platform fell back to its offline engine and says so, rather than showing a
> blank screen or passing it off as a model result."

---

## 2:10 – 2:35 · Drivers and the playbook

**Action**
1. Scroll to **What is driving churn**.
2. Then open any **Playbook** in the at-risk table.

> "A probability on its own is useless to a retention agent. Every account
> carries its drivers — long gap since the last recharge, elevated dropped
> calls, port-out complaints — and a playbook: the channel, the action, and the
> message, ready to send."

**Beat** — hold on the drawer showing the gauge, the drivers and the message.

---

## 2:35 – 2:50 · Close

**Action** — back to the KPI row, or the schema card.

> "Same upload, same code path, three verticals. Measured against a known
> churning cohort in the bundled data, it puts 22 of the 25 real churners in its
> top 25 — running entirely offline, in under a tenth of a second.
>
> It's live now, and the repo is public."

**Screen** — end card with the two URLs.

---

## Shot list for the end card

```
Live    https://churnsystem-two.vercel.app
Source  https://github.com/madhubashana112/churnsystem
```

## If you want to show a second vertical (only if under time)

`/dashboard/fintech` after registering a FinTech workspace shows completely
different KPI cards — liquidity drain, dormant accounts, P2P failure streaks —
from the same code path. It's the strongest single proof of domain adaptation,
so use it if you can trim elsewhere.

## Things to avoid on camera

- Don't open `/docs` — the Swagger page is a distraction at this length.
- Don't use the **Qwen** engine toggle; the key in use returns 401 and it will
  deliberately error. **Auto** and **Local** both work.
- The browser console is clean; don't open dev tools unless a judge asks.
