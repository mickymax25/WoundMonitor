"""Assets du persona — placeholder PNG-tuber en attendant le vrai design.

Le persona v1 est un personnage stylisé (décision n°3 du dossier : jamais
photoréaliste, jamais l'imitation d'une personne réelle). Ce module génère
un placeholder propre ; le design final le remplacera par simple
substitution du fichier.
"""

from __future__ import annotations

from pathlib import Path


def generate_placeholder_persona(path: Path, size: int = 512) -> Path:
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c = size // 2
    # tête
    d.ellipse([size * 0.08, size * 0.08, size * 0.92, size * 0.92],
              fill=(79, 200, 255, 255), outline=(20, 22, 27, 255), width=size // 40)
    # yeux
    for x in (0.36, 0.64):
        d.ellipse([size * (x - 0.06), size * 0.34, size * (x + 0.06), size * 0.46],
                  fill=(20, 22, 27, 255))
    # bouche (état « parle »)
    d.ellipse([c - size * 0.14, size * 0.60, c + size * 0.14, size * 0.76],
              fill=(20, 22, 27, 255))
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path
