"""Model gateway (implements gateway_contract.Gateway). See docs/IMPLEMENTATION.md §1.

Provider order per task
  ad_fields : OpenRouter qwen3.6-35b-a3b -> Gemini flash -> EasyOCR (extra `ml`) -> cache only
  video_pass: Gemini Files API (whole video + audio, structured JSON) -> ffmpeg keyframes + ASR + ad_fields
  transcribe: gemini-3.5-transcribe -> faster-whisper CPU int8 (extra `ml`)
  llm       : Gemini flash/pro (JSON output, function calling) -> OpenRouter qwen3.8-27b

Every response is cached as JSON in settings.cache_dir/models/<sha256>.json, key = sha256(task, model chain, input).
Offline (TROP_MODE=offline, or no keys) replays the cache; a miss returns {} + {"missing": True}, never raises.
Spend is tracked per provider/task and appended to <data_dir>/logs/spend.jsonl; the budget is a hard stop.
Person identity is never taken from a model: names a model volunteers go to `persons_hint`, which the engine ignores.
"""
from __future__ import annotations

import base64
import hashlib
import io
import json
import logging
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from trop.config import settings

log = logging.getLogger("trop.media.gateway")

# USD per 1M tokens (input, output). Deliberately conservative estimates; OpenRouter reports real cost when asked.
PRICES = {"flash": (0.50, 3.00), "pro": (2.00, 12.00), "transcribe": (1.00, 3.00), "openrouter": (0.20, 0.80)}

AD_PROMPT = """Jesteś analitykiem CERT. Na obrazku jest zrzut ekranu reklamy z Facebooka/Instagrama (post sponsorowany)
albo okno 'Szczegóły reklamy' z Biblioteki reklam Meta. Wyciągnij pola i zwróć WYŁĄCZNIE JSON:
{"kind": "feed|adlibrary", "advertiser": "nazwa strony reklamodawcy", "library_id": "cyfry lub null",
 "start_date": "data rozpoczęcia lub null", "caption": "tekst posta pod/nad kreacją, dosłownie",
 "overlay_text": "tekst wypalony na grafice/wideo, dosłownie", "cta": "przycisk", "display_link": "domena wyświetlana lub null",
 "persons": ["rozpoznane osoby publiczne (imię nazwisko) lub opis np. 'nieznany lekarz'"],
 "is_decoy": true/false (czy kreacja jest niezwiązana z przekazem, np. ptak, krajobraz z gry),
 "language": "pl|en|...", "vertical": "investment|health|politics_news|other", "brands": ["podszywane marki/media"],
 "narrative": "1 zdanie po polsku: co reklama sugeruje"}"""

VIDEO_PROMPT = """Jesteś analitykiem CERT badającym reklamy oszukańcze (Polska). Obejrzyj i wysłuchaj CAŁE nagranie
(obraz + dźwięk). Jeśli to nagranie ekranu telefonu/przeglądarki, skup się na reklamie/stronie, którą pokazuje.
Zwróć WYŁĄCZNIE JSON:
{"language": "pl|en|...", "transcript": "pełna transkrypcja mowy, dosłownie, w języku oryginału ('' jeśli brak mowy)",
 "on_screen_text": ["każdy istotny napis na ekranie, dosłownie, w kolejności"],
 "scenes": [{"t": "mm:ss", "description": "co widać/dzieje się (1 zdanie)"}],
 "product": "reklamowany produkt/usługa lub null", "brand": "marka/medium/instytucja, pod którą się podszywa lub null",
 "narrative": "2-3 zdania po polsku: historia i obietnica reklamy",
 "ctas": ["wezwania do działania, dosłownie"], "urls": ["adresy/domeny widoczne lub wypowiedziane"],
 "phones": ["numery telefonów widoczne lub wypowiedziane"],
 "vertical": "investment|health|politics_news|other",
 "persons_hint": ["osoby, które wydają się widoczne/wymienione (NIEZWERYFIKOWANE, tylko wskazówka)"],
 "is_ai_generated": true/false/null, "ad_start_s": liczba lub null, "ad_end_s": liczba lub null}
Nie zgaduj: gdy czegoś nie ma, daj null lub pustą listę."""


class BudgetExceeded(RuntimeError):
    pass


def _sha(*parts: bytes | str) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p if isinstance(p, bytes) else p.encode())
        h.update(b"\x00")
    return h.hexdigest()


