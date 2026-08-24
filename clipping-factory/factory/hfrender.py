"""Station S6 — finition HyperFrames (habillage animé haut de gamme).

Division du travail avec ffmpeg (`vrender.make_mixed_master`) :
- ffmpeg pré-fabrique le « master mixé » : recadrage vertical, punch-ins,
  audio complet (voix + ducking) — le déterministe lourd ;
- HyperFrames rend l'habillage : sous-titres kinétiques mot-à-mot,
  cartes du persona, persona animé (GSAP, entrées à ressort + flottement),
  barre de progression, badges — le motion design.

La composition est générée depuis les données du pipeline (captions, cues)
puis rendue localement : `npx hyperframes render`. Contrat de composition :
.agents/skills/hyperframes-core (une timeline GSAP pausée, déterministe).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

from .vrender import VoiceCue

GSAP_CDN = "https://cdn.jsdelivr.net/npm/gsap@3.14.2/dist/gsap.min.js"
FONTS = ("https://fonts.googleapis.com/css2?family=Archivo+Black&"
         "family=Archivo:wght@600&display=block")


def word_timings(text: str, start: float, end: float) -> list[dict]:
    """Répartit la fenêtre entre les mots au prorata de leur longueur."""
    words = text.split()
    if not words:
        return []
    weights = [len(w) + 1 for w in words]
    span = max(0.1, end - start)
    scale = span / sum(weights)
    out, t = [], start
    for w, weight in zip(words, weights):
        out.append({"w": w, "t": round(t, 3)})
        t += weight * scale
    return out


def generate_composition(
    total: float,
    captions: list[tuple[float, float, str]],
    cues: list[VoiceCue],
    credit_text: str,
    badges: list[str],
    width: int,
    height: int,
) -> str:
    # une seule ligne de sous-titre à l'écran : chaque fenêtre est bornée
    # par le début de la suivante
    clamped = []
    ordered = sorted(captions, key=lambda c: c[0])
    for i, (a, b, txt) in enumerate(ordered):
        if i + 1 < len(ordered):
            b = min(b, ordered[i + 1][0] - 0.05)
        if b - a > 0.2:
            clamped.append((a, b, txt))
    # lignes courtes : max ~6 mots à l'écran (une longue phrase devient
    # plusieurs cartons successifs, chacun sur la fenêtre de ses mots)
    MAX_WORDS = 6
    cap_data = []
    for a, b, txt in clamped:
        words = word_timings(txt, a, b)
        chunks = [words[i:i + MAX_WORDS] for i in range(0, len(words), MAX_WORDS)]
        for j, chunk in enumerate(chunks):
            start = a if j == 0 else chunk[0]["t"]
            end = b if j == len(chunks) - 1 else chunks[j + 1][0]["t"] - 0.03
            if end - start > 0.15:
                cap_data.append({"start": round(start, 3),
                                 "end": round(end, 3), "words": chunk})
    cue_data = [
        {"start": round(c.start, 3), "end": round(c.start + c.duration, 3),
         "text": c.text}
        for c in cues
    ]
    badge_text = " · ".join(badges)
    fs_cap = int(height * 0.034)
    fs_cue = int(height * 0.029)
    fs_meta = int(height * 0.016)

    return f"""<!doctype html>
