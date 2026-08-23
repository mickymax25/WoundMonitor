"""Poste de pilotage S8 — mini interface web de validation (localhost).

`python -m factory.cli serve` puis http://127.0.0.1:8787 : la file des clips
prêts (G3 ✓), lecteur vidéo, approbation/rejet en un clic, publication
tri-plateforme. Outil opérateur local, sans authentification — ne pas
exposer sur Internet en l'état.
"""

from __future__ import annotations

import html
import os
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

from . import db, review
from .config import load_settings
from .publish import PLATFORMS, DryRunPublisher, UploadPostPublisher, publish_render

_PAGE = """<!doctype html><html lang="fr"><head><meta charset="utf-8">
<title>Usine à Clips — validation</title>
<style>
 body{{font-family:system-ui,sans-serif;background:#14161B;color:#E9E6DE;
      max-width:880px;margin:0 auto;padding:24px}}
 .card{{background:#1E2129;border:1px solid #2E323C;border-radius:8px;
       padding:16px;margin:16px 0;display:flex;gap:16px}}
 video{{width:200px;border-radius:6px;background:#000}}
 .meta{{flex:1}} .score{{color:#4FC8FF;font-weight:700}}
 button{{border:0;border-radius:6px;padding:8px 14px;cursor:pointer;font-weight:600}}
 .ok{{background:#2E7D4F;color:#fff}} .ko{{background:#B03024;color:#fff}}
 .pub{{background:#4FC8FF;color:#14161B}}
 input[type=text]{{background:#14161B;color:#E9E6DE;border:1px solid #2E323C;
      border-radius:6px;padding:8px;width:100%}}
 form{{display:inline-block;margin:4px 6px 0 0}}
 label{{margin-right:10px;font-size:.9em}}
 .empty{{color:#8b8a85;padding:40px;text-align:center}}
</style></head><body>
<h1>File de validation <small style="color:#8b8a85">(gate G4)</small></h1>
{items}
</body></html>"""

_ITEM = """<div class="card">
<video src="/video/{id}" controls preload="metadata"></video>
<div class="meta">
 <div><span class="score">{score}/10</span> · {duration:.0f}s ·
      [{language}] {source} — <b>{title}</b></div>
 <p style="color:#b9b6ae">{justification}</p>
 <form method="post" action="/approve/{id}"><button class="ok">✓ Approuver</button></form>
 <form method="post" action="/reject/{id}">
   <input type="text" name="note" placeholder="motif du rejet" required>
   <button class="ko">✗ Rejeter</button></form>
 <form method="post" action="/publish/{id}">
   {platform_boxes}
   <input type="text" name="account" placeholder="compte (handle)" required
          style="width:180px">
   <button class="pub">Publier</button></form>
</div>"""


def create_app(db_path: str | None = None) -> FastAPI:
    settings = load_settings()
    path = db_path or settings.db_path
    app = FastAPI(title="Usine à Clips")

    def conn():
        return db.connect(path)

    @app.get("/", response_class=HTMLResponse)
    def index():
        rows = review.pending(conn())
        boxes = "".join(
            f'<label><input type="checkbox" name="platforms" value="{p}"'
            f' checked>{p}</label>' for p in PLATFORMS
        )
        items = "".join(
            _ITEM.format(
                id=r["id"], score=r["score"], duration=r["duration_s"] or 0,
                language=r["language"], source=html.escape(r["source_name"]),
                title=html.escape(r["title"] or ""),
                justification=html.escape(r["justification"] or ""),
                platform_boxes=boxes,
            )
            for r in rows
        ) or '<div class="empty">File vide — lancer `produce run`.</div>'
        return _PAGE.format(items=items)

    @app.get("/video/{render_id}")
    def video(render_id: int):
        row = conn().execute(
            "SELECT path FROM renders WHERE id=?", (render_id,)
        ).fetchone()
        if row is None or not Path(row["path"]).exists():
            raise HTTPException(404)
        return FileResponse(row["path"], media_type="video/mp4")

    @app.post("/approve/{render_id}")
    def approve(render_id: int):
        review.approve(conn(), render_id)
        return RedirectResponse("/", status_code=303)

    @app.post("/reject/{render_id}")
    def reject(render_id: int, note: str = Form(...)):
        review.reject(conn(), render_id, note)
        return RedirectResponse("/", status_code=303)

    @app.post("/publish/{render_id}")
    def publish(
        render_id: int,
        account: str = Form(...),
        platforms: list[str] = Form(default=[]),
    ):
        if not platforms:
            raise HTTPException(422, "aucune plateforme cochée")
        c = conn()
        # approbation implicite si pas encore faite : le clic Publier EST le G4
        row = c.execute(
            "SELECT review_status FROM renders WHERE id=?", (render_id,)
        ).fetchone()
        if row and row["review_status"] == "pending":
            review.approve(c, render_id, note="approuvé via publication")
        try:
            publisher = (
                UploadPostPublisher()
                if os.environ.get("UPLOADPOST_API_KEY")
                else DryRunPublisher()
            )
            results = publish_render(c, render_id, publisher, platforms, account)
        except ValueError as exc:
            raise HTTPException(409, str(exc))
        return HTMLResponse(
            "<meta http-equiv=refresh content='2;url=/'>"
            + "<br>".join(
                f"{r.platform}: {html.escape(r.url or r.external_id)}"
                for r in results
            )
            + f"<p>via {publisher.name}</p>"
        )

    return app
