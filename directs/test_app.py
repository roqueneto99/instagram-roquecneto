"""Testes com eventos simulados: nada chama a Meta nem a IA de verdade."""

import hashlib
import hmac
import json
import os
import tempfile

os.environ["DB_PATH"] = os.path.join(tempfile.mkdtemp(), "t.db")
os.environ.update(VERIFY_TOKEN="vt", APP_SECRET="seg", PAINEL_SENHA="s", IG_ACCESS_TOKEN="x", IG_USER_ID="999")

import pytest
from fastapi.testclient import TestClient

import app as A
import db
import ia
import meta

ENVIADOS = []


@pytest.fixture(autouse=True)
def falsos(monkeypatch):
    ENVIADOS.clear()

    def req(metodo, caminho, **kw):
        ENVIADOS.append((metodo, caminho, kw))
        if caminho.endswith("/messages"):
            return {"recipient_id": "1", "message_id": f"m{len(ENVIADOS)}"}
        if caminho.endswith("/replies"):
            return {"id": "r1"}
        return {"username": "joao.silva", "name": "João Silva"}

    monkeypatch.setattr(meta, "_req", req)
    monkeypatch.setattr(A, "avisar", lambda *a, **k: None)
    yield


def sugestao(cat, resp="Oi João! Segue o link.", humano=False):
    return lambda hist, nome=None, cliente=None: {"categoria": cat, "resposta": resp, "motivo": "teste", "pede_humano": humano}


def assinar(corpo):
    return "sha256=" + hmac.new(b"seg", corpo, hashlib.sha256).hexdigest()


def dm(cli, mid, texto, sender="111"):
    corpo = json.dumps({"object": "instagram", "entry": [{"id": "999", "time": 1, "messaging": [
        {"sender": {"id": sender}, "recipient": {"id": "999"}, "timestamp": 1, "message": {"mid": mid, "text": texto}}]}]}).encode()
    return cli.post("/webhook", content=corpo, headers={"x-hub-signature-256": assinar(corpo)})


def comentario(cli, cid, texto, de="222"):
    corpo = json.dumps({"object": "instagram", "entry": [{"id": "999", "time": 1, "changes": [{"field": "comments", "value": {
        "id": cid, "from": {"id": de, "username": "maria"}, "text": texto, "media": {"id": "555"}}}]}]}).encode()
    return cli.post("/webhook", content=corpo, headers={"x-hub-signature-256": assinar(corpo)})


@pytest.fixture
def cli():
    with TestClient(A.app) as c:
        db.put("modo", "rascunho")
        yield c


AUTH = ("roque", "s")


