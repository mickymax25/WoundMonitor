"""Station S10 — télémétrie : relevés de vues, preuves de payout, KPIs.

V1 : relevés saisis par l'opérateur aux échéances 24 h / 72 h / 7 j (les
briefs de campagne exigent souvent des captures d'écran à ces horodatages —
`proof_path` les archive). La collecte automatique par API viendra quand
les comptes seront branchés. Les KPIs suivent ARCHITECTURE.md §8.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from .models import utcnow

CHECKPOINT_HOURS = (24, 72, 168)


def record(
    conn: sqlite3.Connection,
    publication_id: int,
    at_hours: int,
    views: int,
    likes: int | None = None,
    comments: int | None = None,
    proof_path: str | None = None,
) -> None:
    if at_hours not in CHECKPOINT_HOURS:
        raise ValueError(f"échéance invalide {at_hours} — attendu {CHECKPOINT_HOURS}")
    if conn.execute(
        "SELECT id FROM publications WHERE id=?", (publication_id,)
    ).fetchone() is None:
        raise ValueError(f"publication {publication_id} inconnue")
    conn.execute(
        "INSERT INTO metrics (publication_id, at_hours, views, likes, comments,"
        " proof_path, recorded_at) VALUES (?,?,?,?,?,?,?)"
        " ON CONFLICT(publication_id, at_hours) DO UPDATE SET"
        " views=excluded.views, likes=excluded.likes, comments=excluded.comments,"
        " proof_path=excluded.proof_path, recorded_at=excluded.recorded_at",
        (
            publication_id, at_hours, views, likes, comments, proof_path,
            utcnow().isoformat(),
        ),
    )
    conn.commit()


@dataclass
class Stats:
    episodes_scored: int
    moments_detected: int
    g2_pass_rate: float | None
    renders_ok: int
    approval_rate: float | None
    publications: int
    views_by_platform: dict[str, int]
    views_by_source: dict[str, int]


def compute_stats(conn: sqlite3.Connection) -> Stats:
    one = lambda q, p=(): conn.execute(q, p).fetchone()[0]

    moments_total = one("SELECT COUNT(*) FROM moments")
    g2_passed = one("SELECT COUNT(*) FROM moments WHERE g2_passed=1")
    reviewed = one(
        "SELECT COUNT(*) FROM renders WHERE review_status IN ('approved','rejected')"
    )
    approved = one("SELECT COUNT(*) FROM renders WHERE review_status='approved'")

    def latest_views(group_sql: str, join_sql: str = "") -> dict[str, int]:
        rows = conn.execute(
            f"""SELECT {group_sql} AS grp, SUM(v.views) AS views FROM (
                    SELECT publication_id, MAX(at_hours) AS at_hours
                    FROM metrics GROUP BY publication_id
                ) last
                JOIN metrics v ON v.publication_id=last.publication_id
                                AND v.at_hours=last.at_hours
                JOIN publications p ON p.id=v.publication_id
                {join_sql}
                GROUP BY grp"""
        ).fetchall()
        return {r["grp"]: r["views"] for r in rows}

    return Stats(
        episodes_scored=one("SELECT COUNT(*) FROM episodes WHERE status='scored'"),
        moments_detected=moments_total,
        g2_pass_rate=(g2_passed / moments_total) if moments_total else None,
        renders_ok=one("SELECT COUNT(*) FROM renders WHERE ok=1"),
        approval_rate=(approved / reviewed) if reviewed else None,
        publications=one("SELECT COUNT(*) FROM publications"),
        views_by_platform=latest_views("p.platform"),
        views_by_source=latest_views(
            "s.name",
            "JOIN renders r ON r.id=p.render_id"
            " JOIN moments m ON m.id=r.moment_id"
            " JOIN episodes e ON e.id=m.episode_id"
            " JOIN content_sources s ON s.id=e.source_id",
        ),
    )
