"""Slack bot surface (Bolt for Python, Socket Mode).

Intents are parsed by Haiku when a key is present, else by a deterministic
regex fallback so the bot logic is testable offline. Replies are Block Kit,
always in-thread, never more than one top-level message per request.

Run: python -m surfaces.slack_bot  (needs SLACK_BOT_TOKEN + SLACK_APP_TOKEN)
"""

from __future__ import annotations

import asyncio
import os
import re
from typing import Any

from pydantic import BaseModel

from agents.bus import EventBus
from agents.orchestrator import conquer


class Intent(BaseModel):
    kind: str  # conquer | mark_failed | allocate | unknown
    company: str = ""
    person: str = ""
    target: str = "CRO"
    hours: float = 8.0
    eur: float = 900.0


_DOMAINS = {"novapay": "novapay.io"}


def parse_intent_fallback(text: str) -> Intent:
    """Deterministic intent parsing used offline and as the Haiku fallback."""
    low = text.lower()
    if match := re.search(r"mark\s+intro\s+failed\s+(.+)", low):
        return Intent(kind="mark_failed", person=match.group(1).strip(), company="novapay.io")
    if match := re.search(r"conquer\s+([\w.-]+)", low):
        raw = match.group(1).strip()
        return Intent(kind="conquer", company=_DOMAINS.get(raw, raw if "." in raw else raw + ".io"))
    if "allocate" in low or "plan my week" in low:
        return Intent(kind="allocate")
    return Intent(kind="unknown")


async def parse_intent(text: str) -> Intent:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return parse_intent_fallback(text)
    from agents.client import extract

    try:
        result = await extract(
            "Parse this revenue-team request into an intent. kinds: conquer "
            "(attack a company; set company to its domain), mark_failed (an intro "
            "failed; set person), allocate (weekly plan), unknown. "
            f"Request: {text}",
            Intent,
        )
        return result  # type: ignore[return-value]
    except Exception:
        return parse_intent_fallback(text)


def _plan_blocks(plan_markdown: str) -> list[dict[str, Any]]:
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": plan_markdown[:2900]}},
        {
            "type": "actions",
            "elements": [
                {"type": "button", "text": {"type": "plain_text", "text": "Open Theater"},
                 "action_id": "open_theater", "url": "http://localhost:3000"},
                {"type": "button", "text": {"type": "plain_text", "text": "Generate deck"},
                 "action_id": "generate_deck"},
                {"type": "button", "text": {"type": "plain_text", "text": "Mark step done"},
                 "action_id": "mark_step_done"},
            ],
        },
    ]


async def handle_request(text: str) -> tuple[str, list[dict[str, Any]]]:
    """Shared handler: returns (fallback_text, blocks). Used by Slack and tests."""
    intent = await parse_intent(text)
    if intent.kind == "conquer":
        plan = await conquer(target=intent.company, objective=intent.target, bus=EventBus())
        return f"Battle plan for {intent.company}", _plan_blocks(plan.to_markdown())
    if intent.kind == "mark_failed":
        from engines import fortress

        rerouted = fortress.fail_edge(intent.company, intent.target, "us", intent.person)
        lines = [f"Rerouted around failed intro to {intent.person}:"]
        for i, path in enumerate(rerouted["paths"], 1):
            chain = " -> ".join(["us"] + [s["to"] for s in path["steps"]])
            lines.append(f"{i}. {chain} (R={path['R']}, EV={path['EV']})")
        text_out = "\n".join(lines)
        return text_out, [{"type": "section", "text": {"type": "mrkdwn", "text": text_out}}]
    if intent.kind == "allocate":
        from engines import allocator

        result = allocator.solve(intent.hours, intent.eur)
        lines = [f"*This week's plan* ({result['budget']['hours_used']}h):"]
        lines += [f"- {i['account']}: {i['action']} (EUR {i['U_eur']})" for i in result["plan"]]
        text_out = "\n".join(lines)
        return text_out, [{"type": "section", "text": {"type": "mrkdwn", "text": text_out}}]
    return (
        "Try: `conquer NovaPay`, `mark intro failed <name>`, or `allocate`.",
        [{"type": "section", "text": {"type": "mrkdwn",
          "text": "Try: `conquer NovaPay`, `mark intro failed <name>`, or `allocate`."}}],
    )


def main() -> None:
    from slack_bolt import App
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    app = App(token=os.environ["SLACK_BOT_TOKEN"])

    @app.event("app_mention")
    def on_mention(body: dict, say: Any) -> None:  # type: ignore[no-untyped-def]
        event = body["event"]
        text = re.sub(r"<@[^>]+>", "", event.get("text", "")).strip()
        fallback, blocks = asyncio.run(handle_request(text))
        # one top-level message per request, threaded under the mention
        say(text=fallback, blocks=blocks, thread_ts=event.get("thread_ts") or event["ts"])

    @app.action("generate_deck")
    def on_deck(ack: Any, body: dict, say: Any) -> None:  # type: ignore[no-untyped-def]
        ack()
        from surfaces.gamma import generate_deck

        thread = body["message"].get("thread_ts") or body["message"]["ts"]
        say(text="Generating deck via Gamma...", thread_ts=thread)
        plan_text = body["message"].get("text", "Battle plan")
        result = asyncio.run(generate_deck(plan_text))
        say(text=f"Deck [{result['status']}]: {result.get('gammaUrl', '-')} "
                 f"(pptx: {result.get('exportUrl', '-')})", thread_ts=thread)

    @app.action("open_theater")
    def on_theater(ack: Any) -> None:  # type: ignore[no-untyped-def]
        ack()

    @app.action("mark_step_done")
    def on_done(ack: Any, body: dict, say: Any) -> None:  # type: ignore[no-untyped-def]
        ack()
        say(text="Step marked done.",
            thread_ts=body["message"].get("thread_ts") or body["message"]["ts"])

    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()


if __name__ == "__main__":
    main()
