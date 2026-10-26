"""Lê as métricas dos posts do @roquecneto e imprime uma linha JSON por post.

Só leitura. Roda na GitHub Action "Ler desempenho dos posts".
"""

import json
import os

import requests

API = "https://graph.instagram.com/" + os.environ.get("IG_API_VERSION", "v23.0")
TOKEN = os.environ["IG_ACCESS_TOKEN"]
UID = os.environ["IG_USER_ID"]

METRICAS = ["reach", "views", "saved", "shares", "total_interactions", "likes", "comments", "follows", "profile_visits"]


def get(caminho, **params):
    r = requests.get(f"{API}/{caminho}", params={"access_token": TOKEN, **params}, timeout=60)
    return r.json()


def insights(media_id):
    dados = {}
    for m in METRICAS:  # uma por vez: métrica não suportada num tipo de mídia derruba a chamada inteira
        r = get(f"{media_id}/insights", metric=m)
        if "data" in r and r["data"]:
            dados[m] = r["data"][0]["values"][0]["value"]
        elif "error" in r and m == "reach":
            dados["erro"] = r["error"].get("message")
    return dados


def main():
    conta = get(UID, fields="username,followers_count,media_count")
    print("CONTA " + json.dumps(conta, ensure_ascii=False))
    url = f"{UID}/media"
    params = {"fields": "id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count", "limit": 50}
    medias = get(url, **params).get("data", [])
    for m in medias:
        linha = {
            "data": m["timestamp"][:10],
            "tipo": m.get("media_product_type") or m.get("media_type"),
            "inicio": (m.get("caption") or "").split("\n")[0][:70],
            "link": m.get("permalink"),
            "curtidas": m.get("like_count"),
            "comentarios": m.get("comments_count"),
            **insights(m["id"]),
        }
        print("POST " + json.dumps(linha, ensure_ascii=False))


if __name__ == "__main__":
    main()
