"""Baixa as imagens de posts já publicados (para reaproveitar em anúncios).

Só leitura na API. Uso: python scripts/baixar_midia.py <media_id> [<media_id> ...]
Grava em midia/<media_id>/01.jpg, 02.jpg, ... e a legenda em legenda.txt.
"""

import os
import sys
from pathlib import Path

import requests

API = "https://graph.instagram.com/" + os.environ.get("IG_API_VERSION", "v23.0")
TOKEN = os.environ["IG_ACCESS_TOKEN"]
RAIZ = Path(__file__).resolve().parent.parent


def get(caminho, **params):
    r = requests.get(f"{API}/{caminho}", params={"access_token": TOKEN, **params}, timeout=60)
    r.raise_for_status()
    return r.json()


def main():
    for mid in sys.argv[1:]:
        info = get(mid, fields="caption,media_type,media_url")
        pasta = RAIZ / "midia" / mid
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / "legenda.txt").write_text(info.get("caption") or "", encoding="utf-8")
        if info.get("media_type") == "CAROUSEL_ALBUM":
            urls = [c["media_url"] for c in get(f"{mid}/children", fields="media_url,media_type")["data"]
                    if c.get("media_type") == "IMAGE"]
        else:
            urls = [info["media_url"]]
        for i, u in enumerate(urls, 1):
            (pasta / f"{i:02d}.jpg").write_bytes(requests.get(u, timeout=120).content)
        print(f"{mid}: {len(urls)} imagens")


if __name__ == "__main__":
    main()
