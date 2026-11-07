"""Ajuste de 04/11/2026 pedido pelo Roque: conjuntos de seguidores só no Instagram (feed, reels,
explorar) e teste A/B de engajamento com metade do orçamento do Profissionais formados.

Idempotente: rodar de novo não duplica nada (procura pelo nome antes de criar).
"""
import json
import sys

sys.path.insert(0, "scripts")
import anunciar as A  # noqa: E402

CONTA = A.CONFIG["conta"]
SEGUIDORES = {
    "profissionais": "120252753265490706",
    "engajados": "120252625057380706",
    "polos": "120252624993030706",
}
POSICOES = {"publisher_platforms": ["instagram"],
            "instagram_positions": ["stream", "reels", "explore_home"]}
NOME_CAMP = "RN · Seguidores · Engajamento (teste A/B)"
NOME_CONJ = "Profissionais formados · BR · 25-50 · engajamento"
MEDIA_APURACAO = "18082101758401845"


def so_instagram(adset_id):
    t = A._api("GET", adset_id, fields="name,targeting")
    alvo = t["targeting"]
    for chave in ("facebook_positions", "messenger_positions", "audience_network_positions",
                  "whatsapp_positions", "threads_positions", "device_platforms",
                  "targeting_optimization"):
        alvo.pop(chave, None)
    alvo.update(POSICOES)
    A._api("POST", adset_id, targeting=alvo)
    print(f"posicionamento só Instagram (feed, reels, explorar): {t['name']}")
    return alvo


def main():
    alvos = {k: so_instagram(v) for k, v in SEGUIDORES.items()}

    prof = SEGUIDORES["profissionais"]
    A._api("POST", prof, daily_budget=600)
    print("Profissionais formados: orçamento R$6/dia")

    camps = A._lista(f"{CONTA}/campaigns", fields="id,name")
    camp = next((c["id"] for c in camps if c["name"] == NOME_CAMP), None)
    if not camp:
        camp = A._api("POST", f"{CONTA}/campaigns", name=NOME_CAMP, objective="OUTCOME_ENGAGEMENT",
                      status="ACTIVE", special_ad_categories=[],
                      is_adset_budget_sharing_enabled=False)["id"]
        print(f"campanha criada: {camp}")

    conjs = A._lista(f"{camp}/adsets", fields="id,name")
    conj = next((c["id"] for c in conjs if c["name"] == NOME_CONJ), None)
    if not conj:
        conj = A._api("POST", f"{CONTA}/adsets", name=NOME_CONJ, campaign_id=camp,
                      daily_budget=600, billing_event="IMPRESSIONS",
                      optimization_goal="POST_ENGAGEMENT", destination_type="ON_POST",
                      bid_strategy="LOWEST_COST_WITHOUT_CAP", targeting=alvos["profissionais"],
                      status="PAUSED")["id"]
        print(f"conjunto criado: {conj}")

    ads = A._lista(f"{conj}/ads", fields="id,name,effective_status")
    if not ads:
        cr = A._api("POST", f"{CONTA}/adcreatives", name="auto · 2026-11-04-apuracao-5-atividades · eng",
                    object_id="112825373722677", instagram_user_id="17841400496533075",
                    source_instagram_media_id=MEDIA_APURACAO)["id"]
        ad = A._api("POST", f"{CONTA}/ads", name="auto · 2026-11-04-apuracao-5-atividades",
                    adset_id=conj, creative={"creative_id": cr}, status="ACTIVE")["id"]
        print(f"anúncio da Apuração criado: {ad}")
    A._api("POST", conj, status="ACTIVE")
    print(f"conjunto de engajamento ativo: {conj}")
    print("CONJ_ENG", conj)


IG = {"publisher_platforms": ["instagram"], "instagram_positions": ["stream", "reels", "explore_home"],
      "geo_locations": {"countries": ["BR"], "location_types": ["home", "recent"]},
      "age_min": 25, "age_max": 55,
      "targeting_automation": {"advantage_audience": 0}}
