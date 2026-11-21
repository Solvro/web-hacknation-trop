"""Model gateway CONTRACT (implemented by WS4 in trop/media/gateway.py; used by WS1, WS5, WS6).

Every call is cached by sha256(task, model-chain, inputs) under settings.cache_dir/models/, so offline mode replays.
Provider order per task is fixed by docs/IMPLEMENTATION.md §1. Persons are NEVER taken from VLM/LLM output.

    from trop.media.gateway import gateway
    gateway.ad_fields(image_path) -> dict          # {advertiser, text, overlay, library_id, display_link, cta, is_decoy, vertical, kind, narrative}
    gateway.video_pass(video_path) -> dict         # {transcript, on_screen_text, scenes, product, brand, narrative, ctas, urls, phones, persons_hint}
    gateway.transcribe(audio_path) -> dict         # {text, lang, model}
    gateway.llm(task, messages, *, json_schema=None, tools=None, model='flash'|'pro') -> dict
                                                   # {text|json|tool_calls, model, usage, cost_usd, cached}
    gateway.spend() -> dict                        # {usd_total, by_provider, by_task}
    faces.match(image_path) -> list[FaceHit]       # trop.media.faces — SFace + gallery, rule cos>=0.45 & lead>=0.10
"""
from __future__ import annotations

from typing import Any, Protocol


class Gateway(Protocol):
    def ad_fields(self, image_path: str) -> dict[str, Any]: ...
    def video_pass(self, video_path: str) -> dict[str, Any]: ...
    def transcribe(self, audio_path: str) -> dict[str, Any]: ...
    def llm(self, task: str, messages: list[dict[str, Any]], *, json_schema: dict | None = None,
            tools: list[dict] | None = None, model: str = "flash") -> dict[str, Any]: ...
    def spend(self) -> dict[str, Any]: ...
