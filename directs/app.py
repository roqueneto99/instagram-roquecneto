"""Atendente de directs do @roquecneto.

Recebe os webhooks do Instagram (mensagens e comentários), responde o "comentou, recebeu",
pede à IA uma resposta para cada direct e deixa no painel para o Roque aprovar. Categorias
simples podem sair sozinhas quando o modo automático está ligado no painel.
"""

import asyncio
import html
import json
import logging
import os
import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import BackgroundTasks, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, RedirectResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials

import db
import ia
import meta

log = logging.getLogger("directs")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI(title="Directs @roquecneto", docs_url=None, redoc_url=None)
basic = HTTPBasic()
BRT = timezone(timedelta(hours=-3))


@app.on_event("startup")
async def _inicio():
    db.iniciar()
    if db.get("modo") is None:
        db.put("modo", "rascunho")
    asyncio.create_task(_rotina_token())


async def _rotina_token():
    """Renova o token a cada 7 dias para nunca vencer (ele dura 60)."""
    while True:
        try:
            ultimo = db.get("ig_token_renovado", 0)
            if db.agora() - ultimo > 7 * 86400 and (db.get("ig_token") or os.environ.get("IG_ACCESS_TOKEN")):
                await asyncio.to_thread(meta.renovar_token)
                log.info("token do Instagram renovado")
        except Exception as e:  # noqa: BLE001
            log.warning("falha ao renovar token: %s", e)
            avisar("Falha ao renovar o token do Instagram", str(e))
        await asyncio.sleep(6 * 3600)


