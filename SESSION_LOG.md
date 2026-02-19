# WoundChrono — SESSION LOG

## [2026-02-18 22:00] Reprise du projet — Diagnostic parsing MedGemma

### Probleme identifie
Le backend sur la VM GCP ne parse pas correctement la sortie de MedGemma 1.5 4B-IT en mode reel (non-mock). Le modele renvoie du texte avant/apres le JSON, des cles avec casse differente, des scores en plain float, etc.

### Corrections appliquees dans `backend/app/models/medgemma.py`

1. **`_strip_thinking`** : ajout gestion du texte libre (preamble) avant le JSON, pas seulement les tokens `<unused>`.

2. **`_repair_json_string`** (nouveau) : corrige trailing commas, single quotes, texte apres le dernier `}`.

3. **`_extract_json_block`** : utilise `_repair_json_string` sur le JSON extrait.

4. **`_normalize_time_scores`** (nouveau) : porte la logique robuste du script d'annotation 03. Gere :
   - Cles case-insensitive (Tissue, TISSUE, tissue)
   - Prefix matching (Inflam... -> inflammation)
   - Single-letter keys (T, I, M, E)
   - Valeurs dict, float, ou string
   - Scores sur echelles 0-10 ou 0-100 (convertis en 0-1)
   - Cles alternatives (description/observation au lieu de type)

5. **`_extract_scores_regex`** (nouveau) : fallback regex pour extraire les scores depuis du texte libre.

6. **`parse_time_json`** : strategie multi-niveaux (JSON parse + normalize, puis regex fallback).

7. **`classify_time`** : 3 retries avec prompts progressivement plus stricts (au lieu de 2).

8. **`generate_report`** : fallback intelligent si JSON echoue (wrap le texte modele, ou mock report si garbage).

9. **`detect_contradiction`** : accepte l'image reelle au lieu d'un placeholder noir 16x16. Gere "contradiction" comme bool ou string. Try/except pour ne pas crasher l'analyse.

10. **`parse_json_safe`** : double tentative avec repair.

### Correction dans `backend/app/agents/wound_agent.py`
- Passe `image=image` a `detect_contradiction` (step 6).

### Script de debug cree
- `scripts/test_inference_debug.py` : a executer sur la VM pour voir le raw output du modele et diagnostiquer les problemes restants.

### Etat du projet
- Phase 4 (Polish & Submission), deadline 24 fev
- 5 commits non-push sur main
- Beaucoup de fichiers modifies non commites
- LoRA fine-tuning fait (MAE 0.028, adapter 46MB)
- Frontend/backend complets en mode mock
- Reste : tester en mode reel sur VM, video, writeup final, soumission

## [2026-02-18 22:30] Backend reel operationnel sur VM GCP

### Probleme OOM resolu
- MedSigLIP causait CUDA OOM quand charge sur GPU avec MedGemma+LoRA (~10.8GB)
- Solution : force MedSigLIP sur CPU (float32, ~3.5GB RAM) dans `medsiglip.py`
  - `self._infer_device = "cpu"` au lieu de `self.device`
  - Toutes les methodes d'inference utilisent `self._infer_device`

### Test end-to-end reussi (mode reel, non-mock)
- Pipeline complet : patient -> assessment -> upload image -> analyze
- **TIME Classification** fonctionne : scores T=0.2, I=0.8, M=0.5, E=0.4 sur test_chronic.jpg
- **MedSigLIP zero-shot** fonctionne sur CPU : top = "wound with undermined edges" (16.8%)
- **Report generation** fonctionne : rapport markdown structure avec resume clinique, interventions, follow-up
- **Alert system** fonctionne : yellow alert pour "suboptimal healing indicators"
- **Raw model output** : le modele renvoie du JSON dans des backticks markdown (```json ... ```)
  - Le parser `_extract_json_block` + `_normalize_time_scores` gere correctement ce format

