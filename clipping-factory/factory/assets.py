"""Assets du persona — placeholder PNG-tuber en attendant le vrai design.

Le persona v1 est un personnage stylisé (décision n°3 du dossier : jamais
photoréaliste, jamais l'imitation d'une personne réelle). Ce module génère
un placeholder propre ; le design final le remplacera par simple
substitution du fichier.
"""

from __future__ import annotations

from pathlib import Path


def generate_gradient(path: Path, width: int, height: int,
                      top=(23, 26, 33), bottom=(9, 11, 16)) -> Path:
    """Fond dégradé vertical sombre pour les cartes persona."""
    from PIL import Image

    img = Image.new("RGB", (width, height))
    px = img.load()
    for y in range(height):
        t = y / max(1, height - 1)
        color = tuple(int(a + (b - a) * t) for a, b in zip(top, bottom))
        for x in range(width):
            px[x, y] = color
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


def generate_persona_states(outdir: Path, size: int = 640) -> tuple[Path, Path]:
    """Deux états du persona (bouche fermée / ouverte) pour l'animation."""
    from PIL import Image, ImageDraw

    outdir.mkdir(parents=True, exist_ok=True)

    def draw(mouth_open: bool, path: Path) -> Path:
        img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        c = size // 2
        # halo
        d.ellipse([size * 0.03, size * 0.03, size * 0.97, size * 0.97],
                  fill=(79, 200, 255, 40))
        # tête
        d.ellipse([size * 0.10, size * 0.10, size * 0.90, size * 0.90],
                  fill=(79, 200, 255, 255), outline=(11, 13, 18, 255),
                  width=size // 48)
        # yeux
        for x in (0.37, 0.63):
            d.ellipse([size * (x - 0.055), size * 0.36,
                       size * (x + 0.055), size * 0.475],
                      fill=(11, 13, 18, 255))
            d.ellipse([size * (x - 0.018), size * 0.375,
                       size * (x + 0.012), size * 0.41],
                      fill=(235, 245, 250, 255))
        # sourcils
        for x in (0.37, 0.63):
            d.line([size * (x - 0.06), size * 0.315,
                    size * (x + 0.06), size * 0.295],
                   fill=(11, 13, 18, 255), width=size // 40)
        # bouche
        if mouth_open:
            d.ellipse([c - size * 0.13, size * 0.60, c + size * 0.13, size * 0.78],
                      fill=(11, 13, 18, 255))
            d.ellipse([c - size * 0.08, size * 0.70, c + size * 0.08, size * 0.775],
                      fill=(255, 110, 110, 255))
        else:
            d.rounded_rectangle(
                [c - size * 0.10, size * 0.655, c + size * 0.10, size * 0.685],
                radius=size * 0.015, fill=(11, 13, 18, 255))
        path.parent.mkdir(parents=True, exist_ok=True)
        img.save(path)
        return path

    return (draw(False, outdir / "persona-closed.png"),
            draw(True, outdir / "persona-open.png"))


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