# ------------------------------------------------------------------ avisos
def avisar(titulo, texto, link=None):
    """Notificação no celular: ntfy (NTFY_TOPIC) e/ou Telegram (TELEGRAM_TOKEN + TELEGRAM_CHAT_ID)."""
    link = link or os.environ.get("PAINEL_URL")
    topico = os.environ.get("NTFY_TOPIC")
    try:
        if topico:
            cab = {"Title": titulo.encode("utf-8").decode("latin-1", "ignore")}
            if link:
                cab["Click"] = link
            httpx.post(f"https://ntfy.sh/{topico}", content=texto.encode(), headers=cab, timeout=10)
        tk, chat = os.environ.get("TELEGRAM_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
        if tk and chat:
            httpx.post(f"https://api.telegram.org/bot{tk}/sendMessage", timeout=10,
                       json={"chat_id": chat, "text": f"{titulo}\n{texto}" + (f"\n{link}" if link else "")})
    except Exception as e:  # noqa: BLE001
        log.warning("aviso falhou: %s", e)


# ------------------------------------------------------------------ webhook
@app.get("/webhook")
def verificar(request: Request):
    p = request.query_params
    if p.get("hub.mode") == "subscribe" and p.get("hub.verify_token") == os.environ.get("VERIFY_TOKEN"):
        return PlainTextResponse(p.get("hub.challenge", ""))
    raise HTTPException(403, "token de verificação inválido")


@app.post("/webhook")
async def receber(request: Request, tarefas: BackgroundTasks):
    corpo = await request.body()
    if not meta.assinatura_ok(corpo, request.headers.get("x-hub-signature-256")):
        log.warning("assinatura inválida")
        raise HTTPException(401, "assinatura inválida")
    tarefas.add_task(processar, json.loads(corpo or b"{}"))
    return {"ok": True}


def processar(payload):
    for entrada in payload.get("entry", []):
        conta = str(entrada.get("id"))
        for ev in entrada.get("messaging", []) or []:
            try:
                tratar_mensagem(conta, ev)
            except Exception as e:  # noqa: BLE001
                log.exception("erro ao tratar mensagem")
                avisar("Erro no atendente de directs", str(e)[:300])
        for mud in entrada.get("changes", []) or []:
            if mud.get("field") == "comments":
                try:
                    tratar_comentario(conta, mud.get("value", {}))
                except Exception as e:  # noqa: BLE001
                    log.exception("erro ao tratar comentário")
                    avisar("Erro no comentou, recebeu", str(e)[:300])


def _texto_da(msg):
    if msg.get("text"):
        return msg["text"]
    tipos = [a.get("type", "anexo") for a in msg.get("attachments", [])]
    return f"[{', '.join(tipos) or 'anexo'}]"


def tratar_mensagem(conta, ev):
    msg = ev.get("message")
    if not msg or msg.get("is_deleted") or msg.get("is_unsupported"):
        return
    remetente = str(ev.get("sender", {}).get("id"))
    destinatario = str(ev.get("recipient", {}).get("id"))

    if msg.get("is_echo") or remetente == conta:
        # Mensagem que saiu da conta. Se fomos nós, o mid já existe e nada acontece.
        # Se o Roque respondeu pelo app, registra e tira o rascunho pendente da fila.
        if db.salvar_mensagem(msg.get("mid"), destinatario, "saida", _texto_da(msg), "app_instagram"):
            for r in db.pendentes():
                if r["igsid"] == destinatario:
                    db.resolver_rascunho(r["id"], "substituido")
        return

    igsid = remetente
    novo = db.contato(igsid) is None
    db.salvar_contato(igsid, entrada=True)
    if novo:
        p = meta.perfil(igsid)
        db.salvar_contato(igsid, username=p.get("username"), nome=p.get("name"))
    texto = _texto_da(msg)
    mid_local = db.salvar_mensagem(msg.get("mid"), igsid, "entrada", texto, "usuario")
    if mid_local is None:
        return  # webhook repetido
    ct = db.contato(igsid)
    quem = ct["username"] or ct["nome"] or igsid

    if ct["humano"]:
        avisar(f"Direct de @{quem}", f"{texto[:200]}\n(conversa com você, a IA não responde)")
        return

    r = ia.regras()
    sug = ia.sugerir(db.historico(igsid), nome=(ct["nome"] or "").split(" ")[0] or None)
    cat = r["categorias"][sug["categoria"]]
    modo = db.get("modo", "rascunho")

    if cat.get("ignorar"):
        db.criar_rascunho(igsid, mid_local, sug["categoria"], "", sug["motivo"], status="ignorado")
        return

    if cat.get("humano") or sug["pede_humano"]:
        db.marcar_humano(igsid)
        db.criar_rascunho(igsid, mid_local, sug["categoria"], sug["resposta"], "Para você: " + sug["motivo"])
        if modo == "automatico" and r.get("aviso_humano"):
            _enviar(igsid, r["aviso_humano"], "ia")
        avisar(f"@{quem} precisa de você ({sug['categoria']})", texto[:200])
        return

    if modo == "automatico" and cat.get("auto") and sug["resposta"]:
        rid = db.criar_rascunho(igsid, mid_local, sug["categoria"], sug["resposta"], sug["motivo"], status="enviando")
        try:
            _enviar(igsid, sug["resposta"], "ia")
            db.resolver_rascunho(rid, "enviado")
        except meta.ErroMeta as e:
            db.resolver_rascunho(rid, "pendente", erro=str(e))
            avisar(f"Não consegui responder @{quem}", str(e)[:200])
        return

    db.criar_rascunho(igsid, mid_local, sug["categoria"], sug["resposta"], sug["motivo"])
    avisar(f"Direct de @{quem} para aprovar", f"{texto[:150]}\nSugestão: {sug['resposta'][:150]}")


def _enviar(igsid, texto, origem, humano=False):
    res = meta.enviar_dm(igsid, texto, humano=humano)
    db.salvar_mensagem(res.get("message_id") or f"local-{secrets.token_hex(6)}", igsid, "saida", texto, origem)
    return res


def _normal(s):
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Z0-9 ]", " ", s.upper())