PROFISSOES = {
    "prof_contador": ("Raio-X · contadores", {
        "interests": ["6003138589139", "6003389795312"],
        "work_positions": ["110927205602254", "339651256100614", "114306391919613", "133532123326775",
                           "113171825383590", "111518682231513"]}),
    "prof_advogado": ("Raio-X · advogados", {
        "interests": ["6003392101554", "6003283840779", "6002867987022"],
        "work_positions": ["127978847249423", "107762792579901"]}),
    "prof_rh": ("Raio-X · RH", {
        "interests": ["6003069499982"],
        "work_positions": ["109288552422516", "126583970748257", "129270633781678", "102010339879775"]}),
    "prof_gestao": ("Raio-X · gestores", {
        "interests": ["6003230008188"],
        "work_positions": ["137453372957907", "134779459890064", "143530962334045", "110463695647944"]}),
}


def alvo_prof(spec):
    t = dict(IG)
    t["flexible_spec"] = [{k: [{"id": i} for i in v] for k, v in spec.items()}]
    return t


def profissoes(media_contador):
    camps = A._lista(f"{CONTA}/campaigns", fields="id,name")
    camp = next(c["id"] for c in camps if c["name"] == NOME_CAMP)
    existentes = {c["name"]: c["id"] for c in A._lista(f"{camp}/adsets", fields="id,name")}
    ids = {}
    for apelido, (nome, spec) in PROFISSOES.items():
        if nome in existentes:
            ids[apelido] = existentes[nome]
            continue
        alvo = alvo_prof(spec)
        try:
            ids[apelido] = A._api("POST", f"{CONTA}/adsets", name=nome, campaign_id=camp, daily_budget=600,
                                  billing_event="IMPRESSIONS", optimization_goal="POST_ENGAGEMENT",
                                  destination_type="ON_POST", bid_strategy="LOWEST_COST_WITHOUT_CAP",
                                  targeting=alvo, status="PAUSED")["id"]
        except A.ErroAnuncio as e:
            print(f"  {nome}: cargo recusado ({e}); tentando só com interesses")
            spec = {"interests": spec["interests"]}
            ids[apelido] = A._api("POST", f"{CONTA}/adsets", name=nome, campaign_id=camp, daily_budget=600,
                                  billing_event="IMPRESSIONS", optimization_goal="POST_ENGAGEMENT",
                                  destination_type="ON_POST", bid_strategy="LOWEST_COST_WITHOUT_CAP",
                                  targeting=alvo_prof(spec), status="PAUSED")["id"]
        print(f"conjunto criado (pausado): {nome} {ids[apelido]}")
    for apelido, i in ids.items():
        est = A._api("GET", f"{i}/delivery_estimate", optimization_goal="POST_ENGAGEMENT").get("data", [{}])[0]
        print(f"PROF {apelido} {i} público estimado: {est.get('estimate_mau_lower_bound')} a "
              f"{est.get('estimate_mau_upper_bound')}")
    # contador já publicado: cria o anúncio agora e liga
    c = ids["prof_contador"]
    if not A._lista(f"{c}/ads", fields="id"):
        cr = A._api("POST", f"{CONTA}/adcreatives", name="auto · 2026-11-05-raiox-contador · prof",
                    object_id="112825373722677", instagram_user_id="17841400496533075",
                    source_instagram_media_id=media_contador)["id"]
        ad = A._api("POST", f"{CONTA}/ads", name="auto · 2026-11-05-raiox-contador", adset_id=c,
                    creative={"creative_id": cr}, status="ACTIVE")["id"]
        print(f"anúncio do Raio-X contador criado: {ad}")
    A._api("POST", c, status="ACTIVE")
    A._api("POST", SEGUIDORES["polos"], status="PAUSED")
    print("Raio-X · contadores ligado; Polos corporativos pausado (orçamento passa para cá)")
    print("IDS", json.dumps(ids))


CARGOS = {
    "120252786356050706": ["110927205602254", "339651256100614", "114306391919613", "133532123326775",
                           "137885909578558", "113171825383590", "111518682231513"],
    "120252786356350706": ["127978847249423", "149331845136451", "141538732533559"],
    "120252786356800706": ["109288552422516", "126583970748257", "129270633781678", "138800332806611"],
    "120252786357290706": ["137453372957907", "134779459890064", "143530962334045", "151145811576881",
                           "197683560270688"],
}


