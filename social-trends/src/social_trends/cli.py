"""social-trends CLI for analysts.

Same capabilities as the MCP server, from the terminal. Human-readable by
default; `--json` for piping. Exists so analysts don't need a chat client.
"""
from __future__ import annotations

import asyncio
import json

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from . import providers as P
from .providers.base import ProviderUnavailable
from .providers.twitch import TwitchProvider
from .providers.scrapecreators import ScrapeCreatorsProvider
from .schemas import Platform

app = typer.Typer(name="social-trends", help="Social trends aggregation CLI.",
                  no_args_is_help=True)
console = Console()


@app.command()
def version() -> None:
    """Print the package version."""
    typer.echo(__version__)


@app.command(name="list-providers")
def list_providers() -> None:
    """Show each capability, its provider, and whether it is usable now."""
    table = Table("capability", "provider", "available", "reason")
    for row in P.registry.status():
        table.add_row(
            str(row["capability"]), str(row["provider"]),
            "[green]yes" if row["available"] else "[red]no", str(row["reason"]),
        )
    console.print(table)


@app.command(name="twitch-top")
def twitch_top(
    first: int = typer.Option(10, "--first", "-n"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Top Twitch games by viewers (set TWITCH_USE_MOCK=true to use the mock-api)."""
    provider = TwitchProvider()
    try:
        entries = asyncio.run(provider.top_games(first=first))
    except ProviderUnavailable as exc:
        console.print(f"[red]{exc}")
        raise typer.Exit(code=1)
    if json_output:
        typer.echo(json.dumps([e.model_dump(mode="json") for e in entries], indent=2))
        return
    table = Table("rank", "game", "id")
    for e in entries:
        table.add_row(str(e.rank), e.name, e.id)
    console.print(table)


@app.command()
def hashtags(
    platform: str = typer.Argument(..., help="tiktok | instagram | twitch | youtube"),
    country: str = typer.Option(None, "--country", "-c"),
    first: int = typer.Option(20, "--first", "-n"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Trending hashtags via ScrapeCreators (needs SCRAPECREATORS_API_KEY)."""
    try:
        plat = Platform(platform)
    except ValueError:
        console.print(f"[red]unknown platform '{platform}'. "
                      f"supported: {[p.value for p in Platform]}")
        raise typer.Exit(code=1)
    provider = ScrapeCreatorsProvider()
    try:
        items = asyncio.run(provider.trending_hashtags(plat, country=country, first=first))
    except ProviderUnavailable as exc:
        console.print(f"[red]{exc}")
        raise typer.Exit(code=1)
    if json_output:
        typer.echo(json.dumps([i.model_dump(mode="json") for i in items], indent=2))
        return
    table = Table("hashtag", "volume", "growth_rate")
    for i in items:
        table.add_row(i.name, str(i.volume or "-"), str(i.growth_rate or "-"))
    console.print(table)


@app.command()
def serve() -> None:
    """Run the MCP server over stdio (same as `social-trends-mcp`)."""
    from .server import main
    main()


if __name__ == "__main__":
    app()
