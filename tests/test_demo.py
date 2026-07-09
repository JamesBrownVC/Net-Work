from __future__ import annotations

import asyncio


def test_gamma_mock_mode() -> None:
    from surfaces.gamma import generate_deck

    result = asyncio.run(generate_deck("# Unified Battle Plan\n..."))
    assert result["status"] == "mock"
    assert result["gammaUrl"].startswith("https://gamma.app/")
    assert result["exportUrl"].endswith(".pptx")


def test_demo_command_end_to_end(capsys) -> None:  # type: ignore[no-untyped-def]
    from typer.testing import CliRunner

    from fabric.cli import app

    result = CliRunner().invoke(app, ["demo", "--target", "novapay.io"])
    assert result.exit_code == 0, result.output
    assert "Unified Battle Plan" in result.output
    assert "moved_to" in result.output and "shares_with" in result.output
    assert "deck [mock]" in result.output
