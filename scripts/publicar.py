"""Publica no Instagram os posts aprovados da pasta posts/.

Roda dentro da GitHub Action. Para cada posts/<slug>/post.json com
status "aprovado", cria os containers na API do Instagram, publica e
grava de volta o status "publicado" com o id e o link do post.

Variáveis de ambiente:
  IG_USER_ID       id da conta profissional do Instagram
  IG_ACCESS_TOKEN  token de longa duração (instagram_business_content_publish)
  MEDIA_BASE_URL   endereço público de onde a Meta baixa as imagens,
                   ex.: https://cdn.jsdelivr.net/gh/usuario/repo@<sha>
  IG_API_VERSION   opcional, padrão v23.0
  DRY_RUN          "1" valida tudo sem chamar a API
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

RAIZ = Path(__file__).resolve().parent.parent
PASTA_POSTS = RAIZ / "posts"
API = "https://graph.instagram.com/" + os.environ.get("IG_API_VERSION", "v23.0")
LIMITE_LEGENDA = 2200
LIMITE_HASHTAGS = 30


class ErroPost(Exception):
    pass


def _api(metodo, caminho, **params):
    params["access_token"] = os.environ["IG_ACCESS_TOKEN"]
    url = f"{API}/{caminho}"
    for tentativa in range(3):
        r = requests.request(metodo, url, data=params if metodo == "POST" else None,
                             params=params if metodo == "GET" else None, timeout=60)
        if r.status_code < 500:
            break
        time.sleep(5 * (tentativa + 1))
    dados = r.json()
    if "error" in dados:
        raise ErroPost(f"{caminho}: {dados['error'].get('message')}")
    return dados


def _aguardar_pronto(container_id, limite_s=300):
    inicio = time.time()
    while time.time() - inicio < limite_s:
        status = _api("GET", container_id, fields="status_code").get("status_code")
        if status == "FINISHED":
            return
        if status in ("ERROR", "EXPIRED"):
            raise ErroPost(f"container {container_id} terminou com {status}")
        time.sleep(5)
    raise ErroPost(f"container {container_id} não ficou pronto em {limite_s}s")


def _url_ok(url):
    try:
        r = requests.get(url, timeout=30)
        return r.status_code == 200 and r.headers.get("content-type", "").startswith("image/")
    except requests.RequestException:
        return False


def _escolher_url(bases, caminho, rodadas=6):
    """Testa cada servidor de imagens e devolve o primeiro que entrega o JPEG.
    Se a Meta não consegue baixar, responde "Only photo or video can be accepted"."""
    for i in range(rodadas):
        for base in bases:
            url = f"{base}/{caminho}"
            if _url_ok(url):
                return url
        time.sleep(10)
    raise ErroPost(f"imagem inacessível em todos os servidores: {caminho}")


def _criar_item(ig, tentativas=3, **params):
    for i in range(tentativas):
        try:
            return _api("POST", f"{ig}/media", **params)["id"]
        except ErroPost as e:
            if "Only photo or video" not in str(e) or i == tentativas - 1:
                raise
            time.sleep(20)


def validar(pasta, post):
    imagens = post.get("imagens") or []
    legenda = post.get("legenda", "")
    if not 1 <= len(imagens) <= 10:
        raise ErroPost(f"precisa de 1 a 10 imagens, tem {len(imagens)}")
    for nome in imagens:
        if not nome.lower().endswith((".jpg", ".jpeg")):
            raise ErroPost(f"{nome}: a API só aceita JPEG")
        if not (pasta / nome).is_file():
            raise ErroPost(f"{nome} não existe na pasta")
    if len(legenda) > LIMITE_LEGENDA:
        raise ErroPost(f"legenda com {len(legenda)} caracteres, limite {LIMITE_LEGENDA}")
    if legenda.count("#") > LIMITE_HASHTAGS:
        raise ErroPost(f"mais de {LIMITE_HASHTAGS} hashtags")


def publicar(pasta, post):
    ig = os.environ["IG_USER_ID"]
    bases = [b.strip().rstrip("/") for b in os.environ["MEDIA_BASE_URL"].split(",") if b.strip()]
    rel = pasta.relative_to(RAIZ).as_posix()
    urls = [_escolher_url(bases, f"{rel}/{nome}") for nome in post["imagens"]]

    if len(urls) == 1:
        criacao = _criar_item(ig, image_url=urls[0], caption=post["legenda"])
    else:
        filhos = []
        for url in urls:
            filhos.append(_criar_item(ig, image_url=url, is_carousel_item="true"))
        for cid in filhos:
            _aguardar_pronto(cid)
        criacao = _api("POST", f"{ig}/media", media_type="CAROUSEL",
                       children=",".join(filhos), caption=post["legenda"])["id"]

    _aguardar_pronto(criacao)
    media_id = _api("POST", f"{ig}/media_publish", creation_id=criacao)["id"]
    link = _api("GET", media_id, fields="permalink").get("permalink")
    return media_id, link


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    falhas = 0
    for arquivo in sorted(PASTA_POSTS.glob("*/post.json")):
        pasta = arquivo.parent
        post = json.loads(arquivo.read_text(encoding="utf-8"))
        if post.get("status") != "aprovado":
            continue
        quando = post.get("agendado_para")
        if quando and datetime.fromisoformat(quando) > datetime.now(timezone.utc):
            print(f"> {pasta.name}: agendado para {quando}, ainda não")
            continue
        print(f"> {pasta.name}")
        try:
            validar(pasta, post)
            if dry:
                print("  ok (dry run, nada publicado)")
                continue
            post["status"] = "publicando"
            arquivo.write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            media_id, link = publicar(pasta, post)
            post.update(status="publicado", media_id=media_id, link=link,
                        publicado_em=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            post.pop("erro", None)
            print(f"  publicado: {link}")
        except (ErroPost, requests.RequestException, KeyError) as e:
            falhas += 1
            post.update(status="erro", erro=str(e))
            print(f"  ERRO: {e}")
        if not dry:
            arquivo.write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
