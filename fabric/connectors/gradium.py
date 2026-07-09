"""Gradium connector: call transcription into transcripts.

Live adapter: Gradium REST speech-to-text, EU region, GRADIUM_API_KEY (promo
GTM-HACK). Sessions cap at 300 seconds, so longer files must be chunked and
stitched by offset. Objection extraction is Claude's job in Phase 3; this
connector stores raw text with empty objections_json."""

from __future__ import annotations

from datetime import datetime

from fabric import schema as S
from fabric.connectors.base import FixtureConnector
from fabric.protocol import RawRecord


class GradiumConnector(FixtureConnector):
    name = "gradium"
    fixture_file = "transcripts.json"
    record_kind = "transcript"
    live_env_keys = ("GRADIUM_API_KEY",)

    def transcribe(self, audio_path: str) -> dict[str, str]:
        """Transcribe an audio file. Mock mode returns the first fixture."""
        if self.mode() == "live":
            raise NotImplementedError(
                "gradium live: verify endpoint in config/apis.yaml, then chunk "
                "audio into <=300s sessions and stitch transcripts by offset"
            )
        fixtures = self._load_fixture()
        first = fixtures[0]
        return {"audio_path": audio_path, "id": first["id"], "text": first["text"]}

    def normalize(self, raw: RawRecord) -> list[S.Entity]:
        p = raw.payload
        return [
            S.Transcript(
                id=p["id"],
                company_id=S.company_id(p["company_domain"]),
                call_ts=datetime.fromisoformat(p["call_ts"]),
                text=p["text"],
                objections_json=[],
            )
        ]
