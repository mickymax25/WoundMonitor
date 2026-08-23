# Usine à Clips

Pipeline de production de clips courts (TikTok / Reels / Shorts) avec réaction IA,
orienté campagnes de clipping rémunérées. Contexte et décisions :

- **`RESEARCH.md`** — dossier de recherche (économie, règles TikTok, droit FR/US, technique)
- **`ARCHITECTURE.md`** — plan d'usine (stations, gates, matrice, phases)
- **`research/`** — les cinq rapports de recherche détaillés

## État : Sprints 1 à 3 — stations S0 à S7

**S0 — radar de campagnes** : scan des sources, gate **G1** (budget restant > 60 %,
CPM ≥ 0,80 $ / 0,40 €, exclusion gambling/crypto, plateformes et audiences
servables), score de priorité (fraîcheur 45 % · budget 30 % · CPM 25 %).

**S1 — sourcing autorisé** : sources de contenu avec autorisation + preuve
obligatoires (règle whitelist du dossier), découverte de nouveaux épisodes par
RSS, téléchargement des enclosures.

**S2 — transcription** : Whisper large-v3-turbo via Groq (`GROQ_API_KEY`,
~0,04 $/h) ou transcript fixture pour le rejeu hors ligne ; segments
horodatés JSON.

**S3 — détection des moments** : scorer heuristique FR/EN sans API (baseline)
et scorer Claude (sorties structurées, `ANTHROPIC_API_KEY`,
modèle via `FACTORY_LLM_MODEL`) ; fenêtres 20–60 s, scores hook/émotion/autonomie,
gate **G2** (composite ≥ `G2_MIN_SCORE`, défaut 7/10).

**S4 — réaction du persona** : script LLM structuré (hook → interruptions
datées → outro) qui ANALYSE l'extrait — writers `llm` (défaut) / `template`
(dégradé) / fixture. **S6 — rendu** : timeline extrait/réaction, TTS
(ElevenLabs ou fixture), sous-titres ASS deux styles, persona PNG-tuber en
overlay pendant les réactions, crédit + badges, MP4 vertical 1080×1920 via
ffmpeg. **S7 — gate G3** : crédit, mention « Collaboration commerciale »
(campagnes), divulgation persona IA, attestation zéro musique, bornes de
durée — un manquement = vidéo bloquée avec motifs.

```bash
pip install -r requirements.txt                       # + ffmpeg requis
python -m pytest tests/ -q                            # 36 tests

# S0
python -m factory.cli radar scan|list|add …
# S1→S3
python -m factory.cli sources add --name "Podcast X" --feed URL --lang fr \
    --auth written --proof "email du 2026-08-12"
python -m factory.cli episodes scan && python -m factory.cli episodes list
python -m factory.cli pipeline run --episode 1        # LLM par défaut
python -m factory.cli moments list --episode 1 -v
# S4→S7
python -m factory.cli produce run --moment 1 --music-cleared
python -m factory.cli renders list
```

Configuration : `FACTORY_DB`, `G1_*`, `G2_MIN_SCORE`, `RADAR_FRESHNESS_WINDOW_H`,
`WHOP_API_KEY`/`WHOP_CAMPAIGNS_ENDPOINT`, `GROQ_API_KEY`, `ANTHROPIC_API_KEY`,
`FACTORY_LLM_MODEL`.

## Prérequis côté opérateur (hors code)

Avant la production réelle : compte Whop (+ clé API) et inscriptions aux
plateformes de campagnes ; compte TikTok/Instagram/YouTube dédiés (warm-up
1–2 semaines) ; abonnement Upload-Post ou Blotato pour la publication ;
clés Groq (transcription), LLM et TTS pour les stations suivantes ;
micro-entreprise avant les premiers revenus.

## Sprints suivants

4. File de validation + publication multi-plateformes + télémétrie (S8–S10)