<html lang="fr">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width={width}, height={height}" />
    <title>Usine à Clips</title>
    <script src="{GSAP_CDN}"></script>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="{FONTS}" rel="stylesheet" />
    <style>
      * {{ box-sizing: border-box; margin: 0; padding: 0; }}
      html, body {{
        width: {width}px; height: {height}px; overflow: hidden;
        background: #0B0D12;
        font-family: "Archivo Black", "Archivo", sans-serif;
      }}
      .capline {{
        position: absolute; left: 6%; right: 6%; bottom: 19%;
        text-align: center; font-size: {fs_cap}px; line-height: 1.32;
        color: #fff; text-transform: none;
        text-shadow: 0 0 14px rgba(0,0,0,.85), 3px 3px 0 #101010,
                     -3px 3px 0 #101010, 3px -3px 0 #101010, -3px -3px 0 #101010;
      }}
      .capline .w {{ display: inline-block; opacity: .4; margin: 0 .14em; }}
      .cueline {{
        position: absolute; left: 9%; right: 9%; top: 11.5%;
        text-align: center; font-size: {fs_cue}px; line-height: 1.32;
        color: #FFC84F;
        text-shadow: 0 0 16px rgba(0,0,0,.9), 3px 3px 0 #101010,
                     -3px 3px 0 #101010, 3px -3px 0 #101010, -3px -3px 0 #101010;
      }}
      #persona {{
        position: absolute; right: 14px; bottom: {int(height * 0.145)}px;
        width: {int(width * 0.34)}px;
        filter: drop-shadow(0 10px 24px rgba(0,0,0,.55));
      }}
      #bar {{
        position: absolute; top: 0; left: 0; width: 100%;
        height: {max(6, int(height * 0.006))}px;
        background: #4FC8FF; transform-origin: left center;
      }}
      .meta {{
        position: absolute; left: 4%; right: 4%; text-align: center;
        font-family: "Archivo", sans-serif; font-weight: 600;
        font-size: {fs_meta}px; color: rgba(210,210,210,.85);
        text-shadow: 0 1px 6px rgba(0,0,0,.9);
      }}
    </style>
  </head>
  <body>
    <div id="root" data-composition-id="clip" data-start="0"
         data-duration="{total:.3f}" data-width="{width}" data-height="{height}">
      <video id="master" class="clip" src="mixed.mp4"
        data-start="0" data-duration="{total:.3f}" data-track-index="0"
        data-has-audio="true" playsinline
        style="position:absolute; inset:0; width:100%; height:100%;
               object-fit:cover; z-index:0;"></video>
      <div id="overlay" style="position:absolute; inset:0; z-index:1;">
        <div id="caps"></div>
        <div id="cues"></div>
        <img id="persona" src="persona.png" alt="" />
        <div id="bar"></div>
        <div class="meta" style="top:26px;">{badge_text}</div>
        <div class="meta" style="bottom:22px;">{credit_text}</div>
      </div>
    </div>

    <script>
      const CAPTIONS = {json.dumps(cap_data, ensure_ascii=False)};
      const CUES = {json.dumps(cue_data, ensure_ascii=False)};
      const TOTAL = {total:.3f};

      window.__timelines = window.__timelines || {{}};
      const tl = gsap.timeline({{ paused: true }});

      // barre de progression
      tl.fromTo("#bar", {{ scaleX: 0 }},
                {{ scaleX: 1, duration: TOTAL, ease: "none" }}, 0);

      // sous-titres karaoké de l'extrait (une ligne par phrase, pop par mot)
      const caps = document.getElementById("caps");
      CAPTIONS.forEach((c, i) => {{
        const line = document.createElement("div");
        line.className = "capline";
        line.id = "cap-" + i;
        c.words.forEach((wd, j) => {{
          const s = document.createElement("span");
          s.className = "w";
          s.id = "cap-" + i + "-w" + j;
          s.textContent = wd.w;
          line.appendChild(s);
        }});
        caps.appendChild(line);
        tl.set(line, {{ autoAlpha: 0 }}, 0);
        tl.set(line, {{ autoAlpha: 1 }}, c.start);
        tl.set(line, {{ autoAlpha: 0 }}, c.end);
        c.words.forEach((wd, j) => {{
          tl.fromTo("#cap-" + i + "-w" + j,
            {{ opacity: 0.4, scale: 0.92, y: 4 }},
            {{ opacity: 1, scale: 1, y: 0, duration: 0.18,
               ease: "back.out(2.2)" }},
            Math.min(wd.t, c.end - 0.05));
        }});
      }});

      // interventions du persona : carte texte en haut + persona animé
      const cuesEl = document.getElementById("cues");
      tl.set("#persona", {{ autoAlpha: 0 }}, 0);
      CUES.forEach((c, i) => {{
        const line = document.createElement("div");
        line.className = "cueline";
        line.id = "cue-" + i;
        line.textContent = c.text;
        cuesEl.appendChild(line);
        const dur = c.end - c.start;

        tl.set(line, {{ autoAlpha: 0 }}, 0);
        tl.fromTo(line,
          {{ autoAlpha: 0, y: 46, scale: 0.9 }},
          {{ autoAlpha: 1, y: 0, scale: 1, duration: 0.45,
             ease: "back.out(1.6)" }}, c.start);
        tl.to(line, {{ autoAlpha: 0, y: -26, duration: 0.3,
                       ease: "power2.in" }}, Math.max(c.start, c.end - 0.3));

        // entrée à ressort, flottement pendant la prise de parole, sortie
        tl.fromTo("#persona",
          {{ autoAlpha: 0, y: 90, rotation: -6, scale: 0.85 }},
          {{ autoAlpha: 1, y: 0, rotation: 0, scale: 1, duration: 0.5,
             ease: "back.out(1.8)" }}, c.start);
        const bobRepeats = Math.max(0, Math.floor((dur - 1.2) / 1.1));
        if (bobRepeats > 0) {{
          tl.to("#persona", {{ y: -12, duration: 0.55, ease: "sine.inOut",
                               yoyo: true, repeat: bobRepeats * 2 - 1 }},
                c.start + 0.55);
          tl.to("#persona", {{ rotation: 2.5, duration: 1.05,
                               ease: "sine.inOut", yoyo: true,
                               repeat: bobRepeats - 1 }}, c.start + 0.55);
        }}
        tl.to("#persona", {{ autoAlpha: 0, y: 70, duration: 0.35,
                             ease: "power2.in" }},
              Math.max(c.start + 0.5, c.end - 0.35));
      }});

      window.__timelines["clip"] = tl;
    </script>
  </body>
