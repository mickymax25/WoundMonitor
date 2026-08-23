"""Station S1 — sourcing autorisé : flux RSS de podcasts et assets de campagne.

Règle de l'usine (RESEARCH.md §3, ARCHITECTURE.md §9) : on n'ingère JAMAIS
une source sans autorisation enregistrée — chaque `content_source` porte son
type d'autorisation et sa preuve. Les enclosures RSS de podcasts sont le
chemin techniquement et juridiquement le plus propre : le MP3 est publié
pour être téléchargé, seule l'autorisation d'en réutiliser des extraits
compte, et elle est tracée ici.
"""

from __future__ import annotations

import re
import sqlite3
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

import httpx

from .models import utcnow

_ITUNES = "{http://www.itunes.com/dtds/podcast-1.0.dtd}"


@dataclass
class FeedEpisode:
    guid: str
    title: str
    audio_url: str
    published_at: str | None
    duration_s: float | None


def parse_feed(xml_text: str) -> list[FeedEpisode]:
    """Parse un flux RSS de podcast (items avec enclosure audio)."""
    root = ET.fromstring(xml_text)
    episodes: list[FeedEpisode] = []
    for item in root.iter("item"):
        enclosure = item.find("enclosure")
        if enclosure is None:
            continue
        url = enclosure.get("url", "")
        if not url:
            continue
        guid_el = item.find("guid")
        title_el = item.find("title")
        pub_el = item.find("pubDate")
        dur_el = item.find(f"{_ITUNES}duration")
        episodes.append(
            FeedEpisode(
                guid=(guid_el.text or url).strip() if guid_el is not None else url,
                title=(title_el.text or "sans titre").strip()
                if title_el is not None
                else "sans titre",
                audio_url=url,
                published_at=pub_el.text.strip() if pub_el is not None and pub_el.text else None,
                duration_s=_parse_duration(dur_el.text) if dur_el is not None else None,
            )
        )
    return episodes


def _parse_duration(raw: str | None) -> float | None:
    if not raw:
        return None
    raw = raw.strip()
    if re.fullmatch(r"\d+(\.\d+)?", raw):
        return float(raw)
    parts = raw.split(":")
    try:
        seconds = 0.0
        for part in parts:
            seconds = seconds * 60 + float(part)
        return seconds
    except ValueError:
        return None


def add_source(
    conn: sqlite3.Connection,
    *,
    kind: str,
    name: str,
    language: str,
    authorization_kind: str,
    authorization_proof: str,
    feed_url: str | None = None,
    campaign_key: str | None = None,
) -> int:
    if authorization_kind not in ("campaign", "written", "native"):
        raise ValueError(f"autorisation inconnue: {authorization_kind}")
    if not authorization_proof.strip():
        raise ValueError("preuve d'autorisation obligatoire (email, URL de campagne…)")
    cur = conn.execute(
        "INSERT INTO content_sources (kind, name, feed_url, language,"
        " authorization_kind, authorization_proof, campaign_key, created_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (
            kind, name, feed_url, language, authorization_kind,
            authorization_proof, campaign_key, utcnow().isoformat(),
        ),
    )
    conn.commit()
    return cur.lastrowid


def scan_sources(
    conn: sqlite3.Connection, fetch=None, max_episodes_per_source: int = 5
) -> dict[str, int]:
    """Interroge les flux des sources actives et enregistre les nouveaux épisodes.

    `fetch(url) -> str` est injectable pour les tests ; par défaut HTTP réel.
    Seuls les épisodes les plus récents entrent (le backlog n'a pas de valeur
    de fraîcheur pour les clips).
    """
    fetch = fetch or _http_fetch
    report = {"sources": 0, "episodes_new": 0, "errors": 0}
    rows = conn.execute(
        "SELECT * FROM content_sources WHERE active=1 AND kind='podcast_rss'"
    ).fetchall()
    for row in rows:
        report["sources"] += 1
        try:
            feed_episodes = parse_feed(fetch(row["feed_url"]))
        except Exception:
            report["errors"] += 1
            continue
        for ep in feed_episodes[:max_episodes_per_source]:
            cur = conn.execute(
                "INSERT OR IGNORE INTO episodes (source_id, guid, title, audio_url,"
                " published_at, duration_s, status, discovered_at)"
                " VALUES (?,?,?,?,?,?, 'new', ?)",
                (
                    row["id"], ep.guid, ep.title, ep.audio_url,
                    ep.published_at, ep.duration_s, utcnow().isoformat(),
                ),
            )
            report["episodes_new"] += cur.rowcount
    conn.commit()
    return report


def fetch_audio(
    conn: sqlite3.Connection, episode_id: int, media_dir: str | Path, fetch_bytes=None
) -> Path:
    """Télécharge l'enclosure audio d'un épisode → statut 'fetched'."""
    fetch_bytes = fetch_bytes or _http_fetch_bytes
    row = conn.execute("SELECT * FROM episodes WHERE id=?", (episode_id,)).fetchone()
    if row is None:
        raise ValueError(f"épisode {episode_id} inconnu")
    media_dir = Path(media_dir)
    media_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(row["audio_url"].split("?")[0]).suffix or ".mp3"
    path = media_dir / f"episode-{episode_id}{suffix}"
    path.write_bytes(fetch_bytes(row["audio_url"]))
    conn.execute(
        "UPDATE episodes SET status='fetched', audio_path=? WHERE id=?",
        (str(path), episode_id),
    )
    conn.commit()
    return path


def _http_fetch(url: str) -> str:
    resp = httpx.get(url, timeout=30, follow_redirects=True)
    resp.raise_for_status()
    return resp.text


def _http_fetch_bytes(url: str) -> bytes:
    resp = httpx.get(url, timeout=300, follow_redirects=True)
    resp.raise_for_status()
    return resp.content
