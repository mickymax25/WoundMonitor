# WoundChrono Video Script (3 minutes)

## SCENE 1 — The Problem (0:00 - 0:25)

**Visual:** Dark background, statistics appearing one by one

**Narration:**
"8.2 million patients in the US live with chronic wounds. The five-year mortality rate is 30 percent — comparable to most cancers. And yet, the way we track whether these wounds are healing or deteriorating hasn't fundamentally changed: a clinician looks at the wound and makes a subjective judgment. Two clinicians assessing the same wound routinely disagree. This inconsistency has real consequences — delayed escalation, missed deterioration, preventable amputations."

---

## SCENE 2 — The Solution (0:25 - 0:50)

**Visual:** Architecture diagram, three model cards appear

**Narration:**
"WoundChrono transforms a smartphone photograph into an objective, quantitative wound trajectory measurement. It uses three Google HAI-DEF models working together: MedGemma for clinical reasoning and structured scoring, MedSigLIP for image embeddings and change detection, and MedASR for transcribing nurse observations. Together, they power an eight-step analysis pipeline that scores wounds using the TIME clinical framework — Tissue, Inflammation, Moisture, and Edge advancement."

---

## SCENE 3 — Demo: First Visit (0:50 - 1:20)

**Visual:** Screen recording — open WoundChrono PWA, select patient Maria G., upload wound photo

**Narration:**
"Let me show you how it works. Here's our dashboard — three patients with chronic wounds. I select Maria G., a 62-year-old with a venous ulcer. I upload a wound photograph from her first visit. The system runs the full pipeline: MedSigLIP computes an image embedding, MedGemma classifies the wound using the TIME framework. Tissue score: 0.7 — healthy granulation. Inflammation: 1.0 — no signs of infection. This is our baseline."

---

## SCENE 4 — Demo: Trajectory Over Time (1:20 - 1:50)

**Visual:** Screen recording — show timeline chart with multiple visits, scores stable

**Narration:**
"Over four weekly visits, the trajectory chart tracks each TIME dimension. Maria's scores remain stable — her venous ulcer is well-managed. But watch what happens with Rosa T., a 55-year-old with a pressure ulcer. Her initial visit shows critical scores — tissue at zero, moisture at zero. By visit two, she improves dramatically. But at visit four, inflammation drops from 1.0 to 0.7. The system detects deterioration and triggers an orange alert."

---

## SCENE 5 — Demo: Alert and Report (1:50 - 2:20)

**Visual:** Screen recording — show orange alert banner, clinical report, contradiction detection

**Narration:**
"The alert tells the supervising clinician: this wound is deteriorating, review the care plan. Below, MedGemma generates a structured clinical report — current wound status, change since last visit, recommended interventions, follow-up timeline. And here's what makes three models better than one: if the nurse dictates 'wound looks better' but the AI detects deterioration, the contradiction detection flags the discrepancy. Neither the AI alone nor the nurse alone catches everything — the disagreement itself is the signal."

---

## SCENE 6 — Impact and Architecture (2:20 - 2:45)

**Visual:** Split screen — architecture diagram left, mobile phone with PWA right

**Narration:**
"WoundChrono runs as a Progressive Web App — installable on any smartphone, with native camera and microphone access. The backend runs on a single GPU with all three models loaded simultaneously. A full analysis takes under 30 seconds. For health equity, this means a community health worker in a rural clinic gets the same objective wound assessment that a specialized wound care center provides. The trajectory tracking detects stagnation weeks earlier than subjective observation."

---

## SCENE 7 — Closing (2:45 - 3:00)

**Visual:** WoundChrono logo, tagline, model logos

**Narration:**
"Chronic wound care lacks an objective instrument. WoundChrono provides one — three HAI-DEF models orchestrated into a single clinical pipeline that transforms a photograph into a quantitative trajectory. The missing measurement in wound care."

**Text on screen:** WoundChrono — Objective Wound Trajectory Assessment
Built with MedGemma + MedSigLIP + MedASR
