"""`trop capture <url>`: budgeted victim-context capture (Docker sandbox preferred) -> organizer-compatible bundle."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Optional

import typer

from trop.config import settings

from . import politeness
from ._util import etld1_of, host_of

IMAGE = "trop-capture"
BACKEND = Path(__file__).resolve().parents[2]


def captures_dir() -> Path:
    return Path(settings.data_dir) / "captures"


def docker_available() -> bool:
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def ensure_image() -> bool:
    if subprocess.run(["docker", "image", "inspect", IMAGE], capture_output=True).returncode == 0:
        return True
    r = subprocess.run(["docker", "build", "-t", IMAGE, "-f", "trop/capture/Dockerfile", "."], cwd=BACKEND)
    return r.returncode == 0


def bundle_summary(bundle: Path) -> dict[str, Any]:
    info = json.loads((bundle / "archive_info.json").read_text(encoding="utf-8"))
    return {"bundle": str(bundle), "url": info.get("url"), "final_url": info.get("final_url"), "status": info.get("status"),
            "title": info.get("title"), "profile": info.get("profile"), "challenge": info.get("challenge_detected"),
            "page_role_hint": info.get("page_role_hint"), "error": info.get("error"),
            "has_har": (bundle / "network.har").is_file(), "has_screenshot": (bundle / "screenshots" / "viewport.png").is_file()}


def _run_docker(url: str, out: Path, profiles: list[str], proxy: str | None, fast: bool, gap: float) -> int:
    out.mkdir(parents=True, exist_ok=True)
    cmd = ["docker", "run", "--rm", "--read-only", "--tmpfs", "/tmp", "--tmpfs", "/home/pwuser", "--cap-drop", "ALL",
           "--security-opt", "no-new-privileges", "--memory", "2g", "--pids-limit", "512", "--shm-size", "512m",
           "--user", f"{os.getuid()}:{os.getgid()}", "-e", "HOME=/tmp", "-v", f"{out.resolve()}:/out", IMAGE, url,
           "--out", "/out", "--gap", str(gap)]
    for p in profiles:
        cmd += ["--profile", p]
    if proxy:
        cmd += ["--proxy", proxy]
    if fast:
        cmd.append("--fast")
    return subprocess.run(cmd).returncode


def _run_local(url: str, out: Path, profiles: list[str], proxy: str | None, fast: bool, gap: float) -> int:
    cmd = [sys.executable, "-m", "trop.capture.worker", url, "--out", str(out), "--gap", str(gap)]
    for p in profiles:
        cmd += ["--profile", p]
    if proxy:
        cmd += ["--proxy", proxy]
    if fast:
        cmd.append("--fast")
    return subprocess.run(cmd, cwd=BACKEND).returncode


def capture_url(url: str, profile: str | list[str] = "fb_inapp_android_pl", docker: bool = True, out: Path | None = None,
                proxy: str | None = None, fast: bool = False, gap: float = 20.0, force: bool = False) -> dict[str, Any]:
    """Capture one URL. Enforces the per-eTLD+1 budget. Never submits forms / logs in. -> summary dict (JSON-safe)."""
    from .profiles import PROFILES
    profiles = [profile] if isinstance(profile, str) else list(profile)
    bad = [p for p in profiles if p not in PROFILES]
    if bad:
        return {"ok": False, "url": url, "error": f"unknown profile {bad}; choose from {sorted(PROFILES)}"}
    site = etld1_of(host_of(url))
    if not force:
        ok, wait = politeness.acquire(site, cost=len(profiles))
        if not ok:
            return {"ok": False, "url": url, "error": f"politeness budget for {site}: retry in {wait:.0f}s", "retry_in_s": wait}
    out = out or captures_dir()
    mode = "docker" if docker and docker_available() and ensure_image() else "local"
    if docker and mode == "local":
        print("warning: docker unavailable, capturing locally (not isolated)", file=sys.stderr)
    before = {p.name for p in out.glob("archive_*") if p.is_dir()} if out.exists() else set()
    rc = (_run_docker if mode == "docker" else _run_local)(url, out, profiles, proxy, fast, gap)
    new = sorted(p for p in out.glob("archive_*") if p.is_dir() and p.name not in before)
    bundles = [bundle_summary(b) for b in new if (b / "archive_info.json").is_file()]
    good = any(b["status"] and b["status"] < 500 and not b["error"] for b in bundles)
    politeness.report(site, good)
    return {"ok": bool(bundles), "url": url, "mode": mode, "exit_code": rc, "bundles": bundles,
            "bundle": bundles[0]["bundle"] if bundles else None}


def capture(
    url: str = typer.Argument(..., help="landing URL to capture (headless; no clicks, no forms, no login)"),
    profile: Optional[list[str]] = typer.Option(None, "--profile", help="repeatable; default fb_inapp_android_pl"),
    out: Optional[Path] = typer.Option(None, "--out", help="default: $DATA_DIR/captures"),
    local: bool = typer.Option(False, "--local", help="run Playwright on this host instead of the Docker sandbox"),
    proxy: Optional[str] = typer.Option(None, "--proxy", help="egress proxy, e.g. socks5://127.0.0.1:1080"),
    fast: bool = typer.Option(False, "--fast", help="no PDF/MHTML, shorter settle"),
    force: bool = typer.Option(False, "--force", help="ignore the politeness budget (use for known-safe pages only)"),
) -> None:
    """Capture a URL as an organizer-compatible bundle (archive_info.json, network.har, html/, screenshots/, dns_ssl.json)."""
    r = capture_url(url, profile or "fb_inapp_android_pl", docker=not local, out=out, proxy=proxy, fast=fast, force=force)
    typer.echo(json.dumps(r, indent=1, ensure_ascii=False))
    raise typer.Exit(0 if r.get("ok") else 1)
