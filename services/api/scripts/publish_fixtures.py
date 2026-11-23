"""Publish the demo adapters from fixtures/adapters.yaml to B2.

    cd services/api && .venv/bin/python scripts/publish_fixtures.py

Uses the dispatcher's own registry code (same publish order and checks as the
API), reading B2 credentials from the repo-root env file.
"""

import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(API_ROOT.parents[1] / ".env")

from app.service.fixtures import load_fixtures, publish_fixtures  # noqa: E402


def main() -> int:
    published = publish_fixtures()
    summary = {
        "fixtures": len(load_fixtures()),
        "published": [f"{d.tenant_id}/{d.adapter}@{d.current_version}" for d in published],
    }
    sys.stdout.write(json.dumps(summary, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
