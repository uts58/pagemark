from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

try:
    import typer
    from rich.console import Console
    from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
except ImportError as _exc:
    raise SystemExit("pagemark CLI requires the [cli] extra: pip install pagemark[cli]") from _exc

from pagemark.backends import resolve_api_key
from pagemark.client import Pagemark

app = typer.Typer(name="pagemark", help="PDF to Markdown via vision-language models.")
console = Console(stderr=True)


@app.command()
def convert(
    input_pdf: Path = typer.Argument(..., help="Input PDF file"),
    output: Path = typer.Option(None, "-o", "--output", help="Output Markdown file"),
    json_output: Path = typer.Option(None, "--json", help="Output JSON document model"),
    model: str = typer.Option(..., "--model", "-m", help="Model name"),
    base_url: str = typer.Option(..., "--base-url", "-b", help="OpenAI-compatible API base URL"),
    api_key: str = typer.Option(None, "--api-key", "-k", help="API key"),
    profile: str = typer.Option("generic", "--profile", "-p", help="Model profile"),
    pages: str = typer.Option(None, "--pages", help="Page range (e.g. 1-5,9,12-)"),
    max_tokens: int = typer.Option(2048, "--max-tokens", help="Max output tokens per page"),
    concurrency: int = typer.Option(None, "--concurrency", "-c", help="Max concurrent pages"),
    assets_dir: str = typer.Option(None, "--assets-dir", help="Directory for extracted images"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable debug logging"),
    quiet: bool = typer.Option(False, "--quiet", "-q", help="Suppress output below ERROR"),
) -> None:
    """Convert a PDF to Markdown using a vision-language model."""
    _configure_logging(verbose, quiet)

    if not input_pdf.exists():
        console.print(f"[red]File not found: {input_pdf}[/red]")
        raise typer.Exit(1)

    if output is None:
        output = input_pdf.with_suffix(".md")

    progress = Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        console=console,
    )

    with progress:
        task_id = progress.add_task("Converting pages...", total=0)

        def on_progress(page_index: int, total_pages: int, status: str) -> None:
            progress.update(task_id, total=total_pages)
            if status == "completed":
                progress.advance(task_id)

        try:
            client = Pagemark(base_url=base_url, api_key=api_key)
            doc = asyncio.run(
                client.aconvert(
                    str(input_pdf),
                    model=model,
                    max_tokens=max_tokens,
                    profile=profile,
                    pages=pages,
                    concurrency=concurrency,
                    progress=on_progress,
                )
            )
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1) from e
        except ConnectionError as e:
            console.print(f"[red]Connection refused: {base_url}[/red]")
            raise typer.Exit(1) from e

    doc.save(str(output), assets_dir=assets_dir)
    console.print(f"[green]Wrote {output}[/green]")

    if json_output:
        json_output.write_text(doc.model_dump_json(indent=2), encoding="utf-8")
        console.print(f"[green]Wrote {json_output}[/green]")

    vlm_pages = sum(1 for p in doc.pages if p.source.value == "vlm")
    fallback_pages = len(doc.pages) - vlm_pages
    console.print(
        f"  {len(doc.pages)} pages | {vlm_pages} VLM | {fallback_pages} text-layer fallback"
    )
    if doc.assets:
        console.print(f"  {len(doc.assets)} embedded images extracted")


@app.command()
def doctor(
    base_url: str = typer.Option(..., "--base-url", "-b", help="OpenAI-compatible API base URL"),
    model: str = typer.Option(None, "--model", "-m", help="Model to check"),
    api_key: str = typer.Option(None, "--api-key", "-k", help="API key"),
) -> None:
    """Check endpoint reachability and model availability."""
    console.print(f"Endpoint: {base_url}")

    try:
        import os

        resolve_api_key(base_url, api_key)
        source = "explicit argument"
        if api_key is None and os.environ.get("OPENAI_API_KEY"):
            source = "OPENAI_API_KEY"
        console.print(f"API key: [green]resolved from {source}[/green]")
    except ValueError as e:
        console.print(f"API key: [red]{e}[/red]")
        raise typer.Exit(1) from e

    try:
        import httpx

        r = httpx.get(f"{base_url}/models", timeout=10)
        r.raise_for_status()
        data = r.json()
        available = [m.get("id", "?") for m in data.get("data", [])]
        console.print("Connection: [green]OK[/green]")
        console.print(f"Models available: {len(available)}")
        for m in available[:20]:
            marker = "[green]*[/green]" if model and m == model else " "
            console.print(f"  {marker} {m}")
        if model and model not in available:
            console.print(f"[yellow]Model {model!r} not found in available models[/yellow]")
    except Exception as e:
        console.print(f"Connection: [red]FAILED — {e}[/red]")
        raise typer.Exit(1) from e


def _configure_logging(verbose: bool, quiet: bool) -> None:
    level = logging.WARNING
    if verbose:
        level = logging.DEBUG
    elif quiet:
        level = logging.ERROR

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter("%(name)s %(levelname)s: %(message)s"))
    pkg_logger = logging.getLogger("pagemark")
    pkg_logger.setLevel(level)
    pkg_logger.addHandler(handler)


if __name__ == "__main__":
    app()
