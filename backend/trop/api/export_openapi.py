"""Write trop/api/openapi.json: `cd backend && uv run python -m trop.api.export_openapi`."""
import json
import os
from pathlib import Path

os.environ["TROP_MODE"] = "mock"

from trop.api.app import app  # noqa: E402

if __name__ == "__main__":
    out = Path(__file__).parent / "openapi.json"
    out.write_text(json.dumps(app.openapi(), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("wrote", out)
