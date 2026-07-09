# ACR: Account Conquest Room

AI-native revenue intelligence platform. Product spec: [ACR_PRD.md](./ACR_PRD.md).
The retired Next.js prototype lives at [archive/nextjs-old-start/](./archive/nextjs-old-start/);
all backend work is Python. Layer map: [ARCHITECTURE_MAPPING.md](./ARCHITECTURE_MAPPING.md).

Layer 0/1 is the Connection Fabric: eight sources feed one unified SQLite
store, and every connector is exposed to Claude as an MCP server over
identical code paths. Mock-first: a fresh clone with an empty `.env` goes
fully green. On top of it sit the engines (warmth, allocator, fortress), the
Claude agents + orchestrator, and the surfaces (CLI, web view, Slack bot,
Gamma decks).

## Setup

Requires Python 3.12+ (built and tested on 3.13).

```
make setup      # venv + pip install -e ".[dev]"
make seed       # deterministic demo world into fixtures/
make ingest     # pull -> normalize -> upsert into acr.db
make status     # connector | mode | health | last_pull | rows
make test       # pytest: contract tests per connector + store + MCP
make lint       # ruff
```

On Windows without make, substitute `.venv/Scripts/python.exe scripts/seed.py`
and friends; the Makefile targets are one command each.

## Mock vs live

`MOCK_MODE=true` is the default. Every connector runs fully from deterministic
fixtures under `fixtures/<name>/`. Live mode is per-connector opt-in: set
`MOCK_MODE=false` AND the connector's credentials (see `.env.example`). A
connector without credentials stays in mock mode even when the global flag is
off, so partial live setups never break the fabric.

For FullEnrich, Sillage, Gradium, and Gamma the base URLs live in
`config/apis.yaml` with `verified: false`. A human must check each endpoint
against `docs_url` and flip the flag before trusting a live adapter; until
then the live paths raise NotImplementedError with instructions.

## Adding credentials per connector

| connector  | env keys                          | notes                          |
|------------|-----------------------------------|--------------------------------|
| gmail      | GOOGLE_TOKEN_PATH                 | scope gmail.readonly           |
| gcal       | GOOGLE_TOKEN_PATH                 | plus GOOGLE_CALENDAR_ID        |
| slack      | SLACK_BOT_TOKEN                   | channels:history               |
| notion     | NOTION_TOKEN, NOTION_DATABASE_ID  | internal integration           |
| fullenrich | FULLENRICH_API_KEY                | docs.fullenrich.com            |
| sillage    | SILLAGE_API_KEY                   | getsillage.com                 |
| gradium    | GRADIUM_API_KEY                   | EU region, 300s session cap    |
| mockcrm    | none                              | the fixture IS the source      |

## MCP

Each connector is served with a thin generic wrapper (`fabric/mcp/serve.py`)
so direct Python calls and MCP calls hit the same class:

```
python -m fabric.mcp.serve fullenrich     # start one server (stdio)
fabric mcp list-tools fullenrich          # health, pull, enrich_company, lookalikes
```

## CLI

```
fabric status
fabric pull gcal --since 90d
fabric ingest --all
fabric mcp list-tools sillage
```

## Adding a ninth connector in under 30 minutes

1. Drop a fixture at `fixtures/<name>/<file>.json` (a list of payload dicts
   with ISO `ts` fields where relevant). Extend `scripts/seed.py` if it should
   be part of the demo world.
2. Create `fabric/connectors/<name>.py`: subclass `FixtureConnector`, set
   `name`, `fixture_file`, `record_kind`, `live_env_keys`, and implement
   `normalize(raw) -> list[Entity]` mapping payloads to `fabric.schema`
   entities with deterministic ids (`person:<email>`, `company:<domain>`,
   `interaction:<source-id>`).
3. Register the class in `fabric/registry.py` (`CONNECTOR_CLASSES`); add any
   connector-specific methods to `EXTRA_TOOLS` to expose them over MCP.
4. Add `tests/test_contract_<name>.py` calling `tests.conftest.contract_check`.
That is the whole surface: pull, normalize, health, MCP, and CLI all come from
the base class and registry.