### Configuration VM
- VM : `oralya-ai-gpu-a` (europe-west4-a, g2-standard-4, L4 24GB)
- MedGemma 1.5 4B + LoRA : GPU cuda (~10.8GB VRAM)
- MedSigLIP 0.9B : CPU float32 (~3.5GB RAM)
- Backend : uvicorn sur port 8000
- Commande de lancement :
  ```
  cd ~/WoundChrono/backend && WOUNDCHRONO_MOCK_MODELS=false WOUNDCHRONO_DEVICE=cuda \
  WOUNDCHRONO_MEDGEMMA_LORA_PATH=../models/medgemma-wound-lora \
  nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 > ~/woundchrono_backend.log 2>&1 &
  ```

### Reste a faire
- Video demo (3 min) — script deja ecrit dans video_script.md
- Writeup final (3 pages) — draft deja dans writeup.md
- Connecter le frontend au backend reel (verifier CORS, URL)
- Package code et soumission Kaggle
- Deadline : 24 fevrier 2026

## [2026-02-19 00:30] Session nocturne — Descriptions TIME + healing_comment

### Architecture LoRA + Base model pour descriptions TIME
- **Probleme** : le LoRA fine-tune ne retourne que des scores ({"T": 0.3, ...}), pas de descriptions cliniques
- **Solution implementee** : double appel sur le meme GPU, zero recharge modele
  1. `classify_time()` appelle le LoRA pour les scores
  2. `_describe_time_dimensions()` desactive le LoRA (`model.disable_adapter_layers()`), appelle le base MedGemma avec les scores en contexte, puis reactive le LoRA
  3. Le prompt du base model inclut les scores LoRA pour coherence : "This wound was scored: Tissue 0.3/1, ..."
  4. Fallback `_score_to_clinical_description()` si le base model echoue (descriptions courtes basees sur score)
- **Resultat** : descriptions 2-4 mots generees par le modele ("Slough with some necrosis", "Mild perilesional erythema", etc.)
- **Prompt cle** : few-shot avec exemples pour forcer le format 2-4 mots

### Prompt TIME aligne avec LoRA
- Le prompt doit rester proche du training prompt sinon les scores tombent a 0.0
- Prompt actuel : "Classify this wound using the TIME framework. Score T/I/M/E from 0.0 (worst) to 1.0 (best). For each dimension include a brief clinical observation. Respond with JSON only."
- Scores stables : T=0.3, I=0.7, M=0.5, E=0.4

### healing_comment (en cours de test)
- Nouveau champ `healing_comment` dans `AssessmentResponse` et `AnalysisResult`
- Extrait de la section "### Clinical Summary" du rapport modele via `_extract_healing_comment()`
- Sanitisation : supprime caracteres non-ASCII (hallucinations), prend la 1ere phrase si > 120 chars
- Fallback trajectory-aware : "Wound showing improvement since last visit." etc.
- Frontend : `result.healing_comment || healingLabel(healingScore)` dans ReportPanel.tsx
- **NON TESTE en end-to-end** — la session s'est arretee avant le test final

### DB migration VM
- Colonnes ajoutees a `data/woundchrono.db` sur la VM : `source TEXT`, `healing_comment TEXT`
- `db.py` synchronise sur la VM (ajout `count_patient_reported`)

### Fichiers modifies (non deployes completement)
- `backend/app/models/medgemma.py` — LoRA+base model, descriptions, prompts
- `backend/app/agents/wound_agent.py` — healing_comment extraction
- `backend/app/schemas/wound.py` — healing_comment field
- `backend/app/api/routes.py` — healing_comment dans reponses
- `backend/app/db.py` — count_patient_reported
- `frontend/src/lib/types.ts` — healing_comment field
- `frontend/src/components/ReportPanel.tsx` — affiche healing_comment

### SSH flaky
- La connexion SSH vers la VM est instable (host key rotation)
- Workaround : `ssh-keygen -f ~/.ssh/google_compute_known_hosts -R compute.4609806835870617157` avant chaque serie de commandes
- SCP fonctionne bien via `gcloud compute scp`

### Reste a faire
- [ ] Tester healing_comment end-to-end (relancer backend + analyze)
- [ ] Verifier rendu dans le simulateur iOS
- [ ] Video demo (3 min)
- [ ] Writeup final (3 pages)
- [ ] Commit + push
- [ ] Soumission Kaggle — deadline 24 fev

