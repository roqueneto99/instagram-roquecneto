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

## Anúncios (Meta Ads)

- Posts com bloco `"anuncio": {"conjuntos": [...]}` viram anúncio sozinhos logo depois de publicados (`scripts/anunciar.py`, conjuntos em `anuncios.json`).
- No "publica" desses posts, troque também `anuncio.status` para `aprovado`. Sem isso o post sai e o anúncio não.
- O script usa o próprio post como criativo, copia botão e link de um anúncio que já existe no conjunto, pausa os anúncios antigos e mantém no máximo 2 automáticos ativos. Não mexe em orçamento.
- Token: secret `META_ADS_TOKEN` (token de usuário estendido, app "Publicador roquecneto", ads_management; vence em 60 dias, renovar no Explorador da Graph API + Depurador › Estender). Teste sem gasto: `anuncios.yml` com `teste_media_id`. `gh workflow run anuncios.yml` lista campanhas e conjuntos (só leitura).
- O workflow grava o bloco `anuncio` de posts já publicados; isso é permitido. O resto do post publicado continua intocável.

## Nunca

- Nunca altere um post `publicado` ou `publicando`.
- Nunca coloque token ou senha em arquivo do repositório.
