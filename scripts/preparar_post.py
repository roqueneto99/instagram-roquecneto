"""Monta a pasta de um post a partir dos PNGs e da legenda.

Uso:
  python scripts/preparar_post.py <slug> <legenda.txt> img1.png img2.png ...

Converte cada PNG para JPEG 1080x1350 (a API só aceita JPEG), copia para
posts/<data>-<slug>/ e grava post.json com status "rascunho".
Para publicar, troque o status para "aprovado" e faça push.
"""

import json
import sys
from datetime import date
from pathlib import Path

from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent


def main():
    if len(sys.argv) < 4:
        sys.exit(__doc__)
    slug, arquivo_legenda, *pngs = sys.argv[1:]
    pasta = RAIZ / "posts" / f"{date.today().isoformat()}-{slug}"
    pasta.mkdir(parents=True, exist_ok=True)

    nomes = []
    for i, png in enumerate(pngs, 1):
        img = Image.open(png).convert("RGB")
        if img.size != (1080, 1350):
            img = img.resize((1080, 1350), Image.LANCZOS)
        nome = f"{i:02d}.jpg"
        img.save(pasta / nome, "JPEG", quality=95, optimize=True)
        nomes.append(nome)

    post = {
        "status": "rascunho",
        "imagens": nomes,
        "legenda": Path(arquivo_legenda).read_text(encoding="utf-8").strip(),
    }
    (pasta / "post.json").write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(pasta)


if __name__ == "__main__":
    main()
