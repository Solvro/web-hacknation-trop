"""Approach (d) on WCSS: structured extraction from ad screenshots with VLMs vs OCR-VLMs (stdlib only, python>=3.8).

Runs inside an allocation that serves OpenAI-compatible vLLM endpoints on localhost:
  srun --jobid=<JOB> --overlap -n1 -c2 --mem=2G python3 vlm_extract.py <img_dir> <out.jsonl> name:port [name:port ...]
For OCR models (paddleocr-vl, glm-ocr) the prompt asks for raw text; for general VLMs a JSON schema.
"""
import base64
import json
import os
import sys
import time
import urllib.request

KEY = open("/lustre/pd03/hpc-dawlin1140-1773687823/hacknation/.api_key").read().strip()
SCHEMA_PROMPT = """Jesteś analitykiem CERT. Na obrazku jest zrzut ekranu reklamy z Facebooka/Instagrama (post sponsorowany)
albo okno 'Szczegóły reklamy' z Biblioteki reklam Meta. Wyciągnij pola i zwróć WYŁĄCZNIE JSON:
{"kind": "feed|adlibrary", "advertiser": "nazwa strony reklamodawcy", "library_id": "cyfry lub null",
 "start_date": "data rozpoczęcia lub null", "caption": "tekst posta pod/nad kreacją, dosłownie",
 "overlay_text": "tekst wypalony na grafice/wideo, dosłownie", "cta": "przycisk", "display_link": "domena wyświetlana lub null",
 "persons": ["rozpoznane osoby publiczne (imię nazwisko) lub opis np. 'nieznany lekarz'"],
 "is_decoy": true/false (czy kreacja jest niezwiązana z przekazem, np. ptak, krajobraz z gry),
 "language": "pl|en|...", "vertical": "investment|health|politics_news|other", "brands": ["podszywane marki/media"],
 "narrative": "1 zdanie po polsku: co reklama sugeruje"}"""
OCR_PROMPT = "OCR: przepisz cały widoczny tekst z obrazu, linia po linii, bez komentarzy."


def call(port, name, img_b64, prompt, max_tokens=900):
    body = {"model": name, "temperature": 0, "max_tokens": max_tokens,
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "user", "content": [
                {"type": "image_url", "image_url": {"url": "data:image/png;base64," + img_b64}},
                {"type": "text", "text": prompt}]}]}
    req = urllib.request.Request(f"http://localhost:{port}/v1/chat/completions", data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    t = time.time()
    try:
        d = json.load(urllib.request.urlopen(req, timeout=300))
        return d["choices"][0]["message"].get("content") or "", round(time.time() - t, 2), d.get("usage")
    except Exception as e:  # noqa: BLE001
        return "ERROR " + str(e)[:300], round(time.time() - t, 2), None


img_dir, out = sys.argv[1], sys.argv[2]
targets = [a.split(":") for a in sys.argv[3:]]
imgs = sorted(f for f in os.listdir(img_dir) if f.endswith(".png"))
with open(out, "a") as fo:
    for name, port in targets:
        ocr = "ocr" in name
        for f in imgs:
            b64 = base64.b64encode(open(os.path.join(img_dir, f), "rb").read()).decode()
            txt, secs, usage = call(port, name, b64, OCR_PROMPT if ocr else SCHEMA_PROMPT)
            rec = {"model": name, "id": f[:-4], "secs": secs, "usage": usage, "raw": txt}
            fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fo.flush()
            print(name, f, secs, txt[:100].replace("\n", " "), flush=True)
