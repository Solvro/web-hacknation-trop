"""Normalized drafts produced by every ingest adapter and consumed by the loader.

Adapters (sample_dir, archive bundle, our own capture, hunter, extension) only produce these;
the loader is the single path into the database. IncidentDraft.to_contract() renders the
PLAN §4 Incident JSON that is stored in incidents.raw and served by the API.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ArtifactDraft:
    role: str
    rel_path: str | None = None
    path: Path | None = None          # read from disk lazily …
    data: bytes | None = None         # … or bytes already in memory (HAR bodies, zip members)
    url: str | None = None
    mime: str | None = None

    def read(self) -> bytes:
        if self.data is not None:
            return self.data
        assert self.path is not None
        return self.path.read_bytes()


@dataclass
class ObsHit:
    type: str
    value: str
    field: str
    display: str | None = None
    confidence: float = 1.0
    context: dict[str, Any] = field(default_factory=dict)
    extractor: str = "rules@1"
    noise_reason: str | None = None   # static noise (public CDN library, CDN edge IP, platform tracker host)
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class RelationDraft:
    src: tuple[str, str]              # (type, value)
    rel: str
    dst: tuple[str, str]
    source: str
    attrs: dict[str, Any] = field(default_factory=dict)


@dataclass
class HopDraft:
    url: str
    kind: str
    status: int | None = None
    ip: str | None = None
    at: datetime | None = None


@dataclass
class RequestDraft:
    seq: int
    started_at: datetime | None
    method: str
    url: str
    host: str
    path_template: str
    status: int | None
    mime: str | None
    resource_type: str | None
    server_ip: str | None
    body_sha256: str | None
    body_size: int | None
    is_third_party: bool
    initiator: str | None


@dataclass
class CaptureDraft:
    tool: str
    entry_url: str
    captured_at: datetime
    tool_version: str | None = None
    profile: str | None = None
    user_agent: str | None = None
    viewport: str | None = None
    locale: str | None = None
    timezone: str | None = None
    referer: str | None = None
    final_url: str | None = None
    final_status: int | None = None
    title: str | None = None
    page_role: str = "unknown"
    cloak_verdict: str = "unknown"
    page_text: str | None = None
    dom_sha256: str | None = None
    text_sha256: str | None = None
    text_simhash: int | None = None
    dom_minhash: list[int] | None = None
    forms: list[dict] = field(default_factory=list)
    outlinks: list[str] = field(default_factory=list)
    tls: dict | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    hops: list[HopDraft] = field(default_factory=list)
    requests: list[RequestDraft] = field(default_factory=list)
    artifacts: list[ArtifactDraft] = field(default_factory=list)


@dataclass
class AdDraft:
    platform: str = "meta"
    library_id: str | None = None
    advertiser_name: str | None = None
    advertiser_platform_id: str | None = None
    body: str | None = None
    title: str | None = None
    display_link: str | None = None
    cta: str | None = None
    link_url: str | None = None
    delivery_start: datetime | None = None
    delivery_stop: datetime | None = None
    eu_total_reach: int | None = None
    targeting: dict = field(default_factory=dict)
    snapshot_url: str | None = None
    raw: dict = field(default_factory=dict)
    artifacts: list[ArtifactDraft] = field(default_factory=list)
    dedupe_key: str | None = None     # filled by the loader when not given


@dataclass
class IncidentDraft:
    source_key: str
    source_ref: str
    kind: str
    observed_at: datetime | None = None
    title: str | None = None
    headline: str | None = None
    headline_template: str | None = None
    narrative: str | None = None
    vertical: str | None = None
    lang: str | None = None
    entry_url: str | None = None
    ad: AdDraft | None = None
    captures: list[CaptureDraft] = field(default_factory=list)
    artifacts: list[ArtifactDraft] = field(default_factory=list)
    observables: list[ObsHit] = field(default_factory=list)
    relations: list[RelationDraft] = field(default_factory=list)
    quality: dict[str, Any] = field(default_factory=lambda: {"available": [], "missing": [], "errors": []})
    sensitivity: str = "restricted"

    def obs(self, type_: str) -> list[str]:
        return sorted({o.value for o in self.observables if o.type == type_})

    def to_contract(self) -> dict:
        """PLAN §4 Incident JSON (the API contract), derived from the draft."""
        cap = self.captures[0] if self.captures else None
        hops = [h.url for h in cap.hops] if cap else []
        return {
            "source": {"type": self.source_key, "ref": self.source_ref,
                       "captured_at": self.observed_at.isoformat() if self.observed_at else None},
            "ad": None if not self.ad else {
                "platform": self.ad.platform, "library_id": self.ad.library_id,
                "advertiser": self.ad.advertiser_name, "text": self.ad.body,
                "display_link": self.ad.display_link, "cta": self.ad.cta,
                "delivery": {"start": self.ad.delivery_start.isoformat() if self.ad.delivery_start else None,
                             "reach": self.ad.eu_total_reach}},
            "landing": None if not cap else {
                "entry_url": cap.entry_url, "final_url": cap.final_url, "redirect_chain": hops,
                "status": cap.final_status, "title": cap.title, "lang": self.lang,
                "forms": cap.forms, "outlinks": cap.outlinks[:50]},
            "tracking": {"fb_pixels": self.obs("fb_pixel"), "capi_gateways": self.obs("capi_gateway"),
                         "google_tags": self.obs("google_tag"), "tiktok_pixels": self.obs("tiktok_pixel"),
                         "url_param_schema": self.obs("url_param_schema"),
                         "kit_endpoints": self.obs("kit_endpoint"), "lander_paths": self.obs("lander_path"),
                         "third_party": self.obs("third_party_host"),
                         "third_party_accounts": self.obs("third_party_account"),
                         "meta_ids": {"campaign": self.obs("meta_campaign_id"), "adset": self.obs("meta_adset_id"),
                                      "ad": self.obs("meta_ad_id")},
                         "tds_keys": self.obs("tds_key"), "html_signatures": self.obs("html_signature")},
            "infra": {"etld1": self.obs("etld1"), "fqdn": self.obs("fqdn"), "ips": self.obs("ip"),
                      "certs": self.obs("cert"), "favicon_mmh3": self.obs("favicon_mmh3")},
            "content": {"headline": self.headline, "headline_template": self.headline_template,
                        "persons": self.obs("person"), "brands": self.obs("brand"),
                        "products": self.obs("product"), "narrative": self.narrative,
                        "contacts": {"phones": self.obs("phone"), "ibans": self.obs("iban"),
                                     "emails": self.obs("email"), "telegram": self.obs("telegram")}},
            "quality": self.quality,
        }
