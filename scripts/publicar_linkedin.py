"""Publica no LinkedIn (perfil pessoal) os posts aprovados para o LinkedIn.

Roda dentro da GitHub Action, depois do Instagram. Um post vai para o LinkedIn
quando o post.json tem o bloco:

  "linkedin": {"status": "aprovado", "texto": "opcional: texto próprio do LinkedIn"}

Sem "texto", usa a "legenda" do Instagram. Grava de volta em "linkedin":
status "publicado", "urn", "link" e "publicado_em" (ou status "erro" e "erro").

Formatos:
  carrossel (imagens)  vira um post de documento (PDF), que o leitor folheia no feed
  uma imagem           post de imagem
  vídeo (story/reels)  post de vídeo nativo

Variáveis de ambiente:
  LINKEDIN_TOKEN       token de acesso (escopos openid, profile, w_member_social)
  LINKEDIN_VERSION     opcional, versão da API no formato AAAAMM
  DRY_RUN              "1" valida tudo sem chamar a API
"""

import io
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from PIL import Image

RAIZ = Path(__file__).resolve().parent.parent
PASTA_POSTS = RAIZ / "posts"
API = "https://api.linkedin.com"
LIMITE_TEXTO = 3000
RESERVADOS = set("\\|{}@[]()<>#*_~")


class ErroPost(Exception):
    pass


def _cab(extra=None):
    h = {
        "Authorization": f"Bearer {os.environ['LINKEDIN_TOKEN']}",
        "LinkedIn-Version": os.environ.get("LINKEDIN_VERSION") or "202608",
        "X-Restli-Protocol-Version": "2.0.0",
    }
    h.update(extra or {})
    return h


def _req(metodo, url, **kw):
    for tentativa in range(3):
        r = requests.request(metodo, url, timeout=120, **kw)
        if r.status_code < 500 and r.status_code != 429:
            break
        time.sleep(5 * (tentativa + 1))
    if r.status_code >= 400:
        raise ErroPost(f"{metodo} {url.split('?')[0]}: {r.status_code} {r.text[:300]}")
    return r


def autor():
    sub = _req("GET", f"{API}/v2/userinfo", headers={"Authorization": f"Bearer {os.environ['LINKEDIN_TOKEN']}"}).json()["sub"]
    return f"urn:li:person:{sub}"


def texto_linkedin(texto):
    """O LinkedIn usa um formato próprio no texto: caracteres especiais precisam de barra,
    e hashtag clicável vira {hashtag|\\#|palavra}."""
    partes = []
    for pedaco in re.split(r"(#\w+)", texto):
        if re.fullmatch(r"#\w+", pedaco):
            partes.append("{hashtag|\\#|" + pedaco[1:] + "}")
        else:
            partes.append("".join("\\" + c if c in RESERVADOS else c for c in pedaco))
    return "".join(partes)


def _subir_imagem(dono, caminho):
    ini = _req("POST", f"{API}/rest/images?action=initializeUpload", headers=_cab({"Content-Type": "application/json"}),
               json={"initializeUploadRequest": {"owner": dono}}).json()["value"]
    _req("PUT", ini["uploadUrl"], data=Path(caminho).read_bytes(),
         headers={"Authorization": f"Bearer {os.environ['LINKEDIN_TOKEN']}"})
    return ini["image"]


def _subir_documento(dono, jpgs):
    paginas = [Image.open(j).convert("RGB") for j in jpgs]
    buf = io.BytesIO()
    paginas[0].save(buf, "PDF", save_all=True, append_images=paginas[1:], resolution=150)
    ini = _req("POST", f"{API}/rest/documents?action=initializeUpload", headers=_cab({"Content-Type": "application/json"}),
               json={"initializeUploadRequest": {"owner": dono}}).json()["value"]
    _req("PUT", ini["uploadUrl"], data=buf.getvalue(),
         headers={"Authorization": f"Bearer {os.environ['LINKEDIN_TOKEN']}"})
    return ini["document"]