def test_verificacao(cli):
    assert cli.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "vt", "hub.challenge": "42"}).text == "42"
    assert cli.get("/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "errado", "hub.challenge": "42"}).status_code == 403


def test_assinatura_invalida(cli):
    r = cli.post("/webhook", content=b"{}", headers={"x-hub-signature-256": "sha256=000"})
    assert r.status_code == 401


def test_dm_vira_rascunho_no_modo_rascunho(cli, monkeypatch):
    monkeypatch.setattr(ia, "sugerir", sugestao("mba"))
    assert dm(cli, "a1", "quanto custa o MBA?").status_code == 200
    fila = db.pendentes()
    assert len(fila) == 1 and fila[0]["categoria"] == "mba"
    assert not [e for e in ENVIADOS if e[1].endswith("/messages")]
    # webhook repetido não duplica
    dm(cli, "a1", "quanto custa o MBA?")
    assert len(db.pendentes()) == 1


def test_aprovar_no_painel_envia(cli, monkeypatch):
    monkeypatch.setattr(ia, "sugerir", sugestao("duvida_ia"))
    dm(cli, "b1", "qual IA você usa?", sender="333")
    rid = [r for r in db.pendentes() if r["igsid"] == "333"][0]["id"]
    assert "qual IA você usa?" in cli.get("/painel", auth=AUTH).text
    r = cli.post(f"/painel/rascunho/{rid}/enviar", data={"texto": "Uso o Claude no dia a dia."}, auth=AUTH, follow_redirects=False)
    assert r.status_code == 303
    assert db.rascunho(rid)["status"] == "enviado"
    env = [e for e in ENVIADOS if e[1].endswith("/messages")][-1]
    assert env[2]["json"]["recipient"]["id"] == "333" and "Claude" in env[2]["json"]["message"]["text"]


def test_automatico_so_categoria_simples(cli, monkeypatch):
    db.put("modo", "automatico")
    monkeypatch.setattr(ia, "sugerir", sugestao("mba", "Oi! O link é este."))
    dm(cli, "c1", "me passa o link do MBA", sender="444")
    assert [e for e in ENVIADOS if e[1].endswith("/messages") and e[2]["json"]["recipient"]["id"] == "444"]
    monkeypatch.setattr(ia, "sugerir", sugestao("duvida_ia"))
    ENVIADOS.clear()
    dm(cli, "c2", "e qual ferramenta pra planilha?", sender="444")
    assert not [e for e in ENVIADOS if e[1].endswith("/messages")]
    assert [r for r in db.pendentes() if r["igsid"] == "444"]


def test_comercial_vai_para_humano(cli, monkeypatch):
    db.put("modo", "automatico")
    monkeypatch.setattr(ia, "sugerir", sugestao("comercial", "Vou ver com ele."))
    dm(cli, "d1", "quero te contratar para uma palestra", sender="555")
    assert db.contato("555")["humano"] == 1
    textos = [e[2]["json"]["message"]["text"] for e in ENVIADOS if e[1].endswith("/messages")]
    assert textos == [ia.regras()["aviso_humano"]]  # só o aviso, nunca a sugestão
    # próxima mensagem não passa pela IA
    monkeypatch.setattr(ia, "sugerir", lambda *a, **k: (_ for _ in ()).throw(AssertionError("não devia chamar a IA")))
    dm(cli, "d2", "pode ser semana que vem?", sender="555")


def test_eco_do_app_tira_rascunho(cli, monkeypatch):
    monkeypatch.setattr(ia, "sugerir", sugestao("outro"))
    dm(cli, "e1", "oi Roque", sender="666")
    assert [r for r in db.pendentes() if r["igsid"] == "666"]
    corpo = json.dumps({"object": "instagram", "entry": [{"id": "999", "messaging": [
        {"sender": {"id": "999"}, "recipient": {"id": "666"}, "message": {"mid": "e2", "text": "oi!", "is_echo": True}}]}]}).encode()
    cli.post("/webhook", content=corpo, headers={"x-hub-signature-256": assinar(corpo)})
    assert not [r for r in db.pendentes() if r["igsid"] == "666"]


def test_comentou_recebeu(cli):
    comentario(cli, "k1", "Quero saber do mba!")
    privados = [e for e in ENVIADOS if e[1].endswith("/messages")]
    assert privados[0][2]["json"]["recipient"] == {"comment_id": "k1"}
    assert "bsspce.com.br" in privados[0][2]["json"]["message"]["text"]
    assert [e for e in ENVIADOS if e[1] == "k1/replies"]
    ENVIADOS.clear()
    comentario(cli, "k2", "MBA")  # mesma pessoa, mesma palavra: não manda de novo
    comentario(cli, "k3", "que legal o post")  # sem palavra: nada
    assert not ENVIADOS
    assert "maria" in cli.get("/painel/comentarios", auth=AUTH).text


def test_janela_24h(cli, monkeypatch):
    monkeypatch.setattr(ia, "sugerir", sugestao("outro"))
    dm(cli, "f1", "oi", sender="777")
    with db.conexao() as c:
        c.execute("update contatos set ultima_entrada=? where igsid='777'", (db.agora() - 30 * 3600,))
    with pytest.raises(meta.ErroMeta):
        meta.enviar_dm("777", "x", humano=False)
    meta.enviar_dm("777", "x", humano=True)
    assert ENVIADOS[-1][2]["json"]["tag"] == "HUMAN_AGENT"


def test_painel_pede_senha(cli):
    assert cli.get("/painel").status_code == 401
    assert cli.get("/painel", auth=("roque", "errada")).status_code == 401


def test_ia_le_json_e_tira_travessao():
    class Bloco:
        type = "text"
        text = 'Claro: {"categoria":"mba","resposta":"Oi — segue o link","motivo":"pediu link","pede_humano":false}'

    class Cli:
        class messages:
            @staticmethod
            def create(**kw):
                assert "MBA" in kw["system"] and "Nunca" in kw["system"]
                return type("R", (), {"content": [Bloco()]})

    s = ia.sugerir([{"direcao": "entrada", "texto": "link do mba?"}], cliente=Cli())
    assert s["categoria"] == "mba" and "—" not in s["resposta"]