## [2026-02-19 09:00] Session matin — Rename + Writeup finalization

### Rename WoundChrono -> Wound Monitor
- `docs/writeup.md` : toutes les occurrences de "WoundChrono" remplacees par "Wound Monitor"
- PDF regenere via pandoc + Chrome headless
- Le code source (backend/frontend) n'a PAS ete renomme (noms internes, classes, etc.)

### Recherche best practices writeup (session precedente)
- Format soumission : Kaggle Writeups (rich text), PAS un PDF upload
- 5 criteres d'evaluation : HAI-DEF usage, probleme importance, impact reel, faisabilite technique, qualite execution
- Recommandations : ajouter screenshots/images, scenario before/after, cibler "Agent-based workflow" special award
- Le writeup est maintenu en markdown pour faciliter le copier-coller dans Kaggle Writeups

### Reste a faire
- [ ] Tester healing_comment end-to-end sur VM
- [ ] Video demo (3 min) — priorite absolue
- [ ] Formater writeup pour Kaggle Writeups (ajouter images, screenshots)
- [ ] Commit + push
- [ ] Soumission Kaggle — deadline 24 fev

## [2026-02-19 11:00] Corrections writeup + Logo + Etude plausibilite

### Writeup v2 (score reviewer : 8.1/10)
- Corrige formule trajectoire : "cosine distance stored as complementary change metric" (pas "combined")
- Ajoute 6e dataset : "Wound Dataset"
- Ajoute phrase FDA CDS exemption dans Limitations
- Ajoute table Before/After (5 dimensions)

### Logo remplacement
- Nouveau logo `LogoWM_V2.png` (shield + cross medical, cyan/coral gradient)
- Remplace dans 6 fichiers : page.tsx, OnboardingScreen, AuthScreen, Dashboard, p/[token]/page, SettingsPanel
- Supprime imports Heart inutilises

### Etude de plausibilite N=30 — TERMINEE
- 30 analyses sur VM avec inference reelle (pas de mock)
- Script : `scripts/plausibility_study.py`
- **Resultats** :
  - 30 analyses en 29.4 min (avg 58.8s/analyse)
  - TIME Score Distributions (N=30):
    - Tissue: min=0.000, mean=0.260, max=0.500
    - Inflammation: min=0.000, mean=0.547, max=0.800
    - Moisture: min=0.000, mean=0.413, max=0.800
    - Edge: min=0.000, mean=0.397, max=0.700
  - Trajectoires : 2 deteriorating, 2 improving, 3 stable, 3 baseline (visit 2) + 20 baseline (singles + visit 1)
  - Alertes : 4 red, 2 orange, 5 yellow, 19 green
  - **6 resultats all-zero** (T=0 I=0 M=0 E=0) — probablement images non-wound ou parsing failure
- **Contradiction Detection** :
  - 3/10 visit-2 flagged comme contradictions
  - MAIS sur le mauvais groupe : les "coherent_worsening" (nurse dit "worse" + AI dit "stable") flagged comme contradictions
  - Le groupe "contradictory" (nurse dit "better" + AI dit "worse") : 0/5 detected
  - Biais du modele : ne flag pas les notes positives contredisant une deterioration
- Tous les resultats stockes en DB et visibles dans le frontend
- JSON complet : `/home/michaelsiam/WoundChrono/plausibility_results.json`

### INT4 Quantization — EN COURS
- Patch applique via `scripts/apply_int4_quantization.py`
- 3 fichiers modifies : config.py (QUANTIZE_4BIT), medgemma.py (BitsAndBytesConfig), main.py (param passthrough)
- bitsandbytes 0.49.2 deja installe sur VM
- Backend redemarre avec WOUNDCHRONO_QUANTIZE_4BIT=true
- Chargement modele en cours (883 poids a quantifier en NF4)
- Objectif : reduire latence de ~60s a ~20-30s par appel MedGemma

### Reste a faire
- [x] Valider INT4 — ABANDONNE (4x plus lent + hallucinations)
- [x] Fix all-zero scores (MedSigLIP fallback)
- [x] Fix contradiction detection (rule-based pre-check)
- [x] Nurse Q&A feature (dedicated inference call)
- [ ] Video demo (3 min)
- [ ] Formater writeup pour Kaggle Writeups
- [ ] Commit + push
- [ ] Soumission Kaggle — deadline 24 fev

