"""Cria anúncios no Meta Ads a partir dos posts que acabaram de sair no Instagram.

Roda na GitHub Action logo depois do publicar.py. Para cada post com
status "publicado" e bloco "anuncio" com status "aprovado", usa o próprio
post do Instagram (source_instagram_media_id) como criativo em cada conjunto
listado em "anuncio.conjuntos", ativa o anúncio e pausa os anúncios antigos
do conjunto, mantendo no máximo MANTER anúncios automáticos ativos.

O modelo do criativo (página, conta do Instagram, botão e link) é copiado de
um anúncio que já existe no conjunto, então o link com UTM continua igual.

post.json:
  "anuncio": {"status": "aprovado", "conjuntos": ["profissionais", "lembranca"]}
Depois de rodar: "status": "criado" com "anuncios": {conjunto: ad_id}, ou "erro".

Os apelidos dos conjuntos e a conta ficam em anuncios.json, na raiz.

Variáveis de ambiente:
  META_ADS_TOKEN   token com ads_management (usuário do sistema)
  META_API_VERSION opcional, padrão v23.0
  DRY_RUN          "1" só mostra o que faria
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
CONFIG = json.loads((RAIZ / "anuncios.json").read_text(encoding="utf-8"))
API = "https://graph.facebook.com/" + os.environ.get("META_API_VERSION", "v23.0")
PREFIXO = "auto · "
MANTER = CONFIG.get("manter_ativos", 2)
ESPERA_MIDIA_S = 900  # o post recém-publicado pode demorar a aparecer para a API de anúncios


class ErroAnuncio(Exception):
    pass


def _api(metodo, caminho, **params):
    params["access_token"] = os.environ["META_ADS_TOKEN"]
    for chave, valor in list(params.items()):
        if isinstance(valor, (dict, list)):
            params[chave] = json.dumps(valor)
    url = f"{API}/{caminho}"
    for tentativa in range(3):
        r = requests.request(metodo, url, data=params if metodo == "POST" else None,
                             params=params if metodo != "POST" else None, timeout=60)
        if r.status_code < 500:
            break
        time.sleep(5 * (tentativa + 1))
    dados = r.json()
    if "error" in dados:
        e = dados["error"]
        msg = e.get("error_user_msg") or e.get("message")
        raise ErroAnuncio(f"{caminho}: {msg}")
    return dados


def _lista(caminho, **params):
    dados = _api("GET", caminho, limit=100, **params)
    return dados.get("data", [])


def conjunto_id(apelido):
    alvo = CONFIG["conjuntos"].get(apelido)
    if not alvo:
        raise ErroAnuncio(f"conjunto '{apelido}' não está em anuncios.json")
    return alvo["id"]


def modelo_do_conjunto(adset):
    """Pega página, conta do Instagram, botão e link de um anúncio que já existe no conjunto."""
    ads = _lista(f"{adset}/ads", fields="id,name,effective_status,created_time,"
                 "creative{object_story_spec,instagram_user_id,call_to_action_type,"
                 "asset_feed_spec,url_tags,object_id,link_url,object_type,source_instagram_media_id,effective_object_story_id}")
    if not ads:
        raise ErroAnuncio(f"conjunto {adset} não tem anúncio para servir de modelo")
    # prefere um anúncio que não foi criado por este script (é o modelo original)
    ads.sort(key=lambda a: (a["name"].startswith(PREFIXO), a.get("effective_status") != "ACTIVE",
                            a.get("created_time", "")))
    cr = ads[0].get("creative", {})
    spec = cr.get("object_story_spec", {})
    page_id = spec.get("page_id") or cr.get("object_id") or \
        (cr.get("effective_object_story_id") or "").split("_")[0] or CONFIG.get("page_id")
    ig_id = spec.get("instagram_user_id") or cr.get("instagram_user_id")
    link, cta = None, None
    for bloco in ("link_data", "video_data"):
        d = spec.get(bloco) or {}
        c = d.get("call_to_action") or {}
        link = link or d.get("link") or (c.get("value") or {}).get("link")
        cta = cta or c.get("type")
    if not link and cr.get("asset_feed_spec"):
        urls = cr["asset_feed_spec"].get("link_urls") or []
        link = urls[0].get("website_url") if urls else None
    cta = cta or cr.get("call_to_action_type")
    return {"page_id": page_id, "ig_id": ig_id or CONFIG.get("instagram_user_id"),
            "link": link or cr.get("link_url"), "cta": cta, "url_tags": cr.get("url_tags"),
            "ads": ads, "bruto": cr}


def criar_anuncio(slug, media_id, apelido, dry, teste=False):
    adset = conjunto_id(apelido)
    m = modelo_do_conjunto(adset)
    m["link"] = CONFIG["conjuntos"][apelido].get("link") or m["link"]
    if not m["page_id"] or not m["ig_id"]:
        raise ErroAnuncio(f"não achei página ou conta do Instagram no modelo do conjunto {apelido}")
    criativo = {
        "name": f"{PREFIXO}{slug}",
        "object_id": m["page_id"],
        "instagram_user_id": m["ig_id"],
        "source_instagram_media_id": media_id,
    }
    if m["link"]:
        criativo["call_to_action"] = {"type": m["cta"] or "LEARN_MORE", "value": {"link": m["link"]}}
    elif m["cta"] == "VIEW_INSTAGRAM_PROFILE":
        criativo["call_to_action"] = {"type": "VIEW_INSTAGRAM_PROFILE"}
    elif m["cta"]:
        raise ErroAnuncio(f"conjunto {apelido} pede botão {m['cta']} mas não tem link (ponha 'link' em anuncios.json)")
    if m["url_tags"]:
        criativo["url_tags"] = m["url_tags"]
    if dry:
        print(f"    [dry] criativo em {apelido}: {criativo}")
        return "dry"

    conta = CONFIG["conta"]
    inicio = time.time()
    while True:
        try:
            cr = _api("POST", f"{conta}/adcreatives", **criativo)
            break
        except ErroAnuncio as e:
            if teste or time.time() - inicio > ESPERA_MIDIA_S:
                raise
            print(f"    criativo ainda não aceito ({e}); tentando de novo em 60 s")
            time.sleep(60)
    if teste:
        # cria pausado (não gasta nada), confere e apaga
        ad = _api("POST", f"{conta}/ads", name=f"teste · apagar · {apelido}", adset_id=adset,
                  creative={"creative_id": cr["id"]}, status="PAUSED")
        print(f"    TESTE ok em {apelido}: criativo {cr['id']} anúncio {ad['id']} {criativo}")
        _api("POST", ad["id"], status="DELETED")
        print("    anúncio de teste apagado")
        return ad["id"]
    ad = _api("POST", f"{conta}/ads", name=f"{PREFIXO}{slug}", adset_id=adset,
              creative={"creative_id": cr["id"]}, status="ACTIVE")

    # pausa os anúncios antigos: todos os manuais e os automáticos além dos MANTER mais novos
    ativos = [a for a in m["ads"] if a.get("effective_status") in
              ("ACTIVE", "PENDING_REVIEW", "IN_PROCESS", "WITH_ISSUES")]
    automaticos = sorted([a for a in ativos if a["name"].startswith(PREFIXO)],
                         key=lambda a: a.get("created_time", ""), reverse=True)
    pausar = [a for a in ativos if not a["name"].startswith(PREFIXO)]
    pausar += automaticos[MANTER - 1:]  # o novo já ocupa uma vaga
    for a in pausar:
        _api("POST", a["id"], status="PAUSED")
        print(f"    pausado: {a['name']}")
    return ad["id"]


def main():
    dry = os.environ.get("DRY_RUN") == "1"
    if not os.environ.get("META_ADS_TOKEN"):
        print("META_ADS_TOKEN não configurado; nada a fazer")
        return
    falhas = 0
    for arquivo in sorted(PASTA_POSTS.glob("*/post.json")):
        post = json.loads(arquivo.read_text(encoding="utf-8"))
        anuncio = post.get("anuncio") or {}
        if post.get("status") != "publicado" or anuncio.get("status") != "aprovado":
            continue
        slug = arquivo.parent.name
        print(f"> {slug}")
        feitos = anuncio.setdefault("anuncios", {})
        try:
            for apelido in anuncio.get("conjuntos", []):
                if apelido in feitos:
                    continue
                feitos[apelido] = criar_anuncio(slug, post["media_id"], apelido, dry)
                print(f"    {apelido}: anúncio {feitos[apelido]}")
            anuncio.update(status="criado",
                           criado_em=datetime.now(timezone.utc).isoformat(timespec="seconds"))
            anuncio.pop("erro", None)
        except (ErroAnuncio, requests.RequestException, KeyError) as e:
            falhas += 1
            anuncio.update(status="erro", erro=str(e))
            print(f"  ERRO: {e}")
        if not dry:
            post["anuncio"] = anuncio
            arquivo.write_text(json.dumps(post, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    sys.exit(1 if falhas else 0)


def validade_token():
    t = os.environ["META_ADS_TOKEN"]
    d = _api("GET", "debug_token", input_token=t).get("data", {})
    exp = d.get("expires_at") or d.get("data_access_expires_at")
    quando = datetime.fromtimestamp(exp, timezone.utc).isoformat() if d.get("expires_at") else "não vence"
    print(f"TOKEN válido={d.get('is_valid')} vence={quando} escopos={d.get('scopes')}")


def listar():
    """Mostra campanhas, conjuntos e anúncios da conta (só leitura), para preencher anuncios.json."""
    validade_token()
    conta = CONFIG["conta"]
    for c in _lista(f"{conta}/campaigns", fields="id,name,objective,effective_status"):
        print(f"CAMPANHA {c['name']} | {c['id']} | {c['objective']} | {c['effective_status']}")
        for s in _lista(f"{c['id']}/adsets", fields="id,name,effective_status,daily_budget,optimization_goal,destination_type"):
            orc = int(s.get("daily_budget") or 0) / 100
            print(f"  CONJUNTO {s['name']} | {s['id']} | {s['effective_status']} | R${orc:.2f} | "
                  f"{s.get('optimization_goal')} | {s.get('destination_type')}")
            for a in _lista(f"{s['id']}/ads", fields="id,name,effective_status"):
                print(f"    ANÚNCIO {a['name']} | {a['id']} | {a['effective_status']}")
    m = _lista("me/businesses", fields="id,name")
    print("NEGÓCIOS", m)


def modelos():
    """Mostra, para cada conjunto do anuncios.json, o modelo que o script vai copiar (só leitura)."""
    for apelido, alvo in CONFIG["conjuntos"].items():
        m = modelo_do_conjunto(alvo["id"])
        print(f"MODELO {apelido}: página={m['page_id']} ig={m['ig_id']} botão={m['cta']} "
              f"link={m['link']} url_tags={m['url_tags']} (de: {m['ads'][0]['name']})")
        print("BRUTO", json.dumps(m["bruto"], ensure_ascii=False))


def desempenho():
    """Resultados por conjunto (dia a dia) e por posicionamento, só leitura."""
    conta = CONFIG["conta"]
    campos = "adset_name,spend,impressions,reach,frequency,clicks,cpm,actions"
    for periodo in ({"since": "2026-11-03", "until": datetime.now(timezone.utc).date().isoformat()},):
        for linha in _lista(f"{conta}/insights", level="adset", fields=campos, time_range=periodo,
                            time_increment=1):
            acoes = {a["action_type"]: a["value"] for a in linha.get("actions", [])}
            print("DIA", linha["date_start"], "|", linha["adset_name"], "| R$", linha["spend"],
                  "| imp", linha["impressions"], "| alc", linha["reach"], "|", json.dumps(acoes))
        for linha in _lista(f"{conta}/insights", level="adset", fields=campos, time_range=periodo,
                            breakdowns="publisher_platform,platform_position"):
            acoes = {a["action_type"]: a["value"] for a in linha.get("actions", [])}
            print("POS", linha["adset_name"], "|", linha["publisher_platform"], linha["platform_position"],
                  "| R$", linha["spend"], "| imp", linha["impressions"], "|", json.dumps(acoes))
        for linha in _lista(f"{conta}/insights", level="adset", fields=campos, time_range=periodo,
                            breakdowns="age"):
            acoes = {a["action_type"]: a["value"] for a in linha.get("actions", [])}
            print("IDADE", linha["adset_name"], "|", linha["age"], "| R$", linha["spend"], "|", json.dumps(acoes))


if __name__ == "__main__":
    if sys.argv[1:] == ["desempenho"]:
        desempenho()
    elif sys.argv[1:] == ["listar"]:
        listar()
        modelos()
    elif sys.argv[1:2] == ["teste"]:
        erros = 0
        for apelido in CONFIG["conjuntos"]:
            try:
                criar_anuncio("teste", sys.argv[2], apelido, False, teste=True)
            except ErroAnuncio as e:
                erros += 1
                print(f"    TESTE ERRO em {apelido}: {e}")
        sys.exit(1 if erros else 0)
    else:
        main()