def tratar_comentario(conta, v):
    cid = v.get("id")
    de = v.get("from", {}) or {}
    if not cid or str(de.get("id")) == conta or db.comentario_existe(cid):
        return
    texto = v.get("text", "")
    midia = (v.get("media") or {}).get("id")
    palavras = _normal(texto).split()
    regra = None
    for p in ia.regras().get("palavras_chave", []):
        if _normal(p["palavra"]).strip() in palavras and (not p.get("posts") or midia in [str(x) for x in p["posts"]]):
            regra = p
            break
    if not regra:
        return  # comentário comum não é guardado
    igsid, user = str(de.get("id")), de.get("username")
    palavra = regra["palavra"].upper()
    if db.ja_recebeu_palavra(igsid, palavra):
        db.salvar_comentario(cid, midia, igsid, user, texto, palavra, "ja_respondido")
        return
    direct = regra["direct"].format(link_mba=ia.regras()["mba"]["link"]).strip()
    try:
        res = meta.resposta_privada(cid, direct)
        db.salvar_contato(igsid, username=user)
        db.salvar_mensagem(res.get("message_id") or f"cmt-{cid}", igsid, "saida", direct, "palavra_chave")
        if regra.get("resposta_publica"):
            try:
                meta.responder_comentario(cid, regra["resposta_publica"])
            except meta.ErroMeta as e:
                log.warning("resposta pública falhou: %s", e)
        db.salvar_comentario(cid, midia, igsid, user, texto, palavra, "enviado")
    except meta.ErroMeta as e:
        db.salvar_comentario(cid, midia, igsid, user, texto, palavra, "erro", str(e))
        avisar("Comentou, recebeu falhou", f"@{user}: {e}"[:300])


# ------------------------------------------------------------------ painel
def autenticar(cred: HTTPBasicCredentials = Depends(basic)):
    senha = os.environ.get("PAINEL_SENHA")
    if not senha:
        raise HTTPException(503, "defina PAINEL_SENHA")
    ok = secrets.compare_digest(cred.username, os.environ.get("PAINEL_USUARIO", "roque")) and \
        secrets.compare_digest(cred.password, senha)
    if not ok:
        raise HTTPException(401, "senha errada", headers={"WWW-Authenticate": "Basic"})
    return True


CSS = """
:root{--bg:#050506;--sf:#141417;--ln:#26262b;--ink:#f5f5f7;--mut:#a1a1a6;--cor:#36d6e7;--alerta:#ff8a3d;--ok:#5ad38a}
@media (prefers-color-scheme: light){:root{--bg:#f6f6f7;--sf:#fff;--ln:#e3e3e6;--ink:#111;--mut:#5d5d63;--cor:#0a8fa0}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.45 -apple-system,system-ui,sans-serif}
main{max-width:720px;margin:0 auto;padding:16px}a{color:var(--cor);text-decoration:none}
header{display:flex;justify-content:space-between;align-items:center;gap:12px;flex-wrap:wrap;margin-bottom:12px}
h1{font-size:20px;margin:0}h2{font-size:15px;color:var(--mut);text-transform:uppercase;letter-spacing:.06em;margin:24px 0 8px}
nav a{margin-right:14px;font-weight:600}.card{background:var(--sf);border:1px solid var(--ln);border-radius:16px;padding:14px;margin-bottom:12px}
.meta{color:var(--mut);font-size:13px}.tag{display:inline-block;border:1px solid var(--ln);border-radius:99px;padding:1px 9px;font-size:12px;margin-right:6px}
.tag.h{border-color:var(--alerta);color:var(--alerta)}textarea{width:100%;min-height:140px;background:var(--bg);color:var(--ink);border:1px solid var(--ln);border-radius:12px;padding:10px;font:inherit}
.acoes{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px}button{font:inherit;font-weight:600;border-radius:10px;border:1px solid var(--ln);background:var(--sf);color:var(--ink);padding:9px 14px;cursor:pointer}
button.p{background:var(--cor);border-color:var(--cor);color:#000}.bal{padding:8px 12px;border-radius:14px;margin:6px 0;max-width:85%;white-space:pre-wrap}
.in{background:var(--sf);border:1px solid var(--ln)}.out{background:color-mix(in srgb,var(--cor) 18%,transparent);margin-left:auto}
.stats{display:grid;grid-template-columns:repeat(4,1fr);gap:8px}.stats div{background:var(--sf);border:1px solid var(--ln);border-radius:12px;padding:10px;text-align:center}
.stats b{display:block;font-size:22px}.erro{color:var(--alerta);font-size:13px}.ultima{color:var(--mut);font-size:14px;white-space:pre-wrap}
@media (max-width:480px){.stats{grid-template-columns:repeat(2,1fr)}}
"""


