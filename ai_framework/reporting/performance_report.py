"""
Performance Report Writer
=========================
Saves latency and token-efficiency data to JSON for trend analysis.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.config import get_config
from core.logger import get_logger

log = get_logger(__name__)
_cfg = get_config()


def save_performance_report(data: dict, path: Optional[Path] = None) -> Path:
    out_path = path or Path(_cfg.reports_dir) / "performance_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {"timestamp": datetime.utcnow().isoformat(), **data}

    existing: list = []
    if out_path.exists():
        try:
            with out_path.open() as f:
                existing = json.load(f)
        except (json.JSONDecodeError, IOError):
            existing = []

    existing.append(entry)
    with out_path.open("w") as f:
        json.dump(existing, f, indent=2)

    log.info(f"Performance report saved → {out_path}")
    return out_path
