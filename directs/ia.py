"""Classifica a mensagem e escreve a resposta sugerida, com as regras de regras.yaml."""

import json
import os
import re
from pathlib import Path

import yaml

REGRAS_ARQ = Path(__file__).with_name("regras.yaml")
MODELO = os.environ.get("MODELO_IA", "claude-sonnet-5-5")


def regras():
    return yaml.safe_load(REGRAS_ARQ.read_text(encoding="utf-8"))


def _sistema(r):
    cats = "\n".join(f"- {k}: {v['descricao']}" for k, v in r["categorias"].items())
    nunca = "\n".join(f"- {x}" for x in r["nunca"])
    return f"""Você escreve respostas de direct do Instagram em nome do perfil @roquecneto.
O Roque revisa antes de sair, a não ser em categorias simples.

Quem é o Roque:
{r['quem_sou']}

MBA que ele indica: {r['mba']['nome']}. Link: {r['mba']['link']}

Estilo:
{r['estilo']}

Nunca:
{nunca}

Categorias:
{cats}

Responda SOMENTE com um JSON, sem texto antes ou depois:
{{"categoria": "<uma das categorias>", "resposta": "<texto do direct, vazio se for spam>",
  "motivo": "<uma frase curta explicando a classificação, para o Roque>",
  "pede_humano": <true se a pessoa pediu para falar com o Roque ou se você não tem segurança para responder>}}"""


def _conversa(historico):
    linhas = []
    for m in historico:
        quem = "Pessoa" if m["direcao"] == "entrada" else "Perfil"
        linhas.append(f"{quem}: {m['texto']}")
    return "\n".join(linhas)


def _limpar(texto):
    texto = texto.replace("—", ",").replace("–", "-")  # nunca travessão longo
    return re.sub(r"\s+,", ",", texto).strip()


def sugerir(historico, nome=None, cliente=None):
    """Devolve dict com categoria, resposta, motivo, pede_humano."""
    r = regras()
    if cliente is None:
        import anthropic
        cliente = anthropic.Anthropic()
    contexto = f"Nome da pessoa: {nome}\n" if nome else ""
    msg = cliente.messages.create(
        model=MODELO, max_tokens=600, system=_sistema(r),
        messages=[{"role": "user", "content": f"{contexto}Conversa até agora (a última é a que precisa de resposta):\n{_conversa(historico)}"}],
    )
    bruto = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    m = re.search(r"\{.*\}", bruto, re.S)
    try:
        dados = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        dados = {}
    cat = dados.get("categoria") if dados.get("categoria") in r["categorias"] else "outro"
    return {
        "categoria": cat,
        "resposta": _limpar(dados.get("resposta") or ""),
        "motivo": dados.get("motivo") or ("não consegui ler a resposta da IA" if not dados else ""),
        "pede_humano": bool(dados.get("pede_humano")),
    }
