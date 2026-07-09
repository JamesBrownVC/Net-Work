"""Claude tool-use loop for agents, with a deterministic mock fallback so the
whole choreography runs on fixtures without an API key.

Live mode: claude-sonnet-5 agent loops, claude-haiku-4-5 extraction
subcalls, prompt caching on charters, structured output forced through a
strict tool schema (assistant prefills are not supported on Sonnet 5; note
Sonnet 5 runs adaptive thinking by default when `thinking` is omitted).
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from agents.bus import EventBus

AGENT_MODEL = "claude-sonnet-5"
EXTRACT_MODEL = "claude-haiku-4-5"
CHARTERS = Path(__file__).parent / "charters"
MAX_TURNS = 12


def llm_available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def _tool_schema(fn: Callable[..., Any], name: str) -> dict[str, Any]:
    import inspect

    props: dict[str, Any] = {}
    required: list[str] = []
    for pname, param in inspect.signature(fn).parameters.items():
        ptype = "number" if param.annotation is float else "string"
        props[pname] = {"type": ptype}
        if param.default is inspect.Parameter.empty:
            required.append(pname)
    return {
        "name": name,
        "description": (fn.__doc__ or name).strip(),
        "input_schema": {
            "type": "object",
            "properties": props,
            "required": required,
            "additionalProperties": False,
        },
    }


def _report_tool(name: str, model_cls: type[BaseModel]) -> dict[str, Any]:
    schema = model_cls.model_json_schema()
    schema["additionalProperties"] = False
    return {
        "name": name,
        "description": f"Submit the final {name} exactly once.",
        "input_schema": schema,
    }


async def run_agent_loop(
    agent_name: str,
    charter_file: str,
    user_task: str,
    tools: dict[str, Callable[..., Any]],
    report_name: str,
    report_cls: type[BaseModel],
    bus: EventBus,
) -> BaseModel:
    """Tool-use loop: charter as cached system prompt, scoped MCP tools, and a
    forced structured report at the end."""
    import anthropic

    client = anthropic.AsyncAnthropic()
    charter = (CHARTERS / charter_file).read_text(encoding="utf-8")
    system = [{"type": "text", "text": charter, "cache_control": {"type": "ephemeral"}}]
    tool_defs = [_tool_schema(fn, name) for name, fn in tools.items()]
    tool_defs.append(_report_tool(report_name, report_cls))
    messages: list[dict[str, Any]] = [{"role": "user", "content": user_task}]

    for _ in range(MAX_TURNS):
        response = await client.messages.create(
            model=AGENT_MODEL,
            max_tokens=4096,
            system=system,
            tools=tool_defs,
            messages=messages,
        )
        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:
            # nudge the model to file its report through the forced tool
            messages.append({"role": "assistant", "content": response.content})
            messages.append(
                {"role": "user", "content": f"Submit your findings via {report_name} now."}
            )
            continue
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in tool_uses:
            if block.name == report_name:
                bus.emit(agent_name, "done", report=report_name)
                return report_cls.model_validate(block.input)
            bus.asks(agent_name, f"{block.name}({json.dumps(block.input, default=str)})")
            try:
                out = tools[block.name](**block.input)
                bus.receives(agent_name, f"{block.name}: ok")
                content = json.dumps(out, default=str)[:20_000]
                results.append(
                    {"type": "tool_result", "tool_use_id": block.id, "content": content}
                )
            except Exception as exc:  # tool errors go back to the model
                bus.receives(agent_name, f"{block.name}: error {exc}")
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": str(exc),
                        "is_error": True,
                    }
                )
        messages.append({"role": "user", "content": results})

    # out of turns: force the report tool
    response = await client.messages.create(
        model=AGENT_MODEL,
        max_tokens=4096,
        system=system,
        tools=tool_defs,
        tool_choice={"type": "tool", "name": report_name},
        messages=messages,
    )
    block = next(b for b in response.content if b.type == "tool_use")
    return report_cls.model_validate(block.input)


async def extract(prompt: str, schema_cls: type[BaseModel]) -> BaseModel:
    """Haiku extraction subcall with a forced strict tool."""
    import anthropic

    client = anthropic.AsyncAnthropic()
    tool = _report_tool("extraction", schema_cls)
    tool["strict"] = True
    response = await client.messages.create(
        model=EXTRACT_MODEL,
        max_tokens=1024,
        tools=[tool],
        tool_choice={"type": "tool", "name": "extraction"},
        messages=[{"role": "user", "content": prompt}],
    )
    block = next(b for b in response.content if b.type == "tool_use")
    return schema_cls.model_validate(block.input)
