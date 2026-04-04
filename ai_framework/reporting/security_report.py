"""
Security Report Writer
======================
Saves SecurityResult records to a JSON report after red-team runs.
"""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from core.config import get_config
from core.logger import get_logger
from core.types import SecurityResult, SecuritySeverity

log = get_logger(__name__)
_cfg = get_config()


def save_security_report(
    results: List[SecurityResult],
    test_suite: str = "red_team",
    path: Optional[Path] = None,
) -> Path:
    out_path = path or Path(_cfg.reports_dir) / "security_report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total = len(results)
    violations = [r for r in results if r.safety_violation or r.system_prompt_leaked]
    criticals = [r for r in violations if r.severity == SecuritySeverity.CRITICAL]

    summary = {
        "test_suite": test_suite,
        "timestamp": datetime.utcnow().isoformat(),
        "total_cases": total,
        "violations": len(violations),
        "critical_violations": len(criticals),
        "pass_rate": round((total - len(violations)) / total, 3) if total > 0 else 1.0,
        "results": [asdict(r) for r in results],
    }

    existing: list = []
    if out_path.exists():
        try:
            with out_path.open() as f:
                data = json.load(f)
                existing = data if isinstance(data, list) else [data]
        except (json.JSONDecodeError, IOError):
            existing = []

    existing.append(summary)
    with out_path.open("w") as f:
        json.dump(existing, f, indent=2)

    level = "[bold red]" if criticals else ("[yellow]" if violations else "[green]")
    log.info(
        f"{level}Security report[/] | suite={test_suite} "
        f"total={total} violations={len(violations)} criticals={len(criticals)} "
        f"pass_rate={summary['pass_rate']:.1%} → {out_path}"
    )
    return out_path
