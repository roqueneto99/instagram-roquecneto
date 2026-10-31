"""Chamadas à API do Instagram (login do Instagram, graph.instagram.com)."""

import hashlib
import hmac
import os
import time

import httpx

import db

VERSAO = os.environ.get("IG_API_VERSION", "v23.0")
API = f"https://graph.instagram.com/{VERSAO}"
JANELA = 24 * 3600
JANELA_HUMANO = 7 * 24 * 3600


class ErroMeta(Exception):
    pass


def token():
    return db.get("ig_token") or os.environ["IG_ACCESS_TOKEN"]


def ig_id():
    return os.environ.get("IG_USER_ID", "me")


def _req(metodo, caminho, **kw):
    url = caminho if caminho.startswith("http") else f"{API}/{caminho}"
    for tentativa in range(3):
        try:
            r = httpx.request(metodo, url, headers={"Authorization": f"Bearer {token()}"}, timeout=30, **kw)
        except httpx.HTTPError as e:
            if tentativa == 2:
                raise ErroMeta(str(e))
            time.sleep(2 * (tentativa + 1))
            continue
        if r.status_code < 500:
            break
        time.sleep(2 * (tentativa + 1))
    dados = r.json() if r.content else {}
    if r.status_code >= 400 or "error" in dados:
        msg = dados.get("error", {}).get("message") if isinstance(dados, dict) else r.text
        raise ErroMeta(f"{caminho.split('?')[0]}: {msg or r.text[:200]}")
    return dados


def assinatura_ok(corpo: bytes, cabecalho: str | None) -> bool:
    """Confere o X-Hub-Signature-256. Aceita mais de um segredo (APP_SECRET separado por vírgula),
    porque o app tem o segredo do app da Meta e o segredo do app do Instagram."""
    segredos = [s.strip() for s in os.environ.get("APP_SECRET", "").split(",") if s.strip()]
    if not segredos:
        return True  # sem segredo configurado, não confere (só para testes)
    if not cabecalho or not cabecalho.startswith("sha256="):
        return False
    recebido = cabecalho.split("=", 1)[1]
    return any(hmac.compare_digest(hmac.new(s.encode(), corpo, hashlib.sha256).hexdigest(), recebido)
               for s in segredos)


def enviar_dm(igsid, texto, humano=False):
    """Envia texto para quem já falou com a conta. Fora das 24h só sai se for resposta
    humana (tag HUMAN_AGENT, até 7 dias)."""
    ct = db.contato(igsid)
    ultima = (ct["ultima_entrada"] if ct else None) or 0
    passou = db.agora() - ultima
    corpo = {"recipient": {"id": igsid}, "message": {"text": texto[:1000]}}
    if passou > JANELA:
        if not humano or passou > JANELA_HUMANO:
            raise ErroMeta("fora da janela de resposta da Meta (24 horas, ou 7 dias para resposta humana)")
        corpo.update(messaging_type="MESSAGE_TAG", tag="HUMAN_AGENT")
    return _req("POST", f"{ig_id()}/messages", json=corpo)


def resposta_privada(comment_id, texto):
    """Manda um direct para quem comentou (uma vez por comentário, até 7 dias)."""
    return _req("POST", f"{ig_id()}/messages", json={"recipient": {"comment_id": comment_id},
                                                     "message": {"text": texto[:1000]}})


def responder_comentario(comment_id, texto):
    return _req("POST", f"{comment_id}/replies", params={"message": texto})


def perfil(igsid):
    try:
        return _req("GET", igsid, params={"fields": "name,username"})
    except ErroMeta:
        return {}


def renovar_token():
    """Token de longa duração vale 60 dias; renovar estica mais 60. Guarda no banco."""
    r = httpx.get("https://graph.instagram.com/refresh_access_token",
                  params={"grant_type": "ig_refresh_token", "access_token": token()}, timeout=30)
    dados = r.json()
    if "access_token" not in dados:
        raise ErroMeta(f"renovar token: {dados}")
    db.put("ig_token", dados["access_token"])
    db.put("ig_token_renovado", db.agora())
    return dados.get("expires_in")


def assinar_webhooks():
    return _req("POST", f"{ig_id()}/subscribed_apps",
                params={"subscribed_fields": "messages,comments"})
