"""Lê as métricas dos posts do @roquecneto e imprime uma linha JSON por post.

Só leitura. Roda na GitHub Action "Ler desempenho dos posts".
"""

import json
import os

import requests

API = "https://graph.instagram.com/" + os.environ.get("IG_API_VERSION", "v23.0")
TOKEN = os.environ["IG_ACCESS_TOKEN"]
UID = os.environ["IG_USER_ID"]

METRICAS = ["reach", "views", "saved", "shares", "total_interactions", "likes", "comments", "follows", "profile_visits", "ig_reels_avg_watch_time", "ig_reels_video_view_total_time"]


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


def conta_insights():
    """Métricas da conta (últimos 28 dias) e perfil dos seguidores. Cada chamada isolada."""
    import time
    ate = int(time.time())
    desde = ate - 28 * 86400
    for m in ["reach", "views", "profile_views", "accounts_engaged", "total_interactions",
              "follows_and_unfollows", "website_clicks", "profile_links_taps", "likes", "comments",
              "saves", "shares", "replies"]:
        r = get(f"{UID}/insights", metric=m, period="day", metric_type="total_value", since=desde, until=ate)
        print("CONTA_METRICA " + json.dumps({"metrica": m, "resposta": r.get("data") or r.get("error")}, ensure_ascii=False))
    for m, bd in [("reach", "media_product_type"), ("reach", "follow_type"), ("views", "follow_type"),
                  ("views", "media_product_type")]:
        r = get(f"{UID}/insights", metric=m, period="day", metric_type="total_value", breakdown=bd, since=desde, until=ate)
        print("CONTA_QUEBRA " + json.dumps({"metrica": m, "quebra": bd, "resposta": r.get("data") or r.get("error")}, ensure_ascii=False))
    for bd in ["age", "gender", "city", "country"]:
        r = get(f"{UID}/insights", metric="follower_demographics", period="lifetime", metric_type="total_value",
                timeframe="this_month", breakdown=bd)
        print("SEGUIDORES " + json.dumps({"quebra": bd, "resposta": r.get("data") or r.get("error")}, ensure_ascii=False))
    r = get(f"{UID}/insights", metric="online_followers", period="lifetime", since=ate - 2 * 86400, until=ate)
    print("ONLINE " + json.dumps(r.get("data") or r.get("error"), ensure_ascii=False))


def main():
    conta = get(UID, fields="username,name,biography,website,followers_count,follows_count,media_count")
    print("CONTA " + json.dumps(conta, ensure_ascii=False))
    conta_insights()
    url = f"{UID}/media"
    params = {"fields": "id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count", "limit": 50}
    medias = get(url, **params).get("data", [])
    for m in medias:
        linha = {
            "id": m["id"],
            "data": m["timestamp"][:10],
            "tipo": m.get("media_product_type") or m.get("media_type"),
            "inicio": (m.get("caption") or "").split("\n")[0][:70],
            "legenda_chars": len(m.get("caption") or ""),
            "link": m.get("permalink"),
            "curtidas": m.get("like_count"),
            "comentarios": m.get("comments_count"),
            **insights(m["id"]),
        }
        print("POST " + json.dumps(linha, ensure_ascii=False))


if __name__ == "__main__":
    main()
