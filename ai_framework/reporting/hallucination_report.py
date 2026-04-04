"""
Hallucination Report
====================
Saves hallucination curve data and produces a human-readable summary
showing at what token count / conversation turn reliability degrades.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.config import get_config
from core.logger import get_logger
from core.types import HallucinationCurveResult

log = get_logger(__name__)
_cfg = get_config()


def save_hallucination_curve(
    result: HallucinationCurveResult,
    test_name: str,
    path: Optional[Path] = None,
) -> Path:
    out_path = path or Path(_cfg.reports_dir) / "hallucination_curves.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    entry = {
        "test_name": test_name,
        "timestamp": datetime.utcnow().isoformat(),
        "threshold": result.threshold,
        "inflection_token_count": result.inflection_token_count,
        "inflection_turn": result.inflection_turn,
        "safe_token_budget": result.safe_token_budget,
        "data_points": [asdict(dp) for dp in result.data_points],
    }

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

    # Human-readable console summary
    if result.inflection_token_count:
        log.warning(
            f"[bold yellow]Hallucination curve summary[/] | test={test_name}\n"
            f"  Inflection at: turn={result.inflection_turn}, "
            f"tokens={result.inflection_token_count}\n"
            f"  Safe token budget: {result.safe_token_budget}\n"
            f"  → Model reliability degrades after ~{result.safe_token_budget} prompt tokens."
        )
    else:
        log.info(
            f"[green]Hallucination curve summary[/] | test={test_name}\n"
            f"  No inflection detected across {len(result.data_points)} turns.\n"
            f"  Model remained reliable throughout."
        )

    log.info(f"Hallucination curve saved → {out_path}")
    return out_path
