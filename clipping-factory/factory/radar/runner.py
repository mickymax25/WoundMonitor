"""Orchestration d'un scan radar : sources → upsert → gate G1 → classement."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field

from .. import db
from ..config import Settings
from ..models import utcnow
from .base import SourceAdapter, SourceUnavailable
from .gate import evaluate


@dataclass
class ScanReport:
    seen: int = 0
    new: int = 0
    passed: int = 0
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def run_scan(
    conn: sqlite3.Connection,
    sources: list[SourceAdapter],
    settings: Settings,
) -> ScanReport:
    report = ScanReport()
    started = utcnow()

    for source in sources:
        try:
            campaigns = source.fetch()
        except SourceUnavailable as exc:
            report.warnings.append(str(exc))
            continue
        except Exception as exc:  # une source cassée ne bloque pas les autres
            report.errors.append(f"{source.name}: {exc}")
            continue

        for c in campaigns:
            is_new = db.upsert_campaign(conn, c)
            report.seen += 1
            report.new += int(is_new)
            # G1 s'évalue sur l'état stocké (first_seen_at préservé → fraîcheur vraie).
            stored = db.load_campaign(conn, c.key)
            result = evaluate(stored, settings.radar)
            db.save_gate_result(conn, c.key, result.passed, result.reasons, result.score)
            report.passed += int(result.passed)

    conn.execute(
        "INSERT INTO scan_runs (started_at, finished_at, sources, campaigns_seen,"
        " campaigns_new, errors) VALUES (?,?,?,?,?,?)",
        (
            started.isoformat(),
            utcnow().isoformat(),
            json.dumps([s.name for s in sources]),
            report.seen,
            report.new,
            json.dumps(report.warnings + report.errors),
        ),
    )
    conn.commit()
    return report
