# Architecture mapping: ACR -> Net-Work (architecture-migration-python)

Both codebases implement the same layered "fabric" architecture from the
master prompt pack; the target branch held the first Phase 1 slice (schema,
store, mockcrm only) and ACR held the completed superset. The merge keeps
the branch's layout and conventions and lands ACR's implementation into it,
with full ACR commit history preserved (no squash).

## Layer mapping

| ACR module | Target location | Notes |
|---|---|---|
| `fabric/protocol.py` | `fabric/protocol.py` | ACR version kept; adopted the branch's `pull(since=None)` default. The branch's `RawRecord.source_id`/`fetched_at` fields were NOT adopted (ACR uses `kind` + payload-embedded ids across 8 connectors); noted as a seam below. |
| `fabric/schema.py` | `fabric/schema.py` | ACR version (Literal types). Branch used Enums + `extra="forbid"`; behavior-equivalent, not worth churning 8 connectors. |
| `fabric/store.py` | `fabric/store.py` | ACR version, including source-priority person upserts. Branch's per-entity natural-key/uuid5 upserts are the noted ambiguity: arguably cleaner, but swapping would touch every connector and the priority guard. Left as a seam. |
| `fabric/connectors/*` (8) | `fabric/connectors/*` | Superset replaces the branch's single mockcrm. |
| `fabric/mcp/serve.py` | `fabric/mcp/serve.py` | MCP wrappers land unchanged; `python -m fabric.mcp.serve <connector|engines>` verified post-merge. |
| `engines/*` (warmth, allocator, fortress) | `engines/*` | Pure-logic layer, net-new to the branch. No math changed. `config/*.yaml` numeric values untouched. |
| `agents/*` (charters, loops, bus, orchestrator) | `agents/*` | Application/use-case layer, net-new. Replaces the archived TS `archive/nextjs-old-start/src/{agents,orchestrator}` conceptually; the archive stays frozen as reference. |
| `surfaces/*` (slack_bot, gamma, web) | `surfaces/*` | Presentation layer, net-new. |
| `fabric/cli.py` | `fabric/cli.py` | Typer CLI (`fabric demo` entry point unchanged). |
| `scripts/`, `fixtures/`, `tests/` | same paths | ACR supersets replace the branch's slice; the branch's `fixtures/mockcrm/accounts.json` removed (superseded by companies/contacts/deals/sellers.json from `scripts/seed.py`). Branch's two test files are subsumed by ACR's contract + store tests. |
| `ACR_PRD.md` | kept at repo root | Was missing from ACR; authoritative narrative spec. Note: it contains no numbered 6.x/7.x tables, so the hand-seeded values in `config/actions.yaml`, `config/uplifts.yaml`, `config/fortress.yaml` remain operative. |

## Tooling reconciliation (branch conventions adopted)

- Build backend: **hatchling** (was setuptools in ACR).
- Pytest: branch's `pythonpath = ["."]` adopted alongside `testpaths`.
- Ruff: identical on both sides (line-length 100, py312) — unchanged.
- Dependency manager: plain pip / `make setup` on both sides; ACR's full
  dependency list (fastmcp, typer, httpx, ortools, networkx, slack-bolt,
  anthropic, pyyaml) carried over.

## Known seams (deliberate, non-blocking)

1. **Upsert style**: ACR's PK-string merge vs branch's natural-key/uuid5
   per-entity upserts. Kept ACR's; a later refactor could adopt uuid5 ids
   behind the same `upsert()` facade without touching connectors.
2. **RawRecord shape**: branch's frozen model with `source_id`/`fetched_at`
   is stricter; adopting it means touching every connector's pull(). Deferred.
3. **Schema enums**: branch's Enum-based entity fields vs ACR's Literals.
   Wire-compatible; unify opportunistically.
