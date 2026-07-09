"""Typer CLI: fabric status | pull | ingest | mcp list-tools."""

from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta

import typer
from sqlalchemy.orm import Session

from fabric import registry, store

app = typer.Typer(help="ACR Connection Fabric CLI", no_args_is_help=True)
mcp_app = typer.Typer(help="MCP inspection", no_args_is_help=True)
app.add_typer(mcp_app, name="mcp")


def _parse_since(value: str | None) -> datetime | None:
    if not value:
        return None
    match = re.fullmatch(r"(\d+)d", value.strip())
    if match:
        return datetime.now() - timedelta(days=int(match.group(1)))
    return datetime.fromisoformat(value)


@app.command()
def status() -> None:
    """Table: connector | mode | health | last_pull | rows."""
    engine = store.get_engine()
    with Session(engine) as session:
        rows = registry.status_rows(session)
        counts = store.table_counts(session)
    header = f"{'connector':12s} {'mode':6s} {'health':7s} {'last_pull':20s} {'rows':>6s}"
    typer.echo(header)
    typer.echo("-" * len(header))
    for r in rows:
        typer.echo(
            f"{r['connector']:12s} {r['mode']:6s} {r['health']:7s} "
            f"{r['last_pull']:20s} {r['rows']:>6s}"
        )
    typer.echo("\nstore: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))


@app.command()
def pull(
    name: str,
    since: str | None = typer.Option(None, "--since", help="ISO datetime or Nd, e.g. 90d"),
) -> None:
    """Pull raw records from one connector and print a summary."""
    connector = registry.get(name)
    records = connector.pull(_parse_since(since))
    typer.echo(f"{name}: {len(records)} raw records")
    for rec in records[:5]:
        ts = rec.payload.get("ts") or rec.payload.get("call_ts") or "-"
        title = (
            rec.payload.get("subject")
            or rec.payload.get("title")
            or rec.payload.get("text", "")[:40]
            or rec.payload.get("name", "")
        )
        typer.echo(f"  [{rec.kind}] {ts} {title}")
    if len(records) > 5:
        typer.echo(f"  ... and {len(records) - 5} more")


@app.command()
def ingest(
    all_: bool = typer.Option(False, "--all", help="Ingest every connector"),
    name: str | None = typer.Argument(None),
) -> None:
    """Pull -> normalize -> upsert."""
    from scripts.ingest import ingest as run_ingest

    names = None if all_ or not name else [name]
    for cname, n in run_ingest(names).items():
        typer.echo(f"{cname:12s} upserted {n} entities")


@app.command()
def warmth(
    company: str = typer.Option(..., "--company", help="Company domain, e.g. novapay.io"),
) -> None:
    """Heatmap-ready warmth table for a company."""
    from sqlalchemy.orm import Session as _Session

    from engines import warmth as warmth_engine

    with _Session(store.get_engine()) as session:
        rows = warmth_engine.company_heatmap(session, company)
    if not rows:
        typer.echo(f"no people found for {company}")
        raise typer.Exit(1)
    header = f"{'person':22s} {'title':20s} {'dept':12s} {'sen':4s} {'warmth':>7s}  components"
    typer.echo(header)
    typer.echo("-" * len(header))
    for r in rows:
        comp = ", ".join(f"{k}={v}" for k, v in r["components"].items())
        typer.echo(
            f"{r['person'][:22]:22s} {r['title'][:20]:20s} {r['dept'][:12]:12s} "
            f"{r['seniority']:4s} {r['warmth']:7.3f}  {comp}"
        )


@app.command()
def allocate(
    hours: float = typer.Option(8.0, "--hours"),
    budget: float = typer.Option(900.0, "--budget", help="Euro budget"),
    greedy: bool = typer.Option(False, "--greedy", help="Greedy fallback instead of CP-SAT"),
) -> None:
    """MCKP plan: account | action | U_eur, plus budget usage and shadow price."""
    from engines import allocator

    result = allocator.solve(hours, budget, greedy=greedy)
    typer.echo(f"{'account':22s} {'action':20s} {'U_eur':>10s}")
    typer.echo("-" * 54)
    for item in result["plan"]:
        typer.echo(f"{item['account'][:22]:22s} {item['action']:20s} {item['U_eur']:>10.2f}")
    b = result["budget"]
    typer.echo(
        f"\nbudget: {b['hours_used']}/{b['hours_budget']}h, "
        f"EUR {b['eur_used']}/{b['eur_budget']}  solver={result['solver']}"
    )
    typer.echo(f"shadow_price_eur_per_hour: {result['shadow_price_eur_per_hour']}")


@app.command()
def conquer(
    company: str = typer.Argument(..., help="Target company domain, e.g. novapay.io"),
    target: str = typer.Option(..., "--target", help="Target person title, e.g. CRO"),
    v_deal: float = typer.Option(50_000.0, "--v-deal"),
    fail: str | None = typer.Option(
        None, "--fail", help="'From Name->To Name' edge to fail before solving"
    ),
) -> None:
    """Top-3 intro paths with R, effort, EV; --fail reroutes around a dead edge."""
    from engines import fortress

    if fail:
        from_p, to_p = (s.strip() for s in fail.split("->", 1))
        result = fortress.fail_edge(company, target, from_p, to_p, v_deal)
        typer.echo(f"failed edge: {from_p} -> {to_p}\n")
    else:
        result = fortress.solve(company, target, v_deal)
    typer.echo(f"target: {result['target']['name']} ({result['target']['title']})")
    for i, path in enumerate(result["paths"], 1):
        chain = " -> ".join(["us"] + [s["to"] for s in path["steps"]])
        typer.echo(f"\npath {i}: {chain}")
        typer.echo(f"  R={path['R']}  effort={path['effort']}  EV={path['EV']}")
        for s in path["steps"]:
            typer.echo(f"    {s['from']} -> {s['to']} ({s['to_title']}) p={s['p']}")


@app.command()
def demo(
    target: str = typer.Option("novapay.io", "--target"),
    objective: str = typer.Option("CRO", "--objective"),
    deck: bool = typer.Option(True, "--deck/--no-deck", help="Also generate a Gamma deck"),
) -> None:
    """Full demo run: agent choreography, Unified Battle Plan, Gamma deck."""
    import asyncio

    from agents.bus import EventBus
    from agents.orchestrator import conquer
    from surfaces.gamma import generate_deck

    bus = EventBus()
    bus.subscribe(lambda e: typer.echo(f"  [{e.agent:12s}] {e.kind:11s} "
                                       + ", ".join(f"{k}={v}" for k, v in e.payload.items())))
    typer.echo(f"=== ACR run: conquer {target} (objective: {objective}) ===\n")

    async def run() -> None:
        plan = await conquer(target=target, objective=objective, bus=bus)
        typer.echo("\n" + plan.to_markdown())
        if deck:
            result = await generate_deck(plan.to_markdown())
            typer.echo(f"\ndeck [{result['status']}]: {result.get('gammaUrl', '-')}")

    asyncio.run(run())


@mcp_app.command("list-tools")
def list_tools(name: str) -> None:
    """List MCP tools exposed by a connector's server."""
    from fabric.mcp.serve import build_engines_server, build_server

    server = build_engines_server() if name == "engines" else build_server(registry.get(name))
    tools = asyncio.run(server.list_tools())
    for tool in sorted(tools, key=lambda t: t.name):
        typer.echo(tool.name)


if __name__ == "__main__":
    app()
