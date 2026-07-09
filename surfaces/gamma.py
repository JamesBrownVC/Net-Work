"""Gamma deck generation: battle plan markdown -> presentation (pptx export).

POST /v1.0/generations with X-API-KEY (GAMMA_API_KEY, promo GAMMA-STATIONF),
then poll GET /v1.0/generations/{id} every 5s until completed. Fired async so
it never blocks a Slack reply; without a key it returns a mock result so the
demo path stays green. Base URL lives in config/apis.yaml (verified: false)."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx
import yaml

from fabric.protocol import REPO_ROOT

POLL_SECONDS = 5
MAX_POLLS = 60


def _base_url() -> str:
    cfg = yaml.safe_load((REPO_ROOT / "config" / "apis.yaml").read_text(encoding="utf-8"))
    return cfg["gamma"]["base_url"]


async def generate_deck(battle_plan_markdown: str) -> dict[str, Any]:
    """Returns {status, gammaUrl, exportUrl}. Mock without GAMMA_API_KEY."""
    api_key = os.getenv("GAMMA_API_KEY")
    if not api_key:
        return {
            "status": "mock",
            "gammaUrl": "https://gamma.app/docs/mock-battle-plan",
            "exportUrl": "https://gamma.app/export/mock-battle-plan.pptx",
        }
    async with httpx.AsyncClient(base_url=_base_url(), timeout=30) as client:
        response = await client.post(
            "/generations",
            headers={"X-API-KEY": api_key},
            json={
                "inputText": battle_plan_markdown,
                "textMode": "preserve",
                "format": "presentation",
                "exportAs": "pptx",
            },
        )
        response.raise_for_status()
        generation_id = response.json()["generationId"]
        for _ in range(MAX_POLLS):
            await asyncio.sleep(POLL_SECONDS)
            poll = await client.get(f"/generations/{generation_id}",
                                    headers={"X-API-KEY": api_key})
            poll.raise_for_status()
            data = poll.json()
            if data.get("status") == "completed":
                return {
                    "status": "completed",
                    "gammaUrl": data.get("gammaUrl"),
                    "exportUrl": data.get("exportUrl"),
                }
        return {"status": "timeout", "generationId": generation_id}


def fire_and_forget(battle_plan_markdown: str, on_done: Any = None) -> asyncio.Task[Any]:
    """Kick off generation without blocking; optional completion callback
    (e.g. posting gammaUrl back to a Slack thread)."""

    async def run() -> dict[str, Any]:
        result = await generate_deck(battle_plan_markdown)
        if on_done is not None:
            on_done(result)
        return result

    return asyncio.ensure_future(run())
