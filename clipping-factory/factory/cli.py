"""CLI de l'usine — `python -m factory.cli <commande>`.

Commandes du Sprint 1 (station S0) :
  radar scan [--manual fichier.json]   scanne les sources et met la base à jour
  radar list [--all]                   campagnes classées (par défaut : G1 ✓ seulement)
  radar add                            ajoute une campagne repérée à la main
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

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