def _pagina(titulo, corpo, atualizar=False):
    refresh = '<meta http-equiv="refresh" content="60">' if atualizar else ""
    return HTMLResponse(f"""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">{refresh}<title>{titulo}</title>
<style>{CSS}</style></head><body><main>
<header><h1>Directs @roquecneto</h1><nav><a href="/painel">Fila</a><a href="/painel/conversas">Conversas</a>
<a href="/painel/comentarios">Comentários</a><a href="/painel/historico">Histórico</a><a href="/painel/config">Ajustes</a></nav></header>
{corpo}</main></body></html>""")


def _hora(ts):
    return datetime.fromtimestamp(ts or 0, BRT).strftime("%d/%m %H:%M") if ts else ""


def _e(s):
    return html.escape(s or "")


def _janela(ultima):
    if not ultima:
        return "sem mensagem recebida"
    resta = ultima + meta.JANELA - db.agora()
    if resta > 0:
        return f"janela de 24h: {resta // 3600}h{(resta % 3600) // 60:02d} restantes"
    resta = ultima + meta.JANELA_HUMANO - db.agora()
    return f"fora das 24h: só resposta sua ({resta // 86400}d restantes)" if resta > 0 else "janela encerrada"


@app.get("/painel", response_class=HTMLResponse)
def painel(_=Depends(autenticar)):
    n = db.contagens()
    modo = db.get("modo", "rascunho")
    outro = "automatico" if modo == "rascunho" else "rascunho"
    rotulo = "Automático: categorias simples saem sozinhas" if modo == "automatico" else "Rascunho: tudo passa por você"
    nome_outro = "automático" if outro == "automatico" else "rascunho"
    corpo = f"""<div class="stats"><div><b>{n['pendentes']}</b>na fila</div><div><b>{n['recebidas_7d']}</b>recebidas 7d</div>
<div><b>{n['enviadas_7d']}</b>enviadas 7d</div><div><b>{n['palavras_7d']}</b>palavra-chave 7d</div></div>
<div class="card" style="margin-top:12px"><b>Modo:</b> {rotulo}
<form method="post" action="/painel/modo" style="display:inline"><input type="hidden" name="modo" value="{outro}">
<button style="margin-left:8px">Mudar para {nome_outro}</button></form></div><h2>Para aprovar</h2>"""
    fila = db.pendentes()
    if not fila:
        corpo += '<p class="meta">Nada na fila.</p>'
    for r in fila:
        hist = db.historico(r["igsid"], 4)
        conversa = "".join(f'<div class="bal {"in" if m["direcao"] == "entrada" else "out"}">{_e(m["texto"])}</div>' for m in hist)
        tag_h = '<span class="tag h">com você</span>' if r["humano"] else ""
        erro = f'<p class="erro">{_e(r["erro"])}</p>' if r["erro"] else ""
        corpo += f"""<div class="card"><div class="meta"><a href="/painel/conversa/{r['igsid']}">@{_e(r['username'] or r['nome'] or r['igsid'])}</a>
 · <span class="tag">{_e(r['categoria'])}</span>{tag_h} {_hora(r['criado'])} · {_janela(r['ultima_entrada'])}</div>
{conversa}<p class="meta">{_e(r['motivo'])}</p>{erro}
<form method="post" action="/painel/rascunho/{r['id']}/enviar"><textarea name="texto">{_e(r['texto'])}</textarea>
<div class="acoes"><button class="p">Enviar</button>
<button formaction="/painel/rascunho/{r['id']}/descartar">Descartar</button></div></form></div>"""
    return _pagina("Fila", corpo, atualizar=True)


