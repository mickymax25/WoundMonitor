"""Station S8 — gate G4 : la validation humaine.

Par conception (RESEARCH.md §5.3, règles TikTok), RIEN ne se publie sans un
clic humain. Ce module gère la file : seuls les renders conformes (G3 ok)
y entrent ; approuver ouvre la publication (S9), rejeter garde la trace du
pourquoi pour la boucle d'amélioration.
"""

from __future__ import annotations

import sqlite3

from .models import utcnow


def pending(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute(
        """SELECT r.*, m.title, m.score, m.justification, e.title AS ep_title,
                  s.name AS source_name, s.language
           FROM renders r
           JOIN moments m ON m.id = r.moment_id
           JOIN episodes e ON e.id = m.episode_id
           JOIN content_sources s ON s.id = e.source_id
           WHERE r.ok = 1 AND r.review_status = 'pending'
           ORDER BY m.score DESC"""
    ))


def _set_status(
    conn: sqlite3.Connection, render_id: int, status: str, note: str | None
) -> None:
    row = conn.execute(
        "SELECT ok, review_status FROM renders WHERE id=?", (render_id,)
    ).fetchone()
    if row is None:
        raise ValueError(f"render {render_id} inconnu")
    if status == "approved" and not row["ok"]:
        raise ValueError(
            f"render {render_id} bloqué par G3 — corriger avant d'approuver"
        )
    conn.execute(
        "UPDATE renders SET review_status=?, reviewed_at=?, review_note=? WHERE id=?",
        (status, utcnow().isoformat(), note, render_id),
    )
    conn.commit()


def approve(conn: sqlite3.Connection, render_id: int, note: str | None = None) -> None:
    _set_status(conn, render_id, "approved", note)


def reject(conn: sqlite3.Connection, render_id: int, note: str) -> None:
    if not note.strip():
        raise ValueError("un rejet exige un motif (il nourrit la boucle S10→S3)")
    _set_status(conn, render_id, "rejected", note)
