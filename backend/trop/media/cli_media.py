"""`trop media video|asr|seed-cache|spend|adjudicate-bench`."""
from __future__ import annotations

import json

import typer

app = typer.Typer(help="Media: video / speech / model cache", no_args_is_help=True)


@app.command()
def video(path: str, model: str = typer.Option("flash", help="flash | pro"), no_faces: bool = False,
          write: bool = typer.Option(True, help="merge into data/experiments/dane/media_gemini.json when path is a DANE item")) -> None:
    """Gemini video pass + keyframe faces + voice -> Incident.media / content hints (JSON on stdout)."""
    from trop.media import pipeline
    r = pipeline.analyze_video(path, model=model, with_faces=not no_faces)
    if write:
        out = pipeline.write_media_gemini(r)
        if out:
            typer.echo(f"# wrote {out}", err=True)
    typer.echo(json.dumps(r, ensure_ascii=False, indent=1))


@app.command()
def asr(path: str) -> None:
    """Transcribe an audio/video file (gemini-3.5-transcribe -> faster-whisper)."""
    from trop.media.gateway import gateway
    from trop.media import video as V
    import tempfile
    from pathlib import Path
    p = Path(path)
    if p.suffix.lower() in (".mp4", ".mov", ".mkv", ".webm"):
        a = V.extract_audio(p, Path(tempfile.mkdtemp()) / "a.mp3", max_s=900)
        if a is None:
            typer.echo(json.dumps({"missing": True, "error": "no audio track"}))
            return
        p = a
    typer.echo(json.dumps(gateway.transcribe(str(p)), ensure_ascii=False, indent=1))


@app.command("seed-cache")
def seed_cache() -> None:
    """Pre-seed the model cache from experiments VLM outputs (so offline/judge builds have ad fields)."""
    from trop.media.seed import seed
    typer.echo(json.dumps(seed()))


@app.command()
def spend() -> None:
    """Model spend so far."""
    from trop.media.gateway import gateway
    typer.echo(json.dumps(gateway.spend(), indent=1))


@app.command("adjudicate-bench")
def adjudicate_bench(model: str = "flash", workers: int = 6) -> None:
    """Rerun the 105-pair adjudicator benchmark through gateway.llm; writes data/experiments/sample_v1/adj_<model>.jsonl."""
    from trop.media.adjudicator import benchmark
    typer.echo(json.dumps(benchmark(model=model, workers=workers), ensure_ascii=False, indent=1))