## Design rules carried through the codebase

- One protocol (`fabric/protocol.py`), no per-source special cases.
- Explainability in the schema: every probabilistic field has a
  `components_json` sibling (warmth, org_edges); no naked scores.
- Idempotent upserts on natural keys; re-running ingest never duplicates.
- Never invent API endpoints: unverified adapters stay stubbed and say so.

## Interaction content analysis (relationship substance)

Beyond interaction *metadata* (recency, frequency, reciprocity), ACR reads the
actual *content* of Slack messages, emails, Notion notes and call transcripts.
`engines/content.py` runs a `claude-haiku-4-5` pass (deterministic keyword
fallback with no key) that extracts, per interaction and cited by its id, into
the `interaction_context` table: sentiment (positive/neutral/negative/tense),
topics, commitments, risk flags, and champion signals.

This folds into two places:
- **Warmth** gains two config-driven components (`content_sentiment`,
  `champion` in `config/warmth.yaml`), visible in `warmth.components_json`.
- **The allocator's** `claude_adjustment()` now reasons over the content
  summary, not just metadata.

Run it with `scripts/ingest.py --analyze` (or `make ingest` / `make demo`).
Proof it is not cosmetic: `Cargolux Digital` keeps a healthy email cadence but
its recent threads have soured, so its content sentiment is `-0.47`; account
warmth drops from `0.909` (metadata only) to `0.815` (with content), and the
Relationship agent flags it as a churn risk that the old ARR/silence rules
missed entirely. See `tests/test_content.py`.

## Orbit pre-call brief (web)

`surfaces/orbit/` is the Orbit pre-call brief UI, wired to real backend data
and served by the web surface. Start it and open a brief per account:

```
python -m surfaces.web
# http://localhost:8787/orbit?account=novapay.io   (healthy, warm)
# http://localhost:8787/orbit?account=cargoluxdigita.example   (at risk, cooled)
# http://localhost:8787/orbit?account=axa.fr        (insurer, Sillage signals)
```

`GET /api/brief?account=<domain>` (in `agents/brief.py`) assembles the
MeetingBrief from real data: warmth + the Part A content signal (sentiment,
champion signals, risk flags, each with its evidence interaction id), the
allocator's recommended action and euro value, references, and account signals.
Account signals come from Sillage for the 13 tracked insurers (AXA, MAIF,
MACIF, …) via `fabric/sillage_provider.py`, which prefers the live Sillage API
(`SILLAGE_API_KEY`, `MOCK_MODE=false`) and falls back to cached data otherwise;
customer accounts use the store's own signals. The "Export one-pager" button
generates a Gamma deck (`GET /api/deck`). The "Plan of attack — the castle"
section is a deliberately empty, labeled slot for the fortress conquest map;
its data contract (the `fortress.solve()` path JSON) is documented in the
markup so wiring it in later is a drop-in. See `tests/test_brief.py`.

## Demo

```
make demo            # seed + ingest + full agent run on fixtures
fabric demo --target novapay.io --objective CRO
```

Prints the live agent choreography (Network, Conquest, Relationship,
Allocator on the event bus), the Unified Battle Plan, and a Gamma deck link
(mock URL without GAMMA_API_KEY; real generation with one). With
ANTHROPIC_API_KEY set, the agents run as claude-sonnet-4-6 tool-use loops
with claude-haiku-4-5 extraction; without it, deterministic mock twins follow
the same tool calls and schemas. The Slack bot (`python -m surfaces.slack_bot`
with SLACK_BOT_TOKEN + SLACK_APP_TOKEN) answers `@ConquestRoom conquer
NovaPay`, `mark intro failed <name>`, and `allocate` in-thread with buttons.

## Phase gates

`warmth` and `org_edges` tables exist but are filled by Phase 2 engines.
`config/actions.yaml` is a Phase 2 placeholder. NOTE: `ACR_PRD.md` is
referenced by later phases and must be present in the repo root before
starting Phase 2.