def _subir_video(dono, caminho):
    dados = Path(caminho).read_bytes()
    ini = _req("POST", f"{API}/rest/videos?action=initializeUpload", headers=_cab({"Content-Type": "application/json"}),
               json={"initializeUploadRequest": {"owner": dono, "fileSizeBytes": len(dados),
                                                 "uploadCaptions": False, "uploadThumbnail": False}}).json()["value"]
    etags = []
    for parte in ini["uploadInstructions"]:
        r = _req("PUT", parte["uploadUrl"], data=dados[parte["firstByte"]:parte["lastByte"] + 1],
                 headers={"Content-Type": "application/octet-stream"})
        etags.append(r.headers.get("etag") or r.headers.get("ETag"))
    _req("POST", f"{API}/rest/videos?action=finalizeUpload", headers=_cab({"Content-Type": "application/json"}),
         json={"finalizeUploadRequest": {"video": ini["video"], "uploadToken": ini.get("uploadToken", ""),
                                         "uploadedPartIds": etags}})
    urn = ini["video"]
    for _ in range(60):  # espera o LinkedIn processar
        st = _req("GET", f"{API}/rest/videos/{requests.utils.quote(urn, safe='')}", headers=_cab()).json().get("status")
        if st == "AVAILABLE":
            break
        if st == "PROCESSING_FAILED":
            raise ErroPost("o LinkedIn não conseguiu processar o vídeo")
        time.sleep(10)
    return urn


def titulo(post):
    primeira = (post.get("legenda") or "").strip().split("\n")[0]
    return (primeira[:180] or "Post")


def validar(pasta, post):
    li = post["linkedin"]
    texto = li.get("texto") or post.get("legenda", "")
    if len(texto) > LIMITE_TEXTO:
        raise ErroPost(f"texto com {len(texto)} caracteres, limite {LIMITE_TEXTO} no LinkedIn")
    arquivos = [post["video"]] if post.get("video") else (post.get("imagens") or [])
    if not arquivos:
        raise ErroPost("post sem imagem nem vídeo")
    for nome in arquivos:
        if not (pasta / nome).is_file():
            raise ErroPost(f"{nome} não existe na pasta")


def publicar(pasta, post):
    dono = autor()
    li = post["linkedin"]
    texto = texto_linkedin(li.get("texto") or post.get("legenda", ""))
    if post.get("video"):
        media = {"id": _subir_video(dono, pasta / post["video"]), "title": titulo(post)}
    elif len(post["imagens"]) == 1:
        media = {"id": _subir_imagem(dono, pasta / post["imagens"][0]), "altText": titulo(post)}
    else:
        media = {"id": _subir_documento(dono, [pasta / n for n in post["imagens"]]), "title": titulo(post)}
    corpo = {
        "author": dono,
        "commentary": texto,
        "visibility": "PUBLIC",
        "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []},
        "content": {"media": media},
        "lifecycleState": "PUBLISHED",
        "isReshareDisabledByAuthor": False,
    }
    r = _req("POST", f"{API}/rest/posts", headers=_cab({"Content-Type": "application/json"}), json=corpo)
    urn = r.headers.get("x-restli-id") or r.headers.get("X-RestLi-Id")
    return urn, f"https://www.linkedin.com/feed/update/{urn}/"


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    if not dry and not os.environ.get("LINKEDIN_TOKEN"):
        print("LinkedIn: sem LINKEDIN_TOKEN, pulando")
        return
    falhas = 0
    for arquivo in sorted(PASTA_POSTS.glob("*/post.json")):
        pasta = arquivo.parent
        post = json.loads(arquivo.read_text(encoding="utf-8"))
        li = post.get("linkedin")
        if not isinstance(li, dict) or li.get("status") != "aprovado":
            continue
        quando = li.get("agendado_para") or post.get("agendado_para")
        if quando and datetime.fromisoformat(quando) > datetime.now(timezone.utc):
            print(f"> {pasta.name} (LinkedIn): agendado para {quando}, ainda não")
            continue
        print(f"> {pasta.name} (LinkedIn)")
        try:
            validar(pasta, post)
            if dry:
                print("  ok (dry run, nada publicado)")
                continue
            li["status"] = "publicando"
            arquivo.write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            urn, link = publicar(pasta, post)
            li.update(status="publicado", urn=urn, link=link,
                      publicado_em=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            li.pop("erro", None)
            print(f"  publicado: {link}")
        except (ErroPost, requests.RequestException, KeyError) as e:
            falhas += 1
            li.update(status="erro", erro=str(e))
            print(f"  ERRO: {e}")
        if not dry:
            arquivo.write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.exit(1 if falhas else 0)


if __name__ == "__main__":
    main()
