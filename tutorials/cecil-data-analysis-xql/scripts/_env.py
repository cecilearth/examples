"""Auto-load .env file from the working directory into os.environ.

Looks for .env in the current directory and walks up to the repo root.
No external dependencies. Imported at the top of each skill script so
the user never has to remember `source .env` — it just works.
"""
from __future__ import annotations

import os
from pathlib import Path


def load_dotenv() -> None:
    """Find and load the nearest .env file."""
    cwd = Path.cwd()
    for directory in (cwd, *cwd.parents):
        env_file = directory / ".env"
        if env_file.is_file():
            for line in env_file.read_text().splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, val = line.partition("=")
                key = key.strip()
                val = val.strip().strip("'\"")
                os.environ.setdefault(key, val)
            return
