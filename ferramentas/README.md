# Ferramentas de IA do @roquecneto

Página publicada como artifact do Claude (link na bio ou no comentou, recebeu).

- `index.html`: a página. Abas por âncora: `#profissao` e `#semana` (prontas), `#pedido`, `#biblioteca` (em breve). Link direto para uma ocupação: `#o2411` (profissão) ou `#s2411` (raio-x da semana, conta: horas × nota × 0,3 ou 0,5).
- `dados.json`: 427 ocupações e 3.265 tarefas da ISCO-08 com o índice de exposição à IA generativa da OIT (Gmyrek et al. 2025, CC BY 4.0), traduzidas para o português.
- `base_en.json` + `juntar.py`: base original e o script que monta o `dados.json` a partir das traduções.

A IA da página roda na conta do Claude de quem abre (capacidade `sample`). Sem conta conectada, o botão abre o claude.ai com o pedido já escrito.
