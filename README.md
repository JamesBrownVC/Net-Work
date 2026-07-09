# ACR: Account Conquest Room

Phase 1: the Connection Fabric. Eight sources feed one unified SQLite store,
and every connector is exposed to Claude as an MCP server over identical code
paths. Mock-first: a fresh clone with an empty `.env` goes fully green.

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
