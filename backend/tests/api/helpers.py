import json


def sse_events(resp_text: str) -> list[tuple[str, dict]]:
    out, ev = [], None
    for line in resp_text.splitlines():
        if line.startswith("event:"):
            ev = line[6:].strip()
        elif line.startswith("data:") and ev:
            out.append((ev, json.loads(line[5:].strip())))
            ev = None
    return out
