# Ferramentas de IA do @roquecneto

Página publicada como artifact do Claude (link na bio ou no comentou, recebeu).

- `index.html`: a página. Abas por âncora: `#profissao` (pronta), `#semana`, `#pedido`, `#biblioteca` (em breve). Link direto para uma ocupação: `#o2411`.
- `dados.json`: 427 ocupações e 3.265 tarefas da ISCO-08 com o índice de exposição à IA generativa da OIT (Gmyrek et al. 2025, CC BY 4.0), traduzidas para o português.
- `base_en.json` + `juntar.py`: base original e o script que monta o `dados.json` a partir das traduções.

A IA da página roda na conta do Claude de quem abre (capacidade `sample`). Sem conta conectada, o botão abre o claude.ai com o pedido já escrito.
