"""Persistance SQLite de l'usine.

SQLite en phase A (cf. ARCHITECTURE.md §5) : un seul fichier, requêtable,
suffisant jusqu'à des dizaines de campagnes et des milliers de publications.
Le schéma reprend le modèle de données d'ARCHITECTURE.md §4 — seules les
tables utiles au Sprint 1 (radar) sont créées ici ; les suivantes arrivent
avec leurs stations.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from .models import Campaign

SCHEMA = """
CREATE TABLE IF NOT EXISTS campaigns (
    key TEXT PRIMARY KEY,                 -- source:external_id
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    name TEXT NOT NULL,
    url TEXT,
    description TEXT,
    currency TEXT,
    cpm REAL,
    budget_total REAL,
    budget_remaining REAL,
    min_payout REAL,
    max_per_video REAL,
    platforms TEXT,                       -- JSON list
    languages TEXT,                       -- JSON list
    audience_requirements TEXT,           -- JSON object {"US": 0.5}
    submission_window_hours REAL,
    status TEXT NOT NULL DEFAULT 'active',
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    -- résultat du dernier passage au gate G1
    g1_passed INTEGER,
    g1_reasons TEXT,                      -- JSON list des motifs de rejet
    score REAL
);

CREATE TABLE IF NOT EXISTS scan_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    sources TEXT,                         -- JSON list des adaptateurs exécutés
    campaigns_seen INTEGER DEFAULT 0,
    campaigns_new INTEGER DEFAULT 0,
    errors TEXT                           -- JSON list
);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def upsert_campaign(conn: sqlite3.Connection, c: Campaign) -> bool:
    """Insère ou met à jour une campagne. Renvoie True si elle est nouvelle.

    `first_seen_at` n'est jamais écrasé : c'est lui qui mesure la fraîcheur
    réelle (le KPI de l'edge, cf. ARCHITECTURE.md §8).
    """
    existing = conn.execute(
        "SELECT first_seen_at FROM campaigns WHERE key = ?", (c.key,)
    ).fetchone()
    is_new = existing is None
    first_seen = c.first_seen_at if is_new else datetime.fromisoformat(
        existing["first_seen_at"]
    )
    conn.execute(
        """
        INSERT INTO campaigns (
            key, source, external_id, name, url, description, currency, cpm,
            budget_total, budget_remaining, min_payout, max_per_video,
            platforms, languages, audience_requirements,
            submission_window_hours, status, first_seen_at, last_seen_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(key) DO UPDATE SET
            name=excluded.name, url=excluded.url, description=excluded.description,
            currency=excluded.currency, cpm=excluded.cpm,
            budget_total=excluded.budget_total,
            budget_remaining=excluded.budget_remaining,
            min_payout=excluded.min_payout, max_per_video=excluded.max_per_video,
            platforms=excluded.platforms, languages=excluded.languages,
            audience_requirements=excluded.audience_requirements,
            submission_window_hours=excluded.submission_window_hours,
            status=excluded.status, last_seen_at=excluded.last_seen_at
        """,
        (
            c.key, c.source, c.external_id, c.name, c.url, c.description,
            c.currency, c.cpm, c.budget_total, c.budget_remaining,
            c.min_payout, c.max_per_video,
            json.dumps(list(c.platforms)), json.dumps(list(c.languages)),
            json.dumps(c.audience_requirements),
            c.submission_window_hours, c.status,
            _iso(first_seen), _iso(c.last_seen_at),
        ),
    )
    return is_new


def save_gate_result(
    conn: sqlite3.Connection,
    key: str,
    passed: bool,
    reasons: list[str],
    score: float | None,
) -> None:
    conn.execute(
        "UPDATE campaigns SET g1_passed=?, g1_reasons=?, score=? WHERE key=?",
        (1 if passed else 0, json.dumps(reasons), score, key),
    )


def load_campaign(conn: sqlite3.Connection, key: str) -> Campaign | None:
    row = conn.execute("SELECT * FROM campaigns WHERE key=?", (key,)).fetchone()
    return _row_to_campaign(row) if row else None


def list_campaigns(
    conn: sqlite3.Connection, only_passed: bool = False
) -> list[sqlite3.Row]:
    q = "SELECT * FROM campaigns WHERE status='active'"
    if only_passed:
        q += " AND g1_passed=1"
    q += " ORDER BY score DESC NULLS LAST, first_seen_at DESC"
    return list(conn.execute(q))


def _row_to_campaign(row: sqlite3.Row) -> Campaign:
    return Campaign(
        source=row["source"],
        external_id=row["external_id"],
        name=row["name"],
        url=row["url"] or "",
        description=row["description"] or "",
        currency=row["currency"] or "USD",
        cpm=row["cpm"],
        budget_total=row["budget_total"],
        budget_remaining=row["budget_remaining"],
        min_payout=row["min_payout"],
        max_per_video=row["max_per_video"],
        platforms=tuple(json.loads(row["platforms"] or "[]")),
        languages=tuple(json.loads(row["languages"] or "[]")),
        audience_requirements=json.loads(row["audience_requirements"] or "{}"),
        submission_window_hours=row["submission_window_hours"],
        status=row["status"],
        first_seen_at=datetime.fromisoformat(row["first_seen_at"]),
        last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
    )
