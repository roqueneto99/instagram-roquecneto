# Ferramentas de IA do @roquecneto

Página publicada como artifact do Claude (link na bio ou no comentou, recebeu).

- `index.html`: a página. Abas por âncora: `#profissao`, `#semana`, `#pedido` e `#biblioteca`. Link direto para uma ocupação: `#o2411` (profissão) ou `#s2411` (raio-x da semana, conta: horas × nota × 0,3 ou 0,5).
- `biblioteca.json`: os pedidos prontos da aba `#biblioteca` (Pedidos por profissão): 8 profissões (advogado, contador, vendedor, gestor, RH, professor, marketing, atendimento), 5 pedidos cada, cada um ligado a uma tarefa da ocupação no `dados.json`, com a nota da tarefa, o que mandar junto e o que conferir. Link direto: `#b-advogado`, `#b-rh` etc.
- `dados.json`: 427 ocupações e 3.265 tarefas da ISCO-08 com o índice de exposição à IA generativa da OIT (Gmyrek et al. 2025, CC BY 4.0), traduzidas para o português.
- `base_en.json` + `juntar.py`: base original e o script que monta o `dados.json` a partir das traduções.

Em `#pedido` (Monte seu pedido), a pessoa escreve uma frase e responde 4 perguntas (para quem, entrega, material, cuidado); o pedido é montado sem IA, parte por parte com o porquê, e o Claude só entra no botão Melhorar.

A IA da página roda na conta do Claude de quem abre (capacidade `sample`). Sem conta conectada, o botão abre o claude.ai com o pedido já escrito.

Em `#biblioteca`, cada pedido tem Copiar e Abrir no Claude; com a conta conectada, Adaptar ao meu caso reescreve o pedido com o caso da pessoa (streaming, com Parar).