</html>
"""


def render_hyperframes(
    mixed_mp4: Path,
    total: float,
    captions: list[tuple[float, float, str]],
    cues: list[VoiceCue],
    persona_keyed_png: Path | None,
    workdir: Path,
    out_path: Path,
    credit_text: str,
    badges: list[str],
    width: int,
    height: int,
    quality: str = "high",
    timeout_s: int = 1200,
) -> Path:
    """Génère le projet HyperFrames et rend le MP4 final localement."""
    project = workdir / "hf-project"
    if not (project / "package.json").exists():
        subprocess.run(
            ["npx", "-y", "hyperframes", "init", str(project),
             "--non-interactive", "--example", "blank"],
            check=True, capture_output=True, text=True, timeout=600,
        )
    shutil.copy(mixed_mp4, project / "mixed.mp4")
    if persona_keyed_png is not None:
        # recadre sur le personnage détouré (les marges transparentes de
        # l'image générée rendraient le persona minuscule à largeur fixe)
        from PIL import Image

        img = Image.open(persona_keyed_png).convert("RGBA")
        bbox = img.getbbox()
        (img.crop(bbox) if bbox else img).save(project / "persona.png")
    else:
        # pixel transparent : le persona reste simplement invisible
        from PIL import Image

        Image.new("RGBA", (8, 8), (0, 0, 0, 0)).save(project / "persona.png")

    (project / "index.html").write_text(
        generate_composition(total, captions, cues, credit_text, badges,
                             width, height),
        encoding="utf-8",
    )

    lint = subprocess.run(
        ["npx", "hyperframes", "lint"],
        cwd=project, capture_output=True, text=True, timeout=600,
    )
    if lint.returncode != 0:
        raise RuntimeError(f"hyperframes lint: {lint.stdout[-1200:]}"
                           f"{lint.stderr[-400:]}")

    render = subprocess.run(
        ["npx", "hyperframes", "render", "--quality", quality,
         "--output", "out.mp4"],
        cwd=project, capture_output=True, text=True, timeout=timeout_s,
    )
    if render.returncode != 0 or not (project / "out.mp4").exists():
        raise RuntimeError(f"hyperframes render: {render.stdout[-1200:]}"
                           f"{render.stderr[-400:]}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(project / "out.mp4", out_path)
    return out_path