## [2026-02-19 12:00] INT4 abandonne + Fixes + Nurse Q&A

### INT4 Quantization — ABANDONNE
- Test 1 : 247.9s latence (4x pire que bf16 ~60s)
- Test 2 : 128s + hallucinations (texte ukrainien/russe dans les rapports)
- Raison : le modele 4B est trop petit pour beneficier de INT4 sur L4 GPU
- Le compute-bound overhead depasse le gain memoire
- Reverted via `scripts/revert_int4.py` (supprime quantize_4bit de medgemma.py et main.py)
- Erreur peft `TypeError: unhashable type: 'set'` causee par le code INT4 residuel

### Fix 1 : MedSigLIP zero-shot fallback (all-zero scores)
- 20% des analyses (6/30) avaient T=0 I=0 M=0 E=0 (parsing failure)
- Solution : `zeroshot_to_time_fallback()` dans wound_agent.py
- Mappe les labels MedSigLIP (ex: "infected wound with purulent discharge") vers des scores TIME approximatifs
- Moyenne ponderee par les probabilites zero-shot
- Test : T=0.36, I=0.47, M=0.39, E=0.38 (au lieu de tout-zero) — PASS

### Fix 2 : Rule-based contradiction detection
- Le LLM ne detectait pas "nurse dit 'mieux' + AI dit 'deteriorating'" (0/5 dans l'etude)
- Solution : `rule_based_contradiction()` dans wound_agent.py
- Keywords positifs ("better", "healing", "improvement") vs negatifs ("worse", "infect", "necrotic")
- Si nurse positive + trajectory "deteriorating" → contradiction=True (pas besoin du LLM)
- Si ambigue → fallback vers le LLM
- Test : nurse "better" + AI "deteriorating" → contradiction=True — PASS

### Nurse Q&A — V1 (in-JSON) ECHEC, V2 (dedicated call) SUCCES
- **V1 (echec)** : ajouter `nurse_answers` au schema JSON du rapport
  - Le modele 4B ne peut pas gerer un schema JSON complexe avec un array additionnel
  - Resultats : questions hallucinées (pas les vraies questions), reponses dupliquees, caracteres non-ASCII (Tamil, Telugu)
- **V2 (succes)** : appel d'inference dedie `answer_nurse_questions()`
  - Questions extraites du texte par regex (split sur `?`)
  - Prompt focalise : TIME scores en contexte, instructions numbered answers
  - Utilise `_generate_base()` (LoRA desactive) pour le raisonnement clinique
  - Resultat integre dans le rapport via "### Clinical Guidance" apres les interventions
  - Test avec 2 questions nurse :
    - "Should I switch to a foam dressing?" → reponse specifique referençant T=0.2, recommande alginate/hydrocolloid
    - "Is there any sign of infection?" → reponse referençant I=0.8, mentionne signes d'infection a verifier
  - Pas de Clinical Guidance quand pas de questions — PASS
  - Latence : ~120s total (report ~60s + Q&A ~60s)

### Scripts crees
- `scripts/apply_fixes.py` — zero-shot fallback + rule-based contradiction
- `scripts/test_fixes.py` — tests des 2 fixes
- `scripts/apply_nurse_qa.py` — V1 nurse Q&A (abandonne)
- `scripts/fix_nurse_qa_v2.py` — V2 nurse Q&A (dedicated call, schema cleanup)
- `scripts/fix_nurse_qa_v3.py` — V3 fix (_pipeline -> _generate_base)
- `scripts/test_nurse_qa.py` — test nurse Q&A
- `scripts/revert_int4.py` — revert INT4 quantization
- `scripts/refine_nurse_qa_prompt.py` — tentative amelioration prompt V1 (abandonne)

### Etat actuel du backend (VM)
- medgemma.py : rapport JSON simple (sans nurse_answers) + methode answer_nurse_questions()
- wound_agent.py : Step 7b nurse Q&A (apres report, avant alert)
- Pas de code INT4 residuel
- Backend stable sur port 8000
