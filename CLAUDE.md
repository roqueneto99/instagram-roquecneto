# Instruções para o Claude neste repositório

Este repositório publica no Instagram pessoal do Roque (@roquecneto). Publicar é público e irreversível.

## Visual dos posts

Todo carrossel segue o design system "Roque Neto Posts" (https://claude.ai/artifact/3GzondSYQ8WUUTXMx3sq3w): leia o `project/README.md` dele antes de montar os cards. Ele define a série (e a cor) por assunto, os modelos de card e as regras de texto.

## Regra principal

Só faça push de um post com `"status": "aprovado"` quando o Roque tiver dito, no chat e para aquele post específico, que é para publicar. Aprovação de um post não vale para outro. Na dúvida, deixe `rascunho` e pergunte.

## Procedimento

1. Mostre os PNGs e a legenda no chat antes de qualquer coisa.
2. Depois do "publica":
   - `python scripts/preparar_post.py <slug> legenda.txt img1.png ...`
   - troque o status no `post.json` para `aprovado` (se o Roque pediu horário, acrescente `agendado_para` com fuso -03:00)
   - confira: legenda sem travessão longo, 2 a 10 imagens, até 2.200 caracteres
   - commit `post: <slug>` e push na `main`
3. Acompanhe com `gh run watch` ou `gh run list --workflow publicar.yml`.
4. Faça `git pull` e leia o `post.json`: se `publicado`, mande o link ao Roque; se `erro`, explique o campo `erro` e só volte para `aprovado` com o ok dele.

## LinkedIn

Todo post também vai para o perfil pessoal do Roque no LinkedIn, salvo se ele disser "só no Instagram".
- No "publica", além do `status` do Instagram, ponha `"linkedin": {"status": "aprovado"}` no `post.json` (com `agendado_para` se houver horário).
- Texto do LinkedIn: use `"linkedin": {"texto": ...}` quando a legenda do Instagram não servir (até 3.000 caracteres, sem travessão longo). Mostre esse texto ao Roque antes.
- Carrossel vira post de documento (PDF); vídeo vira vídeo nativo; story do Instagram vai como vídeo.
- Status e link do LinkedIn ficam dentro do bloco `linkedin`. Mesmas regras: nunca mexa em `publicado` ou `publicando`.
- O token (`LINKEDIN_TOKEN`) vence a cada 60 dias; renovar pelo gerador de tokens do app "Publicador Roque Neto" no portal de desenvolvedores.

## Nunca

- Nunca altere um post `publicado` ou `publicando`.
- Nunca coloque token ou senha em arquivo do repositório.
