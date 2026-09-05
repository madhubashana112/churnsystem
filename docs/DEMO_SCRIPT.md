# Demo Video — narration script and recording guide

**Live URL to record against:** https://churnsystem-two.vercel.app
**Limit:** 3 minutes. Both scripts below run ~70 seconds, leaving room to slow down.

---

## ⚠ Read this before recording

The original draft script contained three claims that the running system
contradicts on screen. A judge watching the video will see the mismatch, so they
are corrected below.

| Draft said | Reality |
|---|---|
| "estimate churn risk using a **machine-learning model**" | There is no trained ML model in this repository — no scikit-learn, XGBoost or PyTorch, no serialised model file. Scoring is a deterministic, explainable engine that ranks each customer against the cohort, with an LLM layer above it. |
| "the system **uses Alibaba Cloud Qwen**" to recommend the action | Qwen is fully implemented, but the hosted prototype has no API key, so it runs the offline engine. The dashboard states this plainly: *"No Qwen API key is configured, so analyses run on the local engine."* |
| "we can **enter** customer information" | There is no per-customer entry form. You upload tables (CSV or Excel), or click **Run the sample**. |

Calling a rules engine "machine learning" is the kind of thing a technical judge
will ask about, and the answer is worse than just describing it accurately —
what the system actually does is more impressive than the generic claim.

---

## Which version to record

**→ Use Version A** if you record today, as the deployment stands.

**→ Use Version B** if you first add a working Qwen key to Vercel. That makes
the original wording true, and it is the stronger demo. See *Enabling Qwen* at
the bottom. **Verify the badge reads "Qwen AI" before recording** — do not
narrate Version B over a screen that says "Local engine."

---

## Version A — accurate to the current deployment

> Hello, this is our AI-powered Customer Churn Prevention System.
>
> The problem we address is that businesses usually identify customers who are
> about to leave only after it is too late — and that every churn tool has to be
> reconfigured by a data engineer for each customer's data before it can say
> anything at all.
>
> **[Screen: onboarding page]**
> You tell it your company name and your industry. That is the entire
> configuration.
>
> **[Screen: click Telecom → Continue → Run the sample]**
> Then you give it your raw tables, exactly as they are. No pre-joining, no
> mapping file.
>
> **[Screen: schema discovery card]**
> The platform works out the schema by itself — it found the join key,
> `subscriber_id`, classified every table, and discarded an identifier column as
> noise. That is the step that normally takes a data engineer weeks.
>
> **[Screen: KPI row and Telecom signals]**
> It scored 100 subscribers and surfaced this vertical's own metrics —
> dropped-call rate, port-out enquiries, the worst-performing region. A SaaS
> workspace shows revenue at risk and login velocity instead, from the same code.
>
> **[Screen: point at the amber engine badge]**
> Our architecture uses Alibaba Cloud Qwen as the reasoning layer for schema
> resolution and churn scoring, with a deterministic offline engine behind it.
> Here you can see that fallback working, and the platform tells you exactly
> which engine produced the numbers rather than hiding it.
>
> **[Screen: open a Playbook]**
> Every at-risk account arrives with its drivers and a retention playbook — the
> channel, the action, and the message, ready to send.
>
> This moves businesses from reactive retention to a proactive, personalised
> approach. Our source code and documentation are public in the repository.
> Thank you.

---

## Version B — record this only with a working Qwen key

Identical to Version A, except replace the engine-badge paragraph with:

> **[Screen: point at the Qwen AI badge]**
> When an account is scored, Alibaba Cloud Qwen acts as the reasoning layer — it
> resolves the schema and produces the churn assessment and a personalised
> retention recommendation for each customer.

Everything else stays the same.

---

## Shot list

| Time | Screen | Action |
|---|---|---|
| 0:00 | Landing page | Hold; scroll the left panel slightly |
| 0:15 | Onboarding form | Type "Northwind Telecom", click **Telecom** |
| 0:22 | — | Click **Continue to dashboard** |
| 0:28 | `/dashboard/telecom` | Click **Run the sample**, let the progress panel run |
| 0:40 | Schema discovery card | Scroll to it, hold 3s |
| 0:52 | KPI row + Telecom signals | Scroll up, hold 4s |
| 1:02 | Engine badge (top right) | Point/zoom |
| 1:12 | At-risk table → **Playbook** | Open the drawer, hold 4s |
| 1:20 | End card | Show both URLs |

**End card text**

```
Live    https://churnsystem-two.vercel.app
Source  https://github.com/madhubashana112/churnsystem
```

---

## How to record it on Windows 11

**Screen capture — Xbox Game Bar (built in)**
1. Open the site in a browser, ideally an incognito window at 1440×900.
2. Press `Win + G`, then the record button (or `Win + Alt + R` to start directly).
3. Recording saves to `Videos\Captures`.

**Voice-over — two options**

*Record your own voice:* in Game Bar, enable the microphone before recording
(`Win + Alt + M` toggles it), and narrate live while you click through.

*Or use text-to-speech:* **Clipchamp** ships with Windows 11 and has an AI
voice-over feature.
1. Open Clipchamp → import your screen recording.
2. Left sidebar → **Text to speech**.
3. Paste one paragraph of the script at a time, pick a voice, generate.
4. Drag each audio clip onto the timeline under the matching section.
5. Export at 1080p.

Recording silently and adding text-to-speech afterwards is usually easier to get
right than narrating live, because you can re-time the clicks to the audio
instead of the other way round.

---

## Enabling Qwen before you record (for Version B)

The hosted prototype has no API key, so it runs the offline engine. To switch it
to the real Qwen path:

1. Get a valid DashScope API key from Alibaba Cloud Model Studio.
   (The key currently in the local `api_key.env` is rejected with `401`.)
2. In the Vercel dashboard → project **churnsystem** → **Settings** →
   **Environment Variables**, add:
   - Name: `DASHSCOPE_API_KEY`
   - Value: your key
   - Environment: Production
3. Redeploy (Deployments → latest → **Redeploy**).
4. Confirm before recording: the badge should read **Qwen AI**, and
   `https://churnsystem-two.vercel.app/api/v1/engine/status` should report
   `"qwen_available": true`.

Add the key yourself in the Vercel dashboard — do not paste API keys into chat.

---

## Do not do these on camera

- **Do not click the Qwen engine toggle** unless a valid key is configured — it
  deliberately returns an error rather than falling back, and that is by design.
- Do not open `/docs`; the Swagger page is a distraction at this length.
- No need for dev tools — the browser console is clean.
