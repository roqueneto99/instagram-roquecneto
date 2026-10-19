# Instruções para o Claude neste repositório

Este repositório publica no Instagram pessoal do Roque (@roquecneto). Publicar é público e irreversível.

## Regra principal

Só faça push de um post com `"status": "aprovado"` quando o Roque tiver dito, no chat e para aquele post específico, que é para publicar. Aprovação de um post não vale para outro. Na dúvida, deixe `rascunho` e pergunte.

## Procedimento

1. Mostre os PNGs e a legenda no chat antes de qualquer coisa.
2. Depois do "publica":
   - `python scripts/preparar_post.py <slug> legenda.txt img1.png ...`
   - troque o status no `post.json` para `aprovado`
   - confira: legenda sem travessão longo, 2 a 10 imagens, até 2.200 caracteres
   - commit `post: <slug>` e push na `main`
3. Acompanhe com `gh run watch` ou `gh run list --workflow publicar.yml`.
4. Faça `git pull` e leia o `post.json`: se `publicado`, mande o link ao Roque; se `erro`, explique o campo `erro` e só volte para `aprovado` com o ok dele.

## Nunca

- Nunca altere um post `publicado` ou `publicando`.
- Nunca coloque token ou senha em arquivo do repositório.