def file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return h.hexdigest()


def parse_json(raw: str) -> Any:
    """Tolerant JSON: strips code fences / prose, trailing commas. Returns {} when nothing parses."""
    if not raw:
        return {}
    s = raw.strip()
    s = re.sub(r"^```(?:json)?\s*|\s*```$", "", s)
    m = re.search(r"\{.*\}", s, re.S) or re.search(r"\[.*\]", s, re.S)
    for cand in (s, m.group(0) if m else None):
        if not cand:
            continue
        for c in (cand, re.sub(r",\s*([}\]])", r"\1", cand)):
            try:
                return json.loads(c)
            except Exception:  # noqa: BLE001
                pass
    return {}


def _strs(v: Any) -> list[str]:
    if isinstance(v, str):
        v = [v]
    return [str(x).strip() for x in (v or []) if isinstance(x, (str, int)) and str(x).strip()]


def norm_ad(j: dict, model: str) -> dict:
    """Map a raw VLM answer (old or new key names) to the AdLayer-facing fields. Names -> persons_hint (never `persons`)."""
    j = j or {}
    kind = j.get("kind") or j.get("screenshot_kind")
    kind = {"adlibrary": "adlibrary_modal"}.get(kind, kind)
    lib = str(j.get("library_id") or "").strip() or None
    persons = [p.lower() for p in _strs(j.get("persons") or j.get("persons_hint"))]
    return {
        "kind": kind, "advertiser": j.get("advertiser"), "library_id": lib, "text": j.get("text") or j.get("caption"),
        "overlay": j.get("overlay") or j.get("overlay_text"), "cta": j.get("cta"), "display_link": j.get("display_link"),
        "is_decoy": j.get("is_decoy"), "vertical": j.get("vertical"), "narrative": j.get("narrative"),
        "brands": _strs(j.get("brands")), "start_date": j.get("start_date"), "language": j.get("language"),
        "persons_hint": persons, "_model": model, "_parsed": bool(j),
    }


def norm_video(j: dict, model: str) -> dict:
    j = j or {}
    return {
        "transcript": (j.get("transcript") or "").strip(), "on_screen_text": _strs(j.get("on_screen_text")),
        "scenes": [s for s in (j.get("scenes") or []) if isinstance(s, dict)], "product": j.get("product"),
        "brand": j.get("brand"), "narrative": j.get("narrative"), "ctas": _strs(j.get("ctas")), "urls": _strs(j.get("urls")),
        "phones": _strs(j.get("phones")), "vertical": j.get("vertical"), "language": j.get("language"),
        "persons_hint": [p.lower() for p in _strs(j.get("persons_hint") or j.get("persons"))],
        "is_ai_generated": j.get("is_ai_generated"), "ad_start_s": j.get("ad_start_s"), "ad_end_s": j.get("ad_end_s"),
        "_model": model, "_parsed": bool(j),
    }


def _price(provider: str, model: str, usage: dict) -> float:
    pin, pout = PRICES["openrouter"]
    if provider == "gemini":
        key = "transcribe" if "transcribe" in model else "pro" if "pro" in model else "flash"
        pin, pout = PRICES[key]
    return (usage.get("prompt_tokens", 0) * pin + usage.get("completion_tokens", 0) * pout) / 1e6


