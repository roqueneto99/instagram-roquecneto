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
            "instagram_positions": ["stream", "reels", "explore", "explore_home"]}
NOME_CAMP = "RN · Seguidores · Engajamento (teste A/B)"
NOME_CONJ = "Profissionais formados · BR · 25-50 · engajamento"
MEDIA_APURACAO = "18082101758401845"


def so_instagram(adset_id):
    t = A._api("GET", adset_id, fields="name,targeting")
    alvo = t["targeting"]
    for chave in ("facebook_positions", "messenger_positions", "audience_network_positions",
                  "whatsapp_positions", "threads_positions", "device_platforms"):
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


if __name__ == "__main__":
    main()
