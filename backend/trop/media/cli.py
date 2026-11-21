"""`trop gallery install|build|match|info` — face gallery (SFace + 6,305 people)."""
from __future__ import annotations

import json

import typer

app = typer.Typer(help="Face gallery: install / build / match", no_args_is_help=True)


@app.command()
def install() -> None:
    """Copy the YuNet/SFace models and the prebuilt gallery index into settings.models_dir (download ONNX if absent)."""
    from trop.media import faces
    for n, p in faces.ensure_models().items():
        typer.echo(f"{n}: {'ok' if p.exists() else 'MISSING'} ({p})")


@app.command()
def info() -> None:
    """Index size."""
    from trop.media import faces
    m = faces.matcher()
    typer.echo(json.dumps({"people": m.n_people, "photos": int(m.G.shape[0])}))


@app.command()
def build(per: int = typer.Option(3, help="max extra Commons photos per person")) -> None:
    """Rebuild the index from the fetched gallery photos (data/experiments/face_gallery) -> models_dir/index_sface.npz."""
    from trop.media import faces
    typer.echo(json.dumps(faces.build(per), indent=1))


@app.command()
def match(image: str, all_faces: bool = typer.Option(False, "--all", help="also list unnamed faces")) -> None:
    """Identify faces in IMAGE (rule cos>=0.45 and lead>=0.10)."""
    from trop.media import faces
    hits = faces.matcher().match(image, all_faces=all_faces)
    typer.echo(json.dumps([h.model_dump(mode="json") for h in hits], ensure_ascii=False, indent=1))
    if not hits:
        typer.echo("no named face")
