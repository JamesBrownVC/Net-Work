# ACR / Orbit — Demo Walkthrough

One-command start, then a guided click-through. Everything runs on
deterministic fixtures with **zero API keys required**.

## 1. Start

```bash
cd Net-Work
.venv/Scripts/python.exe scripts/seed.py         # regenerate fixtures (optional, deterministic)
.venv/Scripts/python.exe scripts/ingest.py --analyze   # load DB + run content analysis
.venv/Scripts/python.exe -m surfaces.web         # -> http://localhost:8787
```

Open **http://localhost:8787/orbit** in a browser.

Sanity check anytime: `.venv/Scripts/python.exe -m pytest -q` (49 tests, should be all green).

## 2. The story: three roles, one relationship graph

Everything below is computed from the same seeded world: **Atlas Revenue OS**
(us) selling to 25 customer accounts, with **NovaPay** as a healthy expansion
target and **Cargolux Digital** as a planted at-risk account (cadence looks
fine, content has soured — the point of the whole content-analysis layer).

### Stop 1 — Schedule (`/orbit`)

Lands on your day: upcoming calls grouped **Today / Tomorrow / Saturday**,
each card showing the person, their title, a live **warmth score**, and the
real purpose of the call. This isn't a static calendar — every slot resolves
to a real person and a real warmth number pulled from the relationship graph.

**Say:** *"This is a rep's actual queue — not a CRM dump, a prioritized list
of who to prep for and why."*

Click **Elsa Jansen — 14:00 — NovaPay** (or any slot).

### Stop 2 — Pre-call brief, healthy account (`/orbit/brief?person=elsa.jansen@novapay.io`)

- Green **Healthy** badge, **+0.63 sentiment**, warmth ~100%
- Champion signal cites **Camille Nguyen by name**, with the source
  interaction id shown next to it — nothing here is invented, every line
  traces to a real message
- Scroll to the bottom: **"Ask them to introduce you to"**
  → **Aya Rossi (CRO)** — *"their manager, the fastest line to a decision"* — **p 0.80**
  → then CEO, COO, CFO ranked by reachability

**Say:** *"The system doesn't stop at 'this contact is warm' — it tells you
who to ask them to open the next door to, and ranks it by how likely that
intro actually lands."*

Go back (`/orbit`), click **Nora Eriksen — Tomorrow 15:00 — Cargolux Digital**.

### Stop 3 — Pre-call brief, at-risk account

- Red **At risk** badge
- **95% warmth but −0.70 sentiment** — say this line out loud: *"the cadence
  looks completely healthy, this account emails on schedule — but the actual
  content of recent messages has cooled. Warmth alone would have missed
  this entirely."*
- Every risk flag cites its source: `interaction:gmail:87`,
  `interaction:slack:132` — click-verifiable, not a vibe score

Scroll to the bottom of the page: the **castle** — a labeled, intentionally
empty slot for the fortress conquest-path visualization. Point at it and say
it's wired for later (documented data contract in the HTML comment), not
built yet — *"we didn't fake this one."*

### Stop 4 — Book of Business (`/orbit/book-of-business.html`)

Full portfolio, 25 accounts, ranked **at-risk first** by the same
sentiment-anchored logic (not just silence-days). Cargolux surfaces at the
top for the same reason as Stop 3.

### Stop 5 (optional) — Fortress Plan tab

Static plan-of-attack mockup — same navigation, not yet wired to the
`fortress.solve()` engine (see castle slot above).

## 3. If asked "what's real vs. mocked"

| Piece | Status |
|---|---|
| Warmth score | Real: recency + frequency + reciprocity + seniority + **content sentiment + champion signal** (config-driven weights in `config/warmth.yaml`) |
| Content analysis (sentiment/champion/risk) | Real Haiku pass over interaction text (`engines/content.py`); falls back to deterministic keyword rules with no API key so the demo never breaks |
| Onward-intro ranking | Real org-graph traversal (`agents/brief.py`), ranked by seniority × edge reachability |
| Sillage insurer signals (AXA, MAIF, …) | Live-API-preferred, cached-fallback (`fabric/sillage_provider.py`) — real integration pattern, not hardcoded |
| Gamma "Export one-pager" | Calls the real Gamma API when a key is present |
| Fortress castle map | **Honestly not built** — labeled empty slot, documented contract |

## 4. Command reference

```bash
.venv/Scripts/python.exe -m surfaces.web          # web UI (Orbit) on :8787
.venv/Scripts/python.exe -m fabric.cli demo       # terminal: agent choreography + full Battle Plan
.venv/Scripts/python.exe -m pytest -q             # 49 tests
.venv/Scripts/python.exe -m ruff check .          # lint
```

## 5. URLs

- `http://localhost:8787/orbit` — schedule (start here)
- `http://localhost:8787/orbit/brief?person=elsa.jansen@novapay.io` — healthy brief
- `http://localhost:8787/orbit/brief?person=nora.eriksen@cargoluxdigita.example` — at-risk brief
- `http://localhost:8787/orbit/book-of-business.html` — portfolio
- `http://localhost:8787/orbit/fortress-plan.html` — plan-of-attack mockup