@app.post("/painel/modo")
def mudar_modo(modo: str = Form(...), _=Depends(autenticar)):
    db.put("modo", "automatico" if modo == "automatico" else "rascunho")
    return RedirectResponse("/painel", 303)


@app.post("/painel/rascunho/{rid}/enviar")
def enviar_rascunho(rid: int, texto: str = Form(...), _=Depends(autenticar)):
    r = db.rascunho(rid)
    if not r or r["status"] != "pendente":
        return RedirectResponse("/painel", 303)
    try:
        _enviar(r["igsid"], texto.strip(), "roque", humano=True)
        db.resolver_rascunho(rid, "enviado", texto=texto.strip())
    except meta.ErroMeta as e:
        db.resolver_rascunho(rid, "pendente", texto=texto.strip(), erro=str(e))
    return RedirectResponse("/painel", 303)


@app.post("/painel/rascunho/{rid}/descartar")
def descartar(rid: int, _=Depends(autenticar)):
    db.resolver_rascunho(rid, "descartado")
    return RedirectResponse("/painel", 303)


@app.get("/painel/conversas", response_class=HTMLResponse)
def lista_conversas(_=Depends(autenticar)):
    corpo = "<h2>Conversas</h2>"
    for c in db.conversas():
        tag = '<span class="tag h">com você</span>' if c["humano"] else ""
        pend = f'<span class="tag">{c["pendentes"]} na fila</span>' if c["pendentes"] else ""
        seta = "Você: " if c["ultima_direcao"] == "saida" else ""
        corpo += f"""<a href="/painel/conversa/{c['igsid']}"><div class="card"><b>@{_e(c['username'] or c['nome'] or c['igsid'])}</b> {tag}{pend}
<span class="meta"> {_hora(c['ultimo_em'])}</span><div class="ultima">{seta}{_e((c['ultimo_texto'] or '')[:140])}</div></div></a>"""
    return _pagina("Conversas", corpo)


@app.get("/painel/conversa/{igsid}", response_class=HTMLResponse)
def conversa(igsid: str, _=Depends(autenticar)):
    ct = db.contato(igsid)
    if not ct:
        raise HTTPException(404)
    hist = db.historico(igsid, 60)
    bal = "".join(f'<div class="bal {"in" if m["direcao"] == "entrada" else "out"}">{_e(m["texto"])}'
                  f'<div class="meta">{_hora(m["criado"])} · {m["origem"]}</div></div>' for m in hist)
    alterna = ("Devolver para a IA", 0) if ct["humano"] else ("Assumir (a IA para de sugerir)", 1)
    corpo = f"""<h2>@{_e(ct['username'] or ct['nome'] or igsid)}</h2><p class="meta">{_janela(ct['ultima_entrada'])}</p>{bal}
<form method="post" action="/painel/conversa/{igsid}/enviar" class="card"><textarea name="texto" placeholder="Escreva a resposta"></textarea>
<div class="acoes"><button class="p">Enviar</button></div></form>
<form method="post" action="/painel/conversa/{igsid}/humano"><input type="hidden" name="valor" value="{alterna[1]}"><button>{alterna[0]}</button></form>"""
    return _pagina("Conversa", corpo)


@app.post("/painel/conversa/{igsid}/enviar")
def enviar_livre(igsid: str, texto: str = Form(...), _=Depends(autenticar)):
    if texto.strip():
        try:
            _enviar(igsid, texto.strip(), "roque", humano=True)
            for r in db.pendentes():
                if r["igsid"] == igsid:
                    db.resolver_rascunho(r["id"], "substituido")
        except meta.ErroMeta as e:
            return _pagina("Erro", f'<p class="erro">{_e(str(e))}</p><a href="/painel/conversa/{igsid}">Voltar</a>')
    return RedirectResponse(f"/painel/conversa/{igsid}", 303)


