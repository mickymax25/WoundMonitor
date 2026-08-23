# Usine à Clips

Pipeline de production de clips courts (TikTok / Reels / Shorts) avec réaction IA,
orienté campagnes de clipping rémunérées. Contexte et décisions :

- **`RESEARCH.md`** — dossier de recherche (économie, règles TikTok, droit FR/US, technique)
- **`ARCHITECTURE.md`** — plan d'usine (stations, gates, matrice, phases)
- **`research/`** — les cinq rapports de recherche détaillés

## État : Sprint 1 — Station S0, radar de campagnes

Le radar scanne les sources de campagnes, normalise, applique le gate **G1**
(budget restant > 60 %, CPM ≥ 0,80 $ / 0,40 €, exclusion gambling/crypto,
plateformes et audiences servables) et classe par score
(fraîcheur 45 % · budget 30 % · CPM 25 %).

```bash
pip install -r requirements.txt
python -m pytest tests/ -q          # tests

python -m factory.cli radar scan                      # scan des sources
python -m factory.cli radar list                      # campagnes G1 ✓, classées
python -m factory.cli radar list --all                # tout, avec motifs de rejet
python -m factory.cli radar add --name "Clips podcast X" \
    --cpm 1.5 --currency USD --budget-total 5000 \
    --platforms tiktok,instagram --languages en       # saisie manuelle (jour 1)
```

Sources branchées :
- **manual** — saisie CLI ou fichier JSON (`radar scan --manual campagnes.json`) : utilisable sans aucun compte.
- **whop** — API officielle, nécessite `WHOP_API_KEY` (l'endpoint des campagnes est configurable via `WHOP_CAMPAIGNS_ENDPOINT`, à valider sur un compte réel — le listing public est une app JS non scrapable proprement).
- à venir : Vyro, clip.farm, plateformes FR (adaptateurs `factory/radar/`, interface `base.SourceAdapter`).

Configuration par variables d'environnement : `FACTORY_DB`, `G1_MIN_BUDGET_RATIO`,
`G1_MIN_CPM_USD`, `G1_MIN_CPM_EUR`, `RADAR_FRESHNESS_WINDOW_H`.

## Prérequis côté opérateur (hors code)

Avant la production réelle : compte Whop (+ clé API) et inscriptions aux
plateformes de campagnes ; compte TikTok/Instagram/YouTube dédiés (warm-up
1–2 semaines) ; abonnement Upload-Post ou Blotato pour la publication ;
clés Groq (transcription), LLM et TTS pour les stations suivantes ;
micro-entreprise avant les premiers revenus.

## Sprints suivants

2. Cœur du pipeline : ingestion autorisée → transcription → détection des moments (S1–S3)
3. Production : réaction, TTS, PNG-tuber, captions, rendu multi-format (S4–S7)
4. File de validation + publication + télémétrie (S8–S10)
