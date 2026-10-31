"""Banco SQLite do atendente. Um arquivo só, no volume do Railway (DB_PATH)."""

import json
import os
import sqlite3
import time
from contextlib import contextmanager

CAMINHO = os.environ.get("DB_PATH", "directs.db")

ESQUEMA = """
create table if not exists contatos (
  igsid text primary key,
  username text,
  nome text,
  ultima_entrada integer,          -- epoch da última mensagem recebida (janela de 24h)
  humano integer default 0,        -- 1 = o Roque assumiu, a IA não mexe
  criado integer
);
create table if not exists mensagens (
  id integer primary key autoincrement,
  mid text unique,                 -- id da Meta, evita processar duas vezes
  igsid text,
  direcao text,                    -- entrada | saida
  texto text,
  origem text,                     -- usuario | ia | roque | palavra_chave | app_instagram
  criado integer
);
create table if not exists rascunhos (
  id integer primary key autoincrement,
  igsid text,
  mensagem_id integer,
  categoria text,
  texto text,
  motivo text,
  status text default 'pendente',  -- pendente | enviado | descartado | erro | expirado
  erro text,
  criado integer,
  resolvido integer
);
create table if not exists comentarios (
  id text primary key,             -- comment id
  midia text,
  igsid text,
  username text,
  texto text,
  palavra text,
  status text,                     -- ignorado | enviado | erro | ja_respondido
  erro text,
  criado integer
);
create table if not exists config (chave text primary key, valor text);
"""


@contextmanager
def conexao():
    c = sqlite3.connect(CAMINHO, timeout=30)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    finally:
        c.close()


def iniciar():
    pasta = os.path.dirname(CAMINHO)
    if pasta:
        os.makedirs(pasta, exist_ok=True)
    with conexao() as c:
        c.executescript(ESQUEMA)


def agora():
    return int(time.time())


# ---------- config ----------
def get(chave, padrao=None):
    with conexao() as c:
        r = c.execute("select valor from config where chave=?", (chave,)).fetchone()
    return json.loads(r["valor"]) if r else padrao


def put(chave, valor):
    with conexao() as c:
        c.execute("insert into config values(?,?) on conflict(chave) do update set valor=excluded.valor",
                  (chave, json.dumps(valor)))


# ---------- contatos ----------
def contato(igsid):
    with conexao() as c:
        return c.execute("select * from contatos where igsid=?", (igsid,)).fetchone()


def salvar_contato(igsid, username=None, nome=None, entrada=False):
    with conexao() as c:
        c.execute("insert or ignore into contatos(igsid, criado) values(?,?)", (igsid, agora()))
        if username:
            c.execute("update contatos set username=? where igsid=?", (username, igsid))
        if nome:
            c.execute("update contatos set nome=? where igsid=?", (nome, igsid))
        if entrada:
            c.execute("update contatos set ultima_entrada=? where igsid=?", (agora(), igsid))


def marcar_humano(igsid, valor=1):
    with conexao() as c:
        c.execute("update contatos set humano=? where igsid=?", (valor, igsid))


# ---------- mensagens ----------
def salvar_mensagem(mid, igsid, direcao, texto, origem):
    """Devolve o id novo, ou None se a mensagem já existia (webhook repetido)."""
    with conexao() as c:
        try:
            cur = c.execute("insert into mensagens(mid, igsid, direcao, texto, origem, criado) values(?,?,?,?,?,?)",
                            (mid, igsid, direcao, texto, origem, agora()))
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return None


def historico(igsid, limite=12):
    with conexao() as c:
        rows = c.execute("select * from mensagens where igsid=? order by id desc limit ?", (igsid, limite)).fetchall()
    return list(reversed(rows))


def conversas(limite=50):
    with conexao() as c:
        return c.execute("""
          select ct.*, m.texto as ultimo_texto, m.direcao as ultima_direcao, m.criado as ultimo_em,
                 (select count(*) from rascunhos r where r.igsid=ct.igsid and r.status='pendente') as pendentes
          from contatos ct
          join mensagens m on m.id = (select max(id) from mensagens where igsid=ct.igsid)
          order by m.id desc limit ?""", (limite,)).fetchall()


# ---------- rascunhos ----------
def criar_rascunho(igsid, mensagem_id, categoria, texto, motivo, status="pendente"):
    with conexao() as c:
        # um pendente por conversa: o novo substitui o antigo
        if status in ("pendente", "enviando"):
            c.execute("update rascunhos set status='substituido', resolvido=? where igsid=? and status='pendente'",
                      (agora(), igsid))
        cur = c.execute("""insert into rascunhos(igsid, mensagem_id, categoria, texto, motivo, status, criado)
                           values(?,?,?,?,?,?,?)""", (igsid, mensagem_id, categoria, texto, motivo, status, agora()))
        return cur.lastrowid


def rascunho(rid):
    with conexao() as c:
        return c.execute("select * from rascunhos where id=?", (rid,)).fetchone()


def pendentes():
    with conexao() as c:
        return c.execute("""select r.*, ct.username, ct.nome, ct.ultima_entrada, ct.humano
                            from rascunhos r left join contatos ct on ct.igsid=r.igsid
                            where r.status='pendente' order by r.id""").fetchall()


def resolver_rascunho(rid, status, texto=None, erro=None):
    with conexao() as c:
        if texto is not None:
            c.execute("update rascunhos set texto=? where id=?", (texto, rid))
        c.execute("update rascunhos set status=?, erro=?, resolvido=? where id=?", (status, erro, agora(), rid))


def ultimos_rascunhos(limite=40):
    with conexao() as c:
        return c.execute("""select r.*, ct.username from rascunhos r left join contatos ct on ct.igsid=r.igsid
                            where r.status!='pendente' order by r.resolvido desc limit ?""", (limite,)).fetchall()


# ---------- comentários ----------
def comentario_existe(cid):
    with conexao() as c:
        return c.execute("select 1 from comentarios where id=?", (cid,)).fetchone() is not None


def salvar_comentario(cid, midia, igsid, username, texto, palavra, status, erro=None):
    with conexao() as c:
        c.execute("""insert or replace into comentarios values(?,?,?,?,?,?,?,?,?)""",
                  (cid, midia, igsid, username, texto, palavra, status, erro, agora()))


def ja_recebeu_palavra(igsid, palavra):
    with conexao() as c:
        return c.execute("select 1 from comentarios where igsid=? and palavra=? and status='enviado'",
                         (igsid, palavra)).fetchone() is not None


def ultimos_comentarios(limite=40):
    with conexao() as c:
        return c.execute("select * from comentarios where palavra is not null order by criado desc limit ?",
                         (limite,)).fetchall()


def contagens():
    with conexao() as c:
        def n(sql):
            return c.execute(sql).fetchone()[0]
        return {
            "pendentes": n("select count(*) from rascunhos where status='pendente'"),
            "enviadas_7d": n(f"select count(*) from mensagens where direcao='saida' and criado>{agora()-7*86400}"),
            "recebidas_7d": n(f"select count(*) from mensagens where direcao='entrada' and criado>{agora()-7*86400}"),
            "palavras_7d": n(f"select count(*) from comentarios where status='enviado' and criado>{agora()-7*86400}"),
        }
