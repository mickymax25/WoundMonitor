# Plan d'usine — Architecture d'industrialisation

**Projet : Usine à Clips · 23 août 2026 · fait suite à `RESEARCH.md` (les contraintes citées y sont sourcées).**

Principe directeur : **industrialiser tout ce que les plateformes n'interdisent pas, et rendre l'interdit inutile.** La force du système ne vient pas de poster plus (puni), mais de trois multiplicateurs légitimes : la **vitesse** d'arrivée sur les campagnes solvables, la **matrice de production** (moments × variantes × plateformes × langues), et la **boucle de données** qui améliore la sélection à chaque publication.

---

## 1. Principes industriels

1. **Flux tiré par la demande.** Ce ne sont pas les vidéos qui cherchent un débouché : ce sont les campagnes solvables (Whop, Vyro, clip.farm…) qui déclenchent les ordres de production. Une vidéo n'est fabriquée que si un débouché payant (campagne) ou stratégique (compte propre en croissance) existe.
2. **Stations découplées par files d'attente.** Chaque étape est un worker indépendant, idempotent et rejouable, qui consomme une file et alimente la suivante. Une panne ou un retard à une station ne bloque pas les autres ; tout job est re-exécutable sans effet de bord.
3. **Quality gates automatiques.** Entre les stations, des seuils chiffrés éliminent le médiocre sans intervention. L'humain n'arbitre que le sommet du funnel (10–15 min/jour).
4. **Duplication : interdite intra-plateforme, systématique inter-plateformes.** Jamais deux fois le même fichier sur une même plateforme (pattern 0 vue, ban) ; toujours le même master exporté vers TikTok + Reels + Shorts (vues agrégées par les campagnes, ~3× l'exposition payable).
5. **Conformité câblée dans la chaîne**, pas contrôlée après coup : musique strippée, crédits incrustés, mentions légales, checklist du brief — ce sont des étapes de fabrication, pas des post-its.
6. **Tout est mesuré.** Chaque moment scoré, chaque variante, chaque publication et ses vues à 24 h/72 h/7 j alimentent une base qui rescore les sources et affine les prompts. Ce dataset propriétaire est l'actif de l'usine — c'est lui qui devient invendable à copier.

---

## 2. La chaîne de production

```
S0  RADAR CAMPAGNES        scan Whop/Vyro/clip.farm/plateformes FR
    (ordres de production) fraîcheur × budget restant × CPM × exigences
        │  gate G1 : budget restant >60%, CPM ≥ seuil, briefs compatibles,
        │            exclusion gambling/crypto
S1  SOURCING AUTORISÉ      assets de campagne, RSS podcasts (fr/en),
    (matière première)     RSS YouTube par chaîne, Twitch Helix, autorisations écrites
S2  TRANSCRIPTION          Groq Whisper large-v3-turbo (0,04 $/h, FR≈EN)
S3  DÉTECTION DES MOMENTS  LLM scoring : hook / émotion / autonomie du segment
        │  gate G2 : score ≥ seuil → fenêtres 20–60 s (top 3–5 par épisode)
S4  RÉACTION               script du persona : analyse le clip, l'interrompt,
    (FR et/ou EN)          prend position ; hook < 2 s
S5  FABRICATION VARIANTES  N montages distincts par moment : hook, point d'entrée,
                           trim, style de captions, angle du commentaire
S6  RENDU MULTI-FORMAT     TTS + PNG-tuber + captions ASS + recadrage vertical ;
                           exports TikTok / Reels / Shorts (safe zones, métadonnées)
S7  CONTRÔLE CONFORMITÉ    gate G3 : musique strippée, crédit source, mention
                           « Collaboration commerciale », durée, checklist du brief
S8  POSTE DE VALIDATION    gate G4 (HUMAIN) : file de clips prêts, aperçu,
                           valider / rejeter / éditer — 10–15 min/jour
S9  PUBLICATION            API tierce auditée (Upload-Post / Blotato) →
                           TikTok + Reels + Shorts simultanés ; fenêtres de post ;
                           3–5 publis/jour/compte/plateforme max
S10 TÉLÉMÉTRIE & PAYOUTS   vues 24h/72h/7j, captures de preuve, soumission aux
                           campagnes, suivi des paiements
        └──► réinjection : rescoring des sources (S0/S1), affinage prompts (S3/S4),
             sélection des styles de variantes gagnants (S5)
```

**Ce qui reste humain, par conception** (cf. RESEARCH.md §5.3) : la validation éditoriale (mur « originalité » + zone grise juridique), le clic de publication (règles API TikTok), le choix des campagnes (engagement contractuel), la gestion des litiges/retraits.

---

## 3. La matrice de production

Un épisode source ne produit pas une vidéo, il produit un arbre :

```
1 épisode ──► 3–5 moments forts ──► × N variantes ──► × 3 plateformes ──► × langues
```

Usage des variantes selon la phase (jamais deux variantes du même moment en même temps sur le même compte) :
- **A/B différé** : publier la variante A, si elle sous-performe re-tenter la variante B à J+3 avec un autre hook — c'est un contenu différent aux yeux de la plateforme.
- **Multi-comptes propres (phase B)** : un compte FR et un compte EN, puis éventuellement un 2ᵉ compte par niche — chaque compte reçoit **sa** variante, jamais le même fichier.
- **Mode agence (phase C)** : les variantes deviennent le stock distribué à d'autres clippeurs qui publient sur leurs propres comptes.

Débit cible : **phase A ≈ 3–5 publications/jour** (1 compte/langue, 1 variante/moment, 3 plateformes) ; **phase B ≈ 20–45 publications/jour** à partir des mêmes 3–5 moments quotidiens — le coût marginal d'une variante est quasi nul (TTS + rendu ≈ centimes), tout le levier est là.

---

## 4. Le modèle de données (l'actif)

```
campaigns    id, plateforme, cpm, budget_restant, exigences (geo/langue/format),
             fenetre_soumission, statut, historique_scans
sources      id, type (campagne|podcast|chaîne|streamer), langue, autorisation
             (campagne|écrite|native), preuve_autorisation, score_historique
episodes     id, source_id, url/asset, durée, date_pub, statut_pipeline
moments      id, episode_id, t_debut, t_fin, score_hook, score_emotion,
             score_autonomie, justification_llm
scripts      id, moment_id, langue, texte, angle, version_prompt
variants     id, moment_id, script_id, style_captions, hook_texte, trim, statut
renders      id, variant_id, plateforme_format, chemin_master, checksum
publications id, render_id, compte, plateforme, campagne_id?, date, url_post
metrics      publication_id, t (24h|72h|7j), vues, likes, complétion, preuve_capture
payouts      campagne_id, periode, vues_soumises, montant, statut, litige?
```

Règles d'or : un `render` n'est jamais publié deux fois sur la même plateforme (contrainte d'unicité `checksum × plateforme × compte`) ; toute `publication` référence l'autorisation de sa `source` ; toute campagne payée déclenche la capture de preuves automatique aux échéances du brief.

---

## 5. Stack technique

Lean d'abord — un monolithe modulaire, pas une cathédrale distribuée :

| Couche | Choix phase A | Pourquoi |
|---|---|---|
| Langage / structure | Python, monorepo `clipping-factory/` | écosystème média/IA, un seul déploiement |
| Files & état | Postgres (ou SQLite au tout début) + table `jobs` (statut, tentatives, worker) | des files robustes sans Kafka/Redis ; tout l'état est requêtable |
| Workers | 1 process par station, boucle poll + verrou ; cron pour S0/S10 | rejouable, débogable, scalable en lançant N process |
| Média | ffmpeg + libass (captions karaoké), MediaPipe (recadrage), PNG-tuber piloté par amplitude | 0 € de licence, CPU-only |
| IA | Groq Whisper (S2), LLM léger classe Haiku/Flash (S3–S4), Cartesia ou ElevenLabs (S6) | coûts RESEARCH.md §5.2 : ~70–120 €/mois tout compris |
| Publication | Upload-Post ou Blotato | API tierces auditées TikTok/Meta/YouTube, multi-plateformes en un appel |
| Poste de pilotage | FastAPI + interface web légère : file de validation S8, dashboard KPIs, radar S0 | l'humain travaille dans UN écran |
| Infra | 1 VPS 8 vCPU + stockage objet pour les masters | suffisant jusqu'à ~20 vidéos/jour |

Évolutions prévues (pas construites d'avance) : passage Postgres managé + workers conteneurisés en phase B ; GPU ponctuel (RunPod) seulement si un avatar animé avancé se justifie aux analytics.

---

## 6. Quality gates chiffrés

| Gate | Station | Critère de passage | Rejet automatique |
|---|---|---|---|
| G1 | S0→S1 | budget restant > 60 %, CPM ≥ 0,80 $/1k (EN) / 0,40 €/1k (FR), brief compatible formats | campagnes gambling/crypto, briefs exigeant > 50 % d'audience d'un pays qu'on ne sert pas |
| G2 | S3→S4 | score composite ≥ 7/10, segment autonome (compréhensible sans contexte), 20–60 s | moments dépendant du contexte, passages musicaux |
| G3 | S7→S8 | musique strippée vérifiée, crédit incrusté, mentions légales, durée & specs du brief | tout manquement — aucune exception manuelle |
| G4 | S8→S9 | validation humaine explicite | par défaut : rien ne part sans clic |

Objectif de funnel : sur ~20 moments détectés/jour, ~8 passent G2, ~5 sont validés en G4 — l'humain ne voit jamais le fond du panier.

---

## 7. Phases d'industrialisation

**Phase A — Atelier (mois 1–2).** Sprints 1–4 de la roadmap (radar → cœur → production → publication). 1 compte/langue warmé, 3–5 publis/jour, variantes limitées à l'A/B différé. Objectif : premier payout (semaines 2–4), ≥ 200 €/mois et > 10 % des clips au-dessus de 10 k vues au mois 2.
**Phase B — Usine (mois 2–4).** Génération de variantes systématique, multi-plateformes complet, 2ᵉ compte par niche, 20–45 publis/jour, dashboard de pilotage complet. Objectif : ≥ 800 €/mois.
**Phase C — Agence / Produit (mois 4+).** Deux débouchés non exclusifs : (1) distribuer les variantes à des clippeurs partenaires publiant sur leurs propres comptes (marge sur campagnes, modèle Bayraktar) ; (2) vendre l'usine en marque blanche aux podcasteurs FR qui veulent leur propre machine à clips (modèle Legend — le succès FR du clipping est un média qui clippe *son propre* contenu).

---

## 8. KPIs du poste de pilotage

- **Délai campagne → première publication** (le KPI de l'edge : viser < 6 h sur une campagne fraîche)
- Débit : publications/jour par plateforme et par langue
- Taux de passage G2 et G4 (santé de la sélection)
- Vues/publication : médiane et p90 à 72 h ; % de clips > 10 k vues
- €/1 000 vues **réalisé** (vs CPM théorique des campagnes) ; € payés/mois ; délais et litiges de payout
- Coût complet/publication (cible : < 0,50 €)
- Santé des comptes : signaux de restriction FYF, strikes, âge/warm-up

---

## 9. Registre des risques industriels

| Risque | Effet | Parade câblée |
|---|---|---|
| Restriction FYF d'un compte | portée → ~0 | un compte par langue/niche, contenu jamais dupliqué intra-plateforme, warm-up, arrêt automatique des posts si signaux de restriction |
| Rafale copyright | terminaison du compte | sources 100 % autorisées (G1/G3), preuves d'autorisation en base, zéro musique |
| Campagne insolvable / rejets post-hoc | travail non payé | G1 (budget restant), captures de preuve automatiques aux échéances, diversification 2–3 campagnes actives |
| Ban de l'API tierce ou changement de règles | publication cassée | abstraction de la couche publication (Upload-Post ⇄ Blotato ⇄ manuel), masters archivés |
| Dérive « AI slop » du format | déclassement algorithmique | le commentaire reste le produit ; revue humaine G4 ; suivi du % de vues organiques |
| Dépendance à une plateforme | fragilité systémique | tri-plateforme par défaut ; le dataset et le pipeline restent l'actif portable |