class ModelGateway:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._gem = None
        self._or = None
        self._session_usd = 0.0

    # ------------------------------------------------------------------ paths / mode
    @property
    def cache_path(self) -> Path:
        p = Path(settings.cache_dir) / "models"
        p.mkdir(parents=True, exist_ok=True)
        return p

    @property
    def spend_log(self) -> Path:
        p = Path(settings.data_dir) / "logs"
        p.mkdir(parents=True, exist_ok=True)
        return p / "spend.jsonl"

    @property
    def offline(self) -> bool:
        return settings.trop_mode == "offline"

    def has_gemini(self) -> bool:
        return bool(settings.gemini_api_key) and not self.offline

    def has_openrouter(self) -> bool:
        return bool(settings.openrouter_api_key) and not self.offline

    def budget(self) -> float:
        cap = os.environ.get("TROP_SPEND_CAP")
        return min(settings.llm_budget_usd, float(cap)) if cap else settings.llm_budget_usd

    # ------------------------------------------------------------------ cache
    def cache_key(self, task: str, chain: list[str], *payload: bytes | str) -> str:
        return _sha(task, "|".join(chain), *payload)

    def cache_get(self, key: str) -> dict | None:
        f = self.cache_path / f"{key}.json"
        if f.exists():
            try:
                return json.loads(f.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                return None
        return None

    def cache_put(self, key: str, task: str, chain: list[str], result: dict, **meta: Any) -> None:
        rec = {"task": task, "chain": chain, "at": time.strftime("%Y-%m-%dT%H:%M:%S"), "result": result, **meta}
        tmp = self.cache_path / f".{key}.{os.getpid()}.tmp"
        tmp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.cache_path / f"{key}.json")

    # ------------------------------------------------------------------ spend
    def _charge(self, provider: str, model: str, task: str, usage: dict, cost: float | None = None) -> float:
        cost = _price(provider, model, usage) if cost is None else cost
        with self._lock:
            self._session_usd += cost
            with open(self.spend_log, "a", encoding="utf-8") as f:
                f.write(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "provider": provider, "model": model,
                                    "task": task, "usage": usage, "usd": round(cost, 6)}) + "\n")
        return cost

    def spend(self) -> dict[str, Any]:
        by_p: dict[str, float] = {}
        by_t: dict[str, float] = {}
        total = 0.0
        if self.spend_log.exists():
            for line in self.spend_log.read_text(encoding="utf-8").splitlines():
                try:
                    r = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                total += r.get("usd", 0.0)
                by_p[r["provider"]] = by_p.get(r["provider"], 0.0) + r.get("usd", 0.0)
                by_t[r["task"]] = by_t.get(r["task"], 0.0) + r.get("usd", 0.0)
        return {"usd_total": round(total, 6), "by_provider": {k: round(v, 6) for k, v in by_p.items()},
                "by_task": {k: round(v, 6) for k, v in by_t.items()}, "session_usd": round(self._session_usd, 6),
                "budget_usd": self.budget()}

    def _check_budget(self) -> None:
        if self.spend()["usd_total"] >= self.budget():
            raise BudgetExceeded(f"LLM budget ${self.budget():.2f} exhausted")

    # ------------------------------------------------------------------ provider clients
    def _gemini(self):
        if self._gem is None:
            from google import genai
            from google.genai import types
            self._gem = genai.Client(api_key=settings.gemini_api_key,
                                     http_options=types.HttpOptions(api_version="v1beta", timeout=300_000))
        return self._gem

    def _openrouter(self):
        if self._or is None:
            from openai import OpenAI
            self._or = OpenAI(api_key=settings.openrouter_api_key, base_url="https://openrouter.ai/api/v1", timeout=120,
                              max_retries=0)
        return self._or

    @staticmethod
    def _retry(fn, what: str, tries: int = 4):
        last: Exception | None = None
        for i in range(tries):
            try:
                return fn()
            except BudgetExceeded:
                raise
            except Exception as e:  # noqa: BLE001
                last = e
                msg = str(e)
                retriable = any(t in msg for t in ("429", "500", "502", "503", "504", "timed out", "Timeout", "timeout",
                                                   "overloaded", "UNAVAILABLE", "Connection", "RESOURCE_EXHAUSTED"))
                if not retriable or i == tries - 1:
                    break
                time.sleep(min(30, 2 ** (i + 1)) + (i * 0.37))
        raise RuntimeError(f"{what} failed: {str(last)[:300]}") from last

    # ------------------------------------------------------------------ raw calls
    def _gemini_generate(self, model: str, contents: Any, task: str, config: dict | None = None) -> tuple[Any, dict, float]:
        self._check_budget()
        from google.genai import types
        cfg = types.GenerateContentConfig(**(config or {}))
        r = self._retry(lambda: self._gemini().models.generate_content(model=model, contents=contents, config=cfg),
                        f"gemini {model}")
        um = r.usage_metadata
        usage = {"prompt_tokens": getattr(um, "prompt_token_count", 0) or 0,
                 "completion_tokens": (getattr(um, "candidates_token_count", 0) or 0) + (getattr(um, "thoughts_token_count", 0) or 0)}
        return r, usage, self._charge("gemini", model, task, usage)

    def _or_chat(self, model: str, messages: list[dict], task: str, **kw: Any) -> tuple[Any, dict, float]:
        self._check_budget()
        extra = {"usage": {"include": True}, "reasoning": {"enabled": False}}
        r = self._retry(lambda: self._openrouter().chat.completions.create(model=model, messages=messages, extra_body=extra, **kw),
                        f"openrouter {model}")
        u = r.usage
        usage = {"prompt_tokens": getattr(u, "prompt_tokens", 0) or 0, "completion_tokens": getattr(u, "completion_tokens", 0) or 0}
        real = (getattr(u, "model_extra", None) or {}).get("cost")
        return r, usage, self._charge("openrouter", model, task, usage, float(real) if real is not None else None)

    # ------------------------------------------------------------------ ad_fields
    @property
    def ad_chain(self) -> list[str]:
        return [settings.openrouter_vlm_model, settings.gemini_flash_model, "easyocr"]

    @staticmethod
    def _image_for_model(path: str, max_side: int = 1800) -> tuple[bytes, str]:
        from PIL import Image
        im = Image.open(path)
        im.load()
        if max(im.size) > max_side:
            im.thumbnail((max_side, max_side))
        buf = io.BytesIO()
        im.convert("RGB").save(buf, "JPEG", quality=90)
        return buf.getvalue(), "image/jpeg"

    def ad_key(self, image_path: str) -> str:
        return self.cache_key("ad_fields", self.ad_chain, Path(image_path).read_bytes())

    def ad_fields(self, image_path: str) -> dict[str, Any]:
        try:
            data = Path(image_path).read_bytes()
        except OSError:
            return {"missing": True, "error": "unreadable image"}
        chain = self.ad_chain
        key = self.cache_key("ad_fields", chain, data)
        hit = self.cache_get(key)
        if hit:
            return {**hit["result"], "_cached": True}
        jpg, mime = self._image_for_model(image_path)
        errors: list[str] = []
        if self.has_openrouter():
            try:
                b64 = base64.b64encode(jpg).decode()
                r, usage, cost = self._or_chat(
                    settings.openrouter_vlm_model,
                    [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                                                  {"type": "text", "text": AD_PROMPT}]}],
                    "ad_fields", temperature=0, max_tokens=1200)
                j = parse_json(r.choices[0].message.content or "")
                if j:
                    res = norm_ad(j, settings.openrouter_vlm_model)
                    self.cache_put(key, "ad_fields", chain, res, usage=usage, cost_usd=cost)
                    return {**res, "_cached": False}
                errors.append("openrouter: unparsable")
            except BudgetExceeded as e:
                return {"missing": True, "error": str(e), "budget_exhausted": True}
            except Exception as e:  # noqa: BLE001
                errors.append(str(e)[:200])
        if self.has_gemini():
            try:
                from google.genai import types
                r, usage, cost = self._gemini_generate(
                    settings.gemini_flash_model,
                    [types.Part.from_bytes(data=jpg, mime_type=mime), AD_PROMPT], "ad_fields",
                    {"response_mime_type": "application/json", "temperature": 0})
                j = parse_json(r.text or "")
                if j:
                    res = norm_ad(j, settings.gemini_flash_model)
                    self.cache_put(key, "ad_fields", chain, res, usage=usage, cost_usd=cost)
                    return {**res, "_cached": False}
                errors.append("gemini: unparsable")
            except BudgetExceeded as e:
                return {"missing": True, "error": str(e), "budget_exhausted": True}
            except Exception as e:  # noqa: BLE001
                errors.append(str(e)[:200])
        res = self._easyocr(image_path)
        if res:
            self.cache_put(key, "ad_fields", chain, res)
            return {**res, "_cached": False}
        return {"missing": True, "error": "; ".join(errors) or "no provider available and no cache entry"}

    @staticmethod
    def _easyocr(image_path: str) -> dict | None:
        try:
            import easyocr  # type: ignore
        except ImportError:
            return None
        try:
            lines = [t for _, t, c in easyocr.Reader(["pl", "en"], gpu=False, verbose=False).readtext(image_path) if c > 0.3]
        except Exception:  # noqa: BLE001
            return None
        blob = "\n".join(lines)
        lib = re.search(r"(?:identyfikator biblioteki|library id)\D{0,5}(\d{10,})", blob, re.I)
        return norm_ad({"kind": "adlibrary" if "szczegóły reklamy" in blob.lower() else "feed", "text": blob,
                        "library_id": lib[1] if lib else None}, "easyocr")

    # ------------------------------------------------------------------ transcribe
    @property
    def asr_chain(self) -> list[str]:
        return [settings.gemini_asr_model, "faster-whisper-small-int8"]

    def transcribe(self, audio_path: str) -> dict[str, Any]:
        try:
            data = Path(audio_path).read_bytes()
        except OSError:
            return {"missing": True, "error": "unreadable audio"}
        chain = self.asr_chain
        key = self.cache_key("transcribe", chain, data)
        hit = self.cache_get(key)
        if hit:
            return {**hit["result"], "_cached": True}
        errors: list[str] = []
        if self.has_gemini():
            try:
                res = self._gemini_transcribe(audio_path, data)
                self.cache_put(key, "transcribe", chain, res, cost_usd=res.get("cost_usd"))
                return {**res, "_cached": False}
            except BudgetExceeded as e:
                return {"missing": True, "error": str(e), "budget_exhausted": True}
            except Exception as e:  # noqa: BLE001
                errors.append(str(e)[:200])
        res = self._whisper(audio_path)
        if res:
            self.cache_put(key, "transcribe", chain, res)
            return {**res, "_cached": False}
        return {"missing": True, "error": "; ".join(errors) or "no provider available and no cache entry"}

    def _gemini_transcribe(self, path: str, data: bytes) -> dict:
        from google.genai import types
        mime = {".mp3": "audio/mp3", ".wav": "audio/wav", ".m4a": "audio/mp4", ".aac": "audio/aac", ".ogg": "audio/ogg",
                ".flac": "audio/flac", ".mp4": "video/mp4"}.get(Path(path).suffix.lower(), "audio/mp3")
        prompt = "Transcribe this audio verbatim in its original language (no summary, no timestamps). Output only the transcript."
        up = None
        if len(data) < 18_000_000:
            part = types.Part.from_bytes(data=data, mime_type=mime)
        else:
            up = self._upload(path, mime)
            part = up
        try:
            r, usage, cost = self._gemini_generate(settings.gemini_asr_model, [part, prompt], "transcribe", {"temperature": 0})
        finally:
            if up is not None:
                self._delete_file(up)
        text = (r.text or "").strip()
        return {"text": text, "lang": None, "model": settings.gemini_asr_model, "cost_usd": cost, "usage": usage}

    @staticmethod
    def _whisper(path: str) -> dict | None:
        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError:
            return None
        try:
            m = WhisperModel("small", device="cpu", compute_type="int8")
            segs, info = m.transcribe(path, vad_filter=True)
            return {"text": " ".join(s.text.strip() for s in segs), "lang": info.language, "model": "faster-whisper-small-int8"}
        except Exception as e:  # noqa: BLE001
            log.warning("faster-whisper failed: %s", e)
            return None

    # ------------------------------------------------------------------ Files API helpers
    def _upload(self, path: str, mime: str):
        from google.genai import types
        client = self._gemini()
        f = self._retry(lambda: client.files.upload(file=str(path), config=types.UploadFileConfig(mime_type=mime)), "gemini upload")
        t0 = time.time()
        while getattr(f.state, "name", str(f.state)) == "PROCESSING":
            if time.time() - t0 > 600:
                raise RuntimeError("gemini file processing timeout")
            time.sleep(3)
            f = client.files.get(name=f.name)
        if getattr(f.state, "name", str(f.state)) != "ACTIVE":
            raise RuntimeError(f"gemini file state {f.state}")
        return f

    def _delete_file(self, f) -> None:
        try:
            self._gemini().files.delete(name=f.name)
        except Exception:  # noqa: BLE001
            pass

    # ------------------------------------------------------------------ video_pass
    @property
    def video_chain(self) -> list[str]:
        return [settings.gemini_flash_model, "ffmpeg-keyframes+asr"]

    def video_pass(self, video_path: str, *, model: str = "flash") -> dict[str, Any]:
        p = Path(video_path)
        if not p.exists():
            return {"missing": True, "error": "no such file"}
        gmodel = settings.gemini_pro_model if model == "pro" else settings.gemini_flash_model
        chain = [gmodel, "ffmpeg-keyframes+asr"]
        key = self.cache_key("video_pass", chain, file_sha256(p))
        hit = self.cache_get(key)
        if hit:
            return {**hit["result"], "_cached": True}
        errors: list[str] = []
        if self.has_gemini():
            try:
                res = self._gemini_video(p, gmodel, key, chain)
                return {**res, "_cached": False}
            except BudgetExceeded as e:
                return {"missing": True, "error": str(e), "budget_exhausted": True}
            except Exception as e:  # noqa: BLE001
                errors.append(str(e)[:300])
                log.warning("gemini video pass failed: %s", e)
        res = self._video_fallback(p)
        if res:
            self.cache_put(key, "video_pass", chain, res)
            return {**res, "_cached": False}
        return {"missing": True, "error": "; ".join(errors) or "no provider available and no cache entry"}

    def _gemini_video(self, p: Path, gmodel: str, key: str, chain: list[str]) -> dict:
        from trop.media import video as V
        info = V.probe(p)
        dur = info["duration_s"] or 0
        tmpd = Path(tempfile.mkdtemp(prefix="trop_vid_"))
        send, trimmed = p, None
        if p.stat().st_size > 20_000_000 or dur > 900 or p.suffix.lower() not in (".mp4", ".mov"):
            send = V.proxy(p, tmpd / "proxy.mp4", max_s=900 if dur > 900 else None, fps=5)
            trimmed = 900 if dur > 900 else None
        up = self._upload(str(send), "video/mp4")
        try:
            r, usage, cost = self._gemini_generate(gmodel, [up, VIDEO_PROMPT], "video_pass",
                                                   {"response_mime_type": "application/json", "temperature": 0})
        finally:
            self._delete_file(up)
        j = parse_json(r.text or "")
        if not j:
            raise RuntimeError("gemini video: unparsable JSON")
        res = norm_video(j, gmodel)
        res.update({"duration_s": dur, "trimmed_to_s": trimmed, "source_bytes": p.stat().st_size})
        self.cache_put(key, "video_pass", chain, res, usage=usage, cost_usd=cost)
        return res

    def _video_fallback(self, p: Path) -> dict | None:
        """No Gemini: ffmpeg keyframes -> ad_fields on each (cache/OpenRouter/OCR), audio -> transcribe."""
        from trop.media import video as V
        info = V.probe(p)
        kdir = Path(settings.artifact_dir) / "keyframes" / file_sha256(p)[:12]
        frames = V.keyframes(p, kdir, n=12)
        texts, ctas, urls, advertisers = [], [], [], []
        for f in frames:
            a = self.ad_fields(f)
            if a.get("missing"):
                continue
            texts += [t for t in (a.get("text"), a.get("overlay")) if t]
            if a.get("cta"):
                ctas.append(a["cta"])
            if a.get("display_link"):
                urls.append(a["display_link"])
            if a.get("advertiser"):
                advertisers.append(a["advertiser"])
        transcript = ""
        wav = V.extract_audio(p, Path(tempfile.mkdtemp(prefix="trop_aud_")) / "a.mp3", max_s=900)
        if wav:
            t = self.transcribe(str(wav))
            transcript = t.get("text", "") if not t.get("missing") else ""
        if not (frames or transcript):
            return None
        return {**norm_video({"transcript": transcript, "on_screen_text": list(dict.fromkeys(texts)), "ctas": ctas, "urls": urls,
                              "brand": advertisers[0] if advertisers else None}, "ffmpeg-keyframes+asr"),
                "duration_s": info["duration_s"], "keyframes": frames}

    # ------------------------------------------------------------------ llm
    def llm(self, task: str, messages: list[dict[str, Any]], *, json_schema: dict | None = None,
            tools: list[dict] | None = None, model: str = "flash") -> dict[str, Any]:
        gmodel = {"flash": settings.gemini_flash_model, "pro": settings.gemini_pro_model}.get(model, model)
        chain = [gmodel, settings.openrouter_llm_model]
        payload = json.dumps({"m": messages, "s": json_schema, "t": tools}, sort_keys=True, ensure_ascii=False, default=str)
        key = self.cache_key("llm:" + task, chain, payload)
        hit = self.cache_get(key)
        if hit:
            return {**hit["result"], "cached": True}
        errors: list[str] = []
        if self.has_gemini():
            try:
                res = self._llm_gemini(task, gmodel, messages, json_schema, tools)
                self.cache_put(key, "llm:" + task, chain, res)
                return {**res, "cached": False}
            except BudgetExceeded as e:
                return {"missing": True, "error": str(e), "budget_exhausted": True, "cached": False}
            except Exception as e:  # noqa: BLE001
                errors.append("gemini: " + str(e)[:200])
        if self.has_openrouter():
            try:
                res = self._llm_openrouter(task, messages, json_schema, tools)
                self.cache_put(key, "llm:" + task, chain, res)
                return {**res, "cached": False}
            except BudgetExceeded as e:
                return {"missing": True, "error": str(e), "budget_exhausted": True, "cached": False}
            except Exception as e:  # noqa: BLE001
                errors.append("openrouter: " + str(e)[:200])
        return {"missing": True, "error": "; ".join(errors) or "no provider available and no cache entry", "cached": False}

    @staticmethod
    def _fn_decls(tools: list[dict]) -> list[dict]:
        out = []
        for t in tools:
            f = t.get("function", t)
            out.append({"name": f["name"], "description": f.get("description", ""),
                        "parameters_json_schema": f.get("parameters") or {"type": "object", "properties": {}}})
        return out

    def _llm_gemini(self, task: str, gmodel: str, messages: list[dict], json_schema: dict | None, tools: list[dict] | None) -> dict:
        from google.genai import types
        system, contents = [], []
        for m in messages:
            role, c = m["role"], m.get("content")
            if role == "system":
                system.append(c if isinstance(c, str) else json.dumps(c))
            elif role == "tool":
                contents.append(types.Content(role="user", parts=[types.Part.from_function_response(
                    name=m.get("name") or m.get("tool_call_id", "tool"), response={"result": c})]))
            elif role == "assistant":
                parts = [types.Part(text=c)] if c else []
                for tc in m.get("tool_calls") or []:
                    fn = tc.get("function", tc)
                    args = fn.get("arguments", fn.get("args", {}))
                    parts.append(types.Part.from_function_call(name=fn["name"], args=json.loads(args) if isinstance(args, str) else args))
                contents.append(types.Content(role="model", parts=parts or [types.Part(text="")]))
            else:
                contents.append(types.Content(role="user", parts=[types.Part(text=c if isinstance(c, str) else json.dumps(c))]))
        cfg: dict[str, Any] = {"temperature": 0}
        if system:
            cfg["system_instruction"] = "\n\n".join(system)
        if json_schema:
            cfg.update(response_mime_type="application/json", response_json_schema=json_schema)
        if tools:
            cfg["tools"] = [types.Tool(function_declarations=self._fn_decls(tools))]
            cfg["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
        r, usage, cost = self._gemini_generate(gmodel, contents, "llm:" + task, cfg)
        out: dict[str, Any] = {"model": gmodel, "usage": usage, "cost_usd": cost}
        calls = [{"name": fc.name, "args": dict(fc.args or {})} for fc in (getattr(r, "function_calls", None) or [])]
        try:
            text = r.text or ""
        except Exception:  # noqa: BLE001
            text = ""
        if calls:
            out["tool_calls"] = calls
        if json_schema:
            out["json"] = parse_json(text)
        out["text"] = text
        return out

    def _llm_openrouter(self, task: str, messages: list[dict], json_schema: dict | None, tools: list[dict] | None) -> dict:
        kw: dict[str, Any] = {"temperature": 0, "max_tokens": 2000}
        msgs = list(messages)
        if json_schema:
            kw["response_format"] = {"type": "json_object"}
            msgs = msgs + [{"role": "user", "content": "Answer ONLY with JSON matching this schema: " + json.dumps(json_schema)}]
        if tools:
            kw["tools"] = [t if "function" in t else {"type": "function", "function": t} for t in tools]
        r, usage, cost = self._or_chat(settings.openrouter_llm_model, msgs, "llm:" + task, **kw)
        msg = r.choices[0].message
        out: dict[str, Any] = {"model": settings.openrouter_llm_model, "usage": usage, "cost_usd": cost, "text": msg.content or ""}
        if getattr(msg, "tool_calls", None):
            out["tool_calls"] = [{"name": tc.function.name, "args": parse_json(tc.function.arguments) or {}, "id": tc.id}
                                 for tc in msg.tool_calls]
        if json_schema:
            out["json"] = parse_json(out["text"])
        return out


gateway = ModelGateway()