def cargos():
    """Pedido do Roque em 05/11: conjuntos por profissão só com cargo declarado."""
    for adset, ids in CARGOS.items():
        t = dict(IG)
        t["work_positions"] = [{"id": i} for i in ids]
        A._api("POST", adset, targeting=t)
        nome = A._api("GET", adset, fields="name")["name"]
        est = A._api("GET", f"{adset}/delivery_estimate", optimization_goal="POST_ENGAGEMENT").get("data", [{}])[0]
        print(f"CARGO {nome}: público estimado {est.get('estimate_mau_lower_bound')} a "
              f"{est.get('estimate_mau_upper_bound')}")


def orcamento(adset, centavos):
    A._api("POST", adset, daily_budget=int(centavos))
    d = A._api("GET", adset, fields="name,daily_budget,effective_status")
    print(f"ORCAMENTO {d['name']}: R${int(d['daily_budget']) / 100:.2f}/dia ({d['effective_status']})")


def problemas(*ids):
    for i in ids:
        d = A._api("GET", i, fields="name,effective_status,configured_status,issues_info,ad_review_feedback,"
                   "recommendations")
        print("DIAG", json.dumps(d, ensure_ascii=False)[:1500])
    c = "120252786356050706"
    d = A._api("GET", c, fields="name,effective_status,issues_info,learning_stage_info,targeting")
    print("CONJ", json.dumps(d, ensure_ascii=False)[:1500])
    est = A._api("GET", f"{c}/delivery_estimate", optimization_goal="POST_ENGAGEMENT")
    print("EST", json.dumps(est, ensure_ascii=False)[:800])


def copiar(origem, destino, quebrado, nome):
    """Recria um anúncio bloqueado usando o criativo de um anúncio que está rodando."""
    cr = A._api("GET", origem, fields="creative{id}")["creative"]["id"]
    ad = A._api("POST", f"{CONTA}/ads", name=nome, adset_id=destino, creative={"creative_id": cr},
                status="ACTIVE")["id"]
    A._api("POST", quebrado, status="DELETED")
    d = A._api("GET", ad, fields="name,effective_status")
    print(f"COPIA {nome}: novo {ad} ({d['effective_status']}), bloqueado {quebrado} apagado")


INTERESSES_EXTRA = {
    "120252786356050706": {"interests": ["6003389795312"]},                       # contabilidade financeira
    "120252786356350706": {"interests": ["6003283840779", "6003392101554"]},      # direito tributário, advogado
    "120252786356800706": {"interests": ["6003069499982"],                        # gestão de RH
                           "education_majors": ["109288552422516"]},
}


def cargos_mais_interesse():
    """Pedido de 06/11: cargo declarado OU um interesse bem específico da profissão (o só-cargo não entregou)."""
    for adset, extra in INTERESSES_EXTRA.items():
        bloco = {"work_positions": [{"id": i} for i in CARGOS[adset]]}
        for k, v in extra.items():
            bloco[k] = [{"id": i} for i in v]
        t = dict(IG)
        t["flexible_spec"] = [bloco]
        A._api("POST", adset, targeting=t)
        nome = A._api("GET", adset, fields="name")["name"]
        est = A._api("GET", f"{adset}/delivery_estimate", optimization_goal="POST_ENGAGEMENT").get("data", [{}])[0]
        print(f"CARGO+ {nome}: público estimado {est.get('estimate_mau_lower_bound')} a "
              f"{est.get('estimate_mau_upper_bound')}")


if __name__ == "__main__":
    if sys.argv[1:2] == ["cargos2"]:
        cargos_mais_interesse()
    elif sys.argv[1:2] == ["copiar"]:
        copiar(*sys.argv[2:6])
    elif sys.argv[1:2] == ["problemas"]:
        problemas(*sys.argv[2:])
    elif sys.argv[1:2] == ["orcamento"]:
        orcamento(sys.argv[2], sys.argv[3])
    elif sys.argv[1:2] == ["cargos"]:
        cargos()
    elif sys.argv[1:2] == ["profissoes"]:
        profissoes(sys.argv[2])
    else:
        main()
