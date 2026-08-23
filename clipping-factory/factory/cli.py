"""CLI de l'usine — `python -m factory.cli <commande>`.

Sprint 1 (station S0) :
  radar scan | list | add              campagnes rémunérées, gate G1, scoring

Sprint 2 (stations S1–S3) :
  sources add | list                   sources de contenu AUTORISÉES (RSS podcast…)
  episodes scan | list                 découverte de nouveaux épisodes
  pipeline run --episode N             fetch → transcription → moments (gate G2)
  moments list [--episode N]           moments détectés, classés
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from . import db
from .config import load_settings
from .radar.manual import ManualSource, parse_entry
from .radar.runner import run_scan
from .radar.whop import WhopSource


def cmd_scan(args: argparse.Namespace) -> int:
    settings = load_settings()
    conn = db.connect(settings.db_path)
    sources = [WhopSource(), ManualSource(args.manual)]
    report = run_scan(conn, sources, settings)
    print(
        f"scan terminé : {report.seen} campagnes vues, {report.new} nouvelles, "
        f"{report.passed} passent G1"
    )
    for w in report.warnings:
        print(f"  ⚠ {w}")
    for e in report.errors:
        print(f"  ✗ {e}")
    return 0 if not report.errors else 1


def cmd_list(args: argparse.Namespace) -> int:
    settings = load_settings()
    conn = db.connect(settings.db_path)
    rows = db.list_campaigns(conn, only_passed=not args.all)
    if not rows:
        print("aucune campagne — lancer `radar scan` ou `radar add`")
        return 0
    now = datetime.now(timezone.utc)
    print(f"{'score':>5}  {'G1':<2} {'CPM':>8}  {'budget':>7}  {'âge':>5}  campagne")
    for r in rows:
        age_h = (now - datetime.fromisoformat(r["first_seen_at"])).total_seconds() / 3600
        cpm = f"{r['cpm']:.2f} {r['currency']}" if r["cpm"] else "?"
        ratio = ""
        if r["budget_total"] and r["budget_remaining"] is not None:
            ratio = f"{r['budget_remaining'] / r['budget_total']:.0%}"
        g1 = "✓" if r["g1_passed"] else "✗"
        score = f"{r['score']:.0f}" if r["score"] is not None else "-"
        print(
            f"{score:>5}  {g1:<2} {cpm:>8}  {ratio:>7}  {age_h:>4.0f}h  "
            f"[{r['source']}] {r['name']}"
        )
        if args.all and not r["g1_passed"]:
            for reason in json.loads(r["g1_reasons"] or "[]"):
                print(f"{'':>34}└ {reason}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    settings = load_settings()
    conn = db.connect(settings.db_path)
    slug = "".join(ch if ch.isalnum() else "-" for ch in args.name.lower()).strip("-")
    entry = {
        "external_id": args.id or f"manual-{slug[:48]}",
        "name": args.name,
        "url": args.url or "",
        "currency": args.currency,
        "cpm": args.cpm,
        "budget_total": args.budget_total,
        "budget_remaining": (
            args.budget_remaining
            if args.budget_remaining is not None
            else args.budget_total
        ),
        "platforms": args.platforms.split(",") if args.platforms else ["tiktok"],
        "languages": args.languages.split(",") if args.languages else [],
    }
    campaign = parse_entry(entry)
    db.upsert_campaign(conn, campaign)
    from .radar.gate import evaluate

    result = evaluate(db.load_campaign(conn, campaign.key), settings.radar)
    db.save_gate_result(conn, campaign.key, result.passed, result.reasons, result.score)
    conn.commit()
    verdict = f"G1 ✓ score {result.score}" if result.passed else (
        "G1 ✗ " + "; ".join(result.reasons)
    )
    print(f"ajoutée : {campaign.key} — {verdict}")
    return 0


def cmd_sources_add(args: argparse.Namespace) -> int:
    from . import ingest

    settings = load_settings()
    conn = db.connect(settings.db_path)
    source_id = ingest.add_source(
        conn,
        kind="podcast_rss",
        name=args.name,
        feed_url=args.feed,
        language=args.lang,
        authorization_kind=args.auth,
        authorization_proof=args.proof,
        campaign_key=args.campaign,
    )
    print(f"source #{source_id} ajoutée : {args.name} ({args.lang}, auth={args.auth})")
    return 0


def cmd_sources_list(args: argparse.Namespace) -> int:
    settings = load_settings()
    conn = db.connect(settings.db_path)
    rows = conn.execute("SELECT * FROM content_sources ORDER BY id").fetchall()
    if not rows:
        print("aucune source — `sources add --name … --feed … --lang … --auth … --proof …`")
        return 0
    for r in rows:
        active = "" if r["active"] else " [inactif]"
        print(f"#{r['id']} [{r['language']}] {r['name']} — auth {r['authorization_kind']}"
              f" ({r['authorization_proof']}){active}")
    return 0


def cmd_episodes_scan(args: argparse.Namespace) -> int:
    from . import ingest

    settings = load_settings()
    conn = db.connect(settings.db_path)
    report = ingest.scan_sources(conn)
    print(f"{report['sources']} source(s) scannée(s), "
          f"{report['episodes_new']} nouvel(s) épisode(s), {report['errors']} erreur(s)")
    return 0


def cmd_episodes_list(args: argparse.Namespace) -> int:
    settings = load_settings()
    conn = db.connect(settings.db_path)
    rows = conn.execute(
        "SELECT e.*, s.name AS source_name, s.language FROM episodes e"
        " JOIN content_sources s ON s.id=e.source_id ORDER BY e.id DESC LIMIT 30"
    ).fetchall()
    if not rows:
        print("aucun épisode — lancer `episodes scan`")
        return 0
    for r in rows:
        dur = f" {r['duration_s'] / 60:.0f}min" if r["duration_s"] else ""
        print(f"#{r['id']} [{r['status']:>11}] [{r['language']}]{dur} "
              f"{r['source_name']} — {r['title']}")
    return 0


def cmd_pipeline_run(args: argparse.Namespace) -> int:
    from . import ingest, moments as moments_mod, transcribe as transcribe_mod

    settings = load_settings()
    conn = db.connect(settings.db_path)
    media_dir = args.media_dir
    ep_id = args.episode

    row = conn.execute("SELECT e.*, s.language FROM episodes e"
                       " JOIN content_sources s ON s.id=e.source_id"
                       " WHERE e.id=?", (ep_id,)).fetchone()
    if row is None:
        print(f"épisode {ep_id} inconnu")
        return 1

    try:
        if row["status"] == "new":
            print(f"S1 téléchargement… ({row['audio_url']})")
            ingest.fetch_audio(conn, ep_id, media_dir)
        if conn.execute("SELECT status FROM episodes WHERE id=?", (ep_id,)
                        ).fetchone()["status"] == "fetched":
            transcriber = transcribe_mod.GroqTranscriber()
            print(f"S2 transcription ({transcriber.name})…")
            transcribe_mod.transcribe_episode(conn, ep_id, transcriber, media_dir)

        tr_path = conn.execute("SELECT transcript_path FROM episodes WHERE id=?",
                               (ep_id,)).fetchone()["transcript_path"]
        segments = transcribe_mod.load_transcript(__import__("pathlib").Path(tr_path))
        from .llm import LLMUnavailable, pick_scorer

        try:
            scorer = (moments_mod.HeuristicScorer() if args.scorer == "heuristic"
                      else pick_scorer())
        except LLMUnavailable as exc:
            print(f"✗ {exc}")
            return 1
        print(f"S3 détection des moments ({scorer.name})…")
        candidates = scorer.find_moments(segments, row["language"], top_n=args.top)
        passed = moments_mod.save_moments(conn, ep_id, candidates, scorer.name)
        print(f"{len(candidates)} moment(s) détecté(s), {passed} passent G2"
              f" (seuil {moments_mod.g2_min_score()})")
        return 0
    except (transcribe_mod.TranscriberUnavailable, ValueError) as exc:
        print(f"✗ {exc}")
        return 1


def cmd_moments_list(args: argparse.Namespace) -> int:
    settings = load_settings()
    conn = db.connect(settings.db_path)
    q = ("SELECT m.*, e.title AS ep_title FROM moments m"
         " JOIN episodes e ON e.id=m.episode_id")
    params: tuple = ()
    if args.episode:
        q += " WHERE m.episode_id=?"
        params = (args.episode,)
    q += " ORDER BY m.score DESC"
    rows = conn.execute(q, params).fetchall()
    if not rows:
        print("aucun moment — lancer `pipeline run --episode N`")
        return 0
    for r in rows:
        g2 = "✓" if r["g2_passed"] else "✗"
        print(f"{r['score']:>4}/10 G2 {g2}  [{_fmt_ts(r['t_start'])}–{_fmt_ts(r['t_end'])}]"
              f" {r['title']}")
        if args.verbose:
            print(f"          hook {r['score_hook']} · émotion {r['score_emotion']}"
                  f" · autonomie {r['score_autonomy']} — {r['justification']}")
    return 0


def cmd_produce_run(args: argparse.Namespace) -> int:
    from pathlib import Path

    from . import produce as produce_mod
    from .assets import generate_placeholder_persona
    from .llm import LLMUnavailable, pick_writer
    from .reaction import TemplateReactionWriter
    from .tts import ElevenLabsTTS, FixtureTTS, TTSUnavailable

    settings = load_settings()
    conn = db.connect(settings.db_path)
    media_dir = Path(args.media_dir)

    try:
        writer = (TemplateReactionWriter() if args.writer == "template"
                  else pick_writer())
    except LLMUnavailable as exc:
        print(f"✗ {exc}")
        return 1
    tts = FixtureTTS() if args.tts == "fixture" else ElevenLabsTTS()

    persona = Path(args.persona) if args.persona else media_dir / "persona.png"
    if not persona.exists():
        generate_placeholder_persona(persona)

    try:
        result = produce_mod.produce_moment(
            conn, args.moment, writer, tts, media_dir,
            persona_png=persona, music_cleared=args.music_cleared,
        )
    except (TTSUnavailable, ValueError) as exc:
        print(f"✗ {exc}")
        return 1
    status = "✓ prêt pour validation (S8)" if result.ok else "✗ BLOQUÉ par G3"
    print(f"render #{result.render_id} — {result.out_path}"
          f" ({result.duration_s:.1f}s) {status}")
    for issue in result.issues:
        print(f"   └ {issue}")
    return 0 if result.ok else 1


def cmd_renders_list(args: argparse.Namespace) -> int:
    settings = load_settings()
    conn = db.connect(settings.db_path)
    rows = conn.execute(
        "SELECT r.*, m.title FROM renders r JOIN moments m ON m.id=r.moment_id"
        " ORDER BY r.id DESC LIMIT 30"
    ).fetchall()
    if not rows:
        print("aucun render — lancer `produce run --moment N`")
        return 0
    for r in rows:
        ok = "✓" if r["ok"] else "✗"
        print(f"#{r['id']} {ok} {r['duration_s']:.0f}s [{r['writer']}/{r['tts']}]"
              f" {r['title']} → {r['path']}")
        for issue in json.loads(r["issues"] or "[]"):
            print(f"     └ {issue}")
    return 0


def cmd_queue_list(args: argparse.Namespace) -> int:
    from . import review

    conn = db.connect(load_settings().db_path)
    rows = review.pending(conn)
    if not rows:
        print("file vide — lancer `produce run`")
        return 0
    for r in rows:
        print(f"#{r['id']} {r['score']}/10 {r['duration_s']:.0f}s [{r['language']}]"
              f" {r['source_name']} — {r['title']}")
    return 0


def cmd_queue_review(args: argparse.Namespace) -> int:
    from . import review

    conn = db.connect(load_settings().db_path)
    try:
        if args.queue_command == "approve":
            review.approve(conn, args.render, args.note)
            print(f"render #{args.render} approuvé (G4 ✓)")
        else:
            review.reject(conn, args.render, args.note or "")
            print(f"render #{args.render} rejeté")
    except ValueError as exc:
        print(f"✗ {exc}")
        return 1
    return 0


def cmd_publish_run(args: argparse.Namespace) -> int:
    from .publish import (
        DryRunPublisher, PublisherUnavailable, UploadPostPublisher, publish_render,
    )

    conn = db.connect(load_settings().db_path)
    publisher = (DryRunPublisher() if args.publisher == "dryrun"
                 else UploadPostPublisher())
    try:
        results = publish_render(
            conn, args.render, publisher,
            args.platforms.split(","), args.account, title=args.title,
        )
    except (ValueError, PublisherUnavailable) as exc:
        print(f"✗ {exc}")
        return 1
    for r in results:
        print(f"✓ {r.platform}: {r.url or r.external_id} (via {publisher.name})")
    return 0


def cmd_metrics_record(args: argparse.Namespace) -> int:
    from . import telemetry

    conn = db.connect(load_settings().db_path)
    try:
        telemetry.record(
            conn, args.publication, args.at, args.views,
            likes=args.likes, comments=args.comments, proof_path=args.proof,
        )
    except ValueError as exc:
        print(f"✗ {exc}")
        return 1
    print(f"relevé enregistré : publication #{args.publication} @{args.at}h"
          f" = {args.views} vues")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    from . import telemetry

    conn = db.connect(load_settings().db_path)
    s = telemetry.compute_stats(conn)
    pct = lambda v: f"{v:.0%}" if v is not None else "n/a"
    print(f"épisodes scorés     : {s.episodes_scored}")
    print(f"moments détectés    : {s.moments_detected} (G2 : {pct(s.g2_pass_rate)})")
    print(f"renders conformes   : {s.renders_ok} (approbation : {pct(s.approval_rate)})")
    print(f"publications        : {s.publications}")
    for platform, views in sorted(s.views_by_platform.items()):
        print(f"  vues {platform:<10}: {views}")
    for source, views in sorted(s.views_by_source.items()):
        print(f"  vues {source:<10}: {views}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .webapp import create_app

    uvicorn.run(create_app(), host=args.host, port=args.port)
    return 0


def _fmt_ts(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="factory")
    sub = parser.add_subparsers(dest="command", required=True)

    radar = sub.add_parser("radar", help="station S0 — radar de campagnes")
    radar_sub = radar.add_subparsers(dest="radar_command", required=True)

    p_scan = radar_sub.add_parser("scan")
    p_scan.add_argument("--manual", help="fichier JSON de campagnes saisies à la main")
    p_scan.set_defaults(func=cmd_scan)

    p_list = radar_sub.add_parser("list")
    p_list.add_argument("--all", action="store_true", help="inclure les rejets G1")
    p_list.set_defaults(func=cmd_list)

    p_add = radar_sub.add_parser("add")
    p_add.add_argument("--name", required=True)
    p_add.add_argument("--cpm", type=float, required=True)
    p_add.add_argument("--currency", default="USD", choices=["USD", "EUR"])
    p_add.add_argument("--budget-total", type=float, dest="budget_total")
    p_add.add_argument("--budget-remaining", type=float, dest="budget_remaining")
    p_add.add_argument("--platforms", help="ex: tiktok,instagram,youtube")
    p_add.add_argument("--languages", help="ex: fr,en")
    p_add.add_argument("--url")
    p_add.add_argument("--id")
    p_add.set_defaults(func=cmd_add)

    sources = sub.add_parser("sources", help="station S1 — sources autorisées")
    sources_sub = sources.add_subparsers(dest="sources_command", required=True)
    p_sadd = sources_sub.add_parser("add")
    p_sadd.add_argument("--name", required=True)
    p_sadd.add_argument("--feed", required=True, help="URL du flux RSS")
    p_sadd.add_argument("--lang", required=True, choices=["fr", "en"])
    p_sadd.add_argument("--auth", required=True,
                        choices=["campaign", "written", "native"])
    p_sadd.add_argument("--proof", required=True,
                        help="preuve d'autorisation (email du…, URL campagne…)")
    p_sadd.add_argument("--campaign", help="clé de campagne liée (source:id)")
    p_sadd.set_defaults(func=cmd_sources_add)
    p_slist = sources_sub.add_parser("list")
    p_slist.set_defaults(func=cmd_sources_list)

    episodes = sub.add_parser("episodes", help="découverte d'épisodes")
    episodes_sub = episodes.add_subparsers(dest="episodes_command", required=True)
    episodes_sub.add_parser("scan").set_defaults(func=cmd_episodes_scan)
    episodes_sub.add_parser("list").set_defaults(func=cmd_episodes_list)

    pipeline = sub.add_parser("pipeline", help="stations S1→S3 sur un épisode")
    pipeline_sub = pipeline.add_subparsers(dest="pipeline_command", required=True)
    p_run = pipeline_sub.add_parser("run")
    p_run.add_argument("--episode", type=int, required=True)
    p_run.add_argument(
        "--scorer", choices=["llm", "heuristic"], default="llm",
        help="llm = analyse complète du transcript (défaut, seul chemin de"
             " qualité) ; heuristic = fallback hors ligne / tests",
    )
    p_run.add_argument("--top", type=int, default=5)
    p_run.add_argument("--media-dir", dest="media_dir", default="media")
    p_run.set_defaults(func=cmd_pipeline_run)

    moments = sub.add_parser("moments", help="moments forts détectés")
    moments_sub = moments.add_subparsers(dest="moments_command", required=True)
    p_mlist = moments_sub.add_parser("list")
    p_mlist.add_argument("--episode", type=int)
    p_mlist.add_argument("-v", "--verbose", action="store_true")
    p_mlist.set_defaults(func=cmd_moments_list)

    produce = sub.add_parser("produce", help="stations S4→S7 sur un moment")
    produce_sub = produce.add_subparsers(dest="produce_command", required=True)
    p_prun = produce_sub.add_parser("run")
    p_prun.add_argument("--moment", type=int, required=True)
    p_prun.add_argument("--writer", choices=["llm", "template"], default="llm",
                        help="llm = réaction écrite par le modèle (défaut) ;"
                             " template = gabarit hors ligne (démo/dégradé)")
    p_prun.add_argument("--tts", choices=["elevenlabs", "fixture"],
                        default="elevenlabs")
    p_prun.add_argument("--persona", help="PNG du persona (défaut: placeholder)")
    p_prun.add_argument("--music-cleared", action="store_true", dest="music_cleared",
                        help="attester que l'extrait ne contient pas de musique")
    p_prun.add_argument("--media-dir", dest="media_dir", default="media")
    p_prun.set_defaults(func=cmd_produce_run)

    renders = sub.add_parser("renders", help="vidéos produites (file S8)")
    renders_sub = renders.add_subparsers(dest="renders_command", required=True)
    renders_sub.add_parser("list").set_defaults(func=cmd_renders_list)

    queue = sub.add_parser("queue", help="station S8 — validation humaine (G4)")
    queue_sub = queue.add_subparsers(dest="queue_command", required=True)
    queue_sub.add_parser("list").set_defaults(func=cmd_queue_list)
    for action in ("approve", "reject"):
        p_q = queue_sub.add_parser(action)
        p_q.add_argument("--render", type=int, required=True)
        p_q.add_argument("--note", help="obligatoire pour un rejet")
        p_q.set_defaults(func=cmd_queue_review)

    publish = sub.add_parser("publish", help="station S9 — publication")
    publish_sub = publish.add_subparsers(dest="publish_command", required=True)
    p_pub = publish_sub.add_parser("run")
    p_pub.add_argument("--render", type=int, required=True)
    p_pub.add_argument("--platforms", default="tiktok,instagram,youtube")
    p_pub.add_argument("--account", required=True, help="handle du compte")
    p_pub.add_argument("--publisher", choices=["uploadpost", "dryrun"],
                       default="uploadpost")
    p_pub.add_argument("--title")
    p_pub.set_defaults(func=cmd_publish_run)

    metrics = sub.add_parser("metrics", help="station S10 — relevés de vues")
    metrics_sub = metrics.add_subparsers(dest="metrics_command", required=True)
    p_rec = metrics_sub.add_parser("record")
    p_rec.add_argument("--publication", type=int, required=True)
    p_rec.add_argument("--at", type=int, required=True, choices=[24, 72, 168])
    p_rec.add_argument("--views", type=int, required=True)
    p_rec.add_argument("--likes", type=int)
    p_rec.add_argument("--comments", type=int)
    p_rec.add_argument("--proof", help="chemin de la capture d'écran (preuve)")
    p_rec.set_defaults(func=cmd_metrics_record)

    sub.add_parser("stats", help="KPIs du poste de pilotage").set_defaults(
        func=cmd_stats
    )

    serve = sub.add_parser("serve", help="interface web de validation (S8)")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8787)
    serve.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