@app.post("/painel/conversa/{igsid}/humano")
def alternar_humano(igsid: str, valor: int = Form(...), _=Depends(autenticar)):
    db.marcar_humano(igsid, 1 if valor else 0)
    return RedirectResponse(f"/painel/conversa/{igsid}", 303)


@app.get("/painel/comentarios", response_class=HTMLResponse)
def comentarios(_=Depends(autenticar)):
    pal = ", ".join(p["palavra"] for p in ia.regras().get("palavras_chave", []))
    corpo = f'<h2>Comentou, recebeu</h2><p class="meta">Palavras ativas: {_e(pal)}. Edite em directs/regras.yaml.</p>'
    for c in db.ultimos_comentarios():
        erro = f'<div class="erro">{_e(c["erro"])}</div>' if c["erro"] else ""
        corpo += f"""<div class="card"><b>@{_e(c['username'])}</b> <span class="tag">{_e(c['palavra'])}</span>
<span class="tag">{_e(c['status'])}</span><span class="meta">{_hora(c['criado'])}</span><div class="ultima">{_e(c['texto'])}</div>{erro}</div>"""
    return _pagina("Comentários", corpo)


@app.get("/painel/historico", response_class=HTMLResponse)
def historico(_=Depends(autenticar)):
    corpo = "<h2>Respostas decididas</h2>"
    for r in db.ultimos_rascunhos():
        corpo += f"""<div class="card"><span class="meta">@{_e(r['username'] or r['igsid'])} · {_hora(r['resolvido'])}</span>
<span class="tag">{_e(r['categoria'])}</span><span class="tag">{_e(r['status'])}</span><div class="ultima">{_e(r['texto'])}</div></div>"""
    return _pagina("Histórico", corpo)


@app.get("/saude")
def saude():
    return {"ok": True, "modo": db.get("modo"), "token_renovado": db.get("ig_token_renovado")}


@app.get("/painel/config", response_class=HTMLResponse)
def config(_=Depends(autenticar)):
    def tem(v):
        return "ok" if os.environ.get(v) else "faltando"
    itens = ["IG_ACCESS_TOKEN", "IG_USER_ID", "APP_SECRET", "VERIFY_TOKEN", "ANTHROPIC_API_KEY", "PAINEL_URL", "NTFY_TOPIC"]
    lista = "".join(f"<div>{v}: <b>{tem(v)}</b></div>" for v in itens)
    renov = _hora(db.get("ig_token_renovado")) or "ainda não"
    corpo = f"""<h2>Ajustes</h2><div class="card">{lista}<p class="meta">Token renovado pela última vez: {renov}</p></div>
<div class="card"><b>Ligar os avisos da Meta</b><p class="meta">Rode uma vez, depois de configurar o webhook no painel da Meta.</p>
<form method="post" action="/painel/config/assinar"><button class="p">Assinar mensagens e comentários</button></form></div>
<div class="card"><b>Testar aviso no celular</b><form method="post" action="/painel/config/aviso"><button>Mandar aviso de teste</button></form></div>"""
    return _pagina("Ajustes", corpo)


@app.post("/painel/config/assinar", response_class=HTMLResponse)
def assinar(_=Depends(autenticar)):
    """Liga os webhooks de mensagens e comentários para a conta."""
    try:
        res = meta.assinar_webhooks()
        txt = f"Resposta da Meta: {_e(json.dumps(res))}"
    except meta.ErroMeta as e:
        txt = f'<span class="erro">{_e(str(e))}</span>'
    return _pagina("Ajustes", f'<div class="card">{txt}</div><a href="/painel/config">Voltar</a>')


@app.post("/painel/config/aviso")
def aviso_teste(_=Depends(autenticar)):
    avisar("Teste do atendente de directs", "Se chegou no celular, os avisos estão funcionando.")
    return RedirectResponse("/painel/config", 303)
