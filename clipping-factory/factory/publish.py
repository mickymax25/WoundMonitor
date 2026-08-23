"""Station S9 — publication multi-plateformes via API tierce auditée.

Décisions du dossier câblées ici :
- publication UNIQUEMENT après approbation humaine G4 (S8) ;
- tri-plateforme systématique (TikTok + Reels + Shorts) — même master,
  jamais deux fois le même fichier au même endroit : l'index unique
  (checksum, platform, account) le garantit au niveau base ;
- passage par une API tierce détentrice d'une app auditée (Upload-Post),
  jamais de bot non officiel.

L'endpoint Upload-Post est configurable (UPLOADPOST_ENDPOINT) — à valider
sur le compte réel, comme pour Whop ; le parsing et les règles sont testés
sur stub.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import httpx

from .models import utcnow

PLATFORMS = ("tiktok", "instagram", "youtube")


class PublisherUnavailable(Exception):
    pass


@dataclass
class PostResult:
    platform: str
    external_id: str
    url: str


class Publisher(Protocol):
    name: str

    def post(
        self, video: Path, platform: str, account: str, title: str
    ) -> PostResult: ...


class UploadPostPublisher:
    name = "uploadpost"

    def __init__(self, api_key: str | None = None, endpoint: str | None = None):
        self.api_key = api_key or os.environ.get("UPLOADPOST_API_KEY")
        self.endpoint = endpoint or os.environ.get(
            "UPLOADPOST_ENDPOINT", "https://api.upload-post.com/api/upload"
        )

    def post(
        self, video: Path, platform: str, account: str, title: str
    ) -> PostResult:
        if not self.api_key:
            raise PublisherUnavailable(
                "UPLOADPOST_API_KEY absent — créer un compte upload-post.com"
                " et y connecter les comptes sociaux"
            )
        with open(video, "rb") as fh:
            resp = httpx.post(
                self.endpoint,
                headers={"Authorization": f"Apikey {self.api_key}"},
                data={"title": title, "user": account, "platform[]": platform},
                files={"video": (video.name, fh, "video/mp4")},
                timeout=600,
            )
        resp.raise_for_status()
        payload = resp.json()
        return PostResult(
            platform=platform,
            external_id=str(payload.get("id", payload.get("request_id", ""))),
            url=str(payload.get("url", "")),
        )


class DryRunPublisher:
    """Simule la publication — démo et tests, aucune sortie réseau."""

    name = "dryrun"

    def post(
        self, video: Path, platform: str, account: str, title: str
    ) -> PostResult:
        return PostResult(
            platform=platform,
            external_id=f"dry-{platform}-{video.stem}",
            url=f"https://example.invalid/{platform}/{video.stem}",
        )


def file_checksum(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def publish_render(
    conn: sqlite3.Connection,
    render_id: int,
    publisher: Publisher,
    platforms: list[str],
    account: str,
    title: str | None = None,
) -> list[PostResult]:
    """Publie un render approuvé sur chaque plateforme demandée.

    Refus bloquants : render inconnu, non conforme (G3), non approuvé (G4),
    plateforme inconnue, ou doublon (checksum, platform, account).
    """
    row = conn.execute(
        "SELECT r.*, m.title AS m_title FROM renders r"
        " JOIN moments m ON m.id=r.moment_id WHERE r.id=?",
        (render_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"render {render_id} inconnu")
    if not row["ok"]:
        raise ValueError(f"render {render_id} bloqué par G3 — publication refusée")
    if row["review_status"] != "approved":
        raise ValueError(
            f"render {render_id} non approuvé (G4: {row['review_status']})"
            " — la validation humaine est obligatoire"
        )
    for p in platforms:
        if p not in PLATFORMS:
            raise ValueError(f"plateforme inconnue: {p}")

    video = Path(row["path"])
    checksum = row["checksum"] or file_checksum(video)
    title = title or row["m_title"] or video.stem

    results: list[PostResult] = []
    for platform in platforms:
        dup = conn.execute(
            "SELECT id FROM publications WHERE checksum=? AND platform=? AND account=?",
            (checksum, platform, account),
        ).fetchone()
        if dup:
            raise ValueError(
                f"doublon refusé : ce fichier est déjà publié sur {platform}"
                f" ({account}) — publication #{dup['id']}"
            )
        result = publisher.post(video, platform, account, title)
        conn.execute(
            "INSERT INTO publications (render_id, platform, account, publisher,"
            " external_id, url, checksum, published_at)"
            " VALUES (?,?,?,?,?,?,?,?)",
            (
                render_id, platform, account, publisher.name,
                result.external_id, result.url, checksum, utcnow().isoformat(),
            ),
        )
        results.append(result)
    conn.commit()
    return results
