# Atendente de directs do @roquecneto

Um servidor pequeno que:

- **Comentou, recebeu:** quem comenta uma palavra-chave (ex.: MBA) num post recebe a mensagem no direct e uma resposta pública "Te mandei no direct!".
- **Responde directs com IA:** cada mensagem nova vira uma resposta sugerida, com categoria (MBA, dúvida de IA, comercial etc.).
- **Painel de aprovação no celular:** você aprova, edita ou descarta. No modo automático, só as categorias simples (MBA e agradecimento) saem sozinhas.
- **Passa para você:** proposta comercial, reclamação ou "quero falar com o Roque" nunca são respondidas pela IA. A conversa fica marcada "com você".
- **Avisa no celular** pelo app ntfy (ou Telegram).
- **Renova o token do Instagram sozinho** a cada 7 dias.

O que a IA sabe, o que nunca diz e as palavras-chave ficam em `regras.yaml`.

## Regras da Meta que valem sempre

- Só dá para responder quem mandou mensagem, até 24 horas depois. Resposta escrita por você (pelo painel) vale até 7 dias.
- Comentou, recebeu: um direct por comentário, até 7 dias depois do comentário.
- A conta precisa ser pública e o app precisa estar no modo Live.

## Configuração (uma vez)

### 1. No app do Instagram (celular)
Configurações > Mensagens e respostas > Ferramentas conectadas > ligar **Permitir acesso a mensagens**.

### 2. No painel de desenvolvedores da Meta (app do publicador)
1. Instagram > Configuração da API com login do Instagram.
2. Em permissões, garanta `instagram_business_basic`, `instagram_business_content_publish`, `instagram_business_manage_messages` e `instagram_business_manage_comments`.
3. **Gerar token** de novo para a @roquecneto (o novo token inclui as permissões novas). Esse token vai no Railway (passo 3) e também substitui o `IG_ACCESS_TOKEN` do GitHub.
4. Anote o **segredo do app do Instagram** (mesma tela) para o `APP_SECRET`.

### 3. No Railway
1. New Project > Deploy from GitHub repo > `roqueneto99/instagram-roquecneto`.
2. Settings > Root Directory: `directs`.
3. Adicionar um **Volume** montado em `/data`.
4. Variables:

| Variável | Valor |
|---|---|
| `DB_PATH` | `/data/directs.db` |
| `IG_ACCESS_TOKEN` | token gerado no passo 2 |
| `IG_USER_ID` | o mesmo do GitHub |
| `APP_SECRET` | segredo do app do Instagram (pode pôr dois, separados por vírgula) |
| `VERIFY_TOKEN` | uma frase qualquer, repetida no passo 4 |
| `ANTHROPIC_API_KEY` | chave da API da Anthropic |
| `PAINEL_SENHA` | senha do painel (usuário: `roque`) |
| `PAINEL_URL` | `https://<domínio>/painel` |
| `NTFY_TOPIC` | um nome difícil de adivinhar, ex.: `roque-directs-8k2p` |

5. Settings > Networking > Generate Domain.

### 4. Webhook na Meta
Instagram > Configuração da API > Configurar webhooks:
- Callback URL: `https://<domínio>/webhook`
- Verify token: o mesmo `VERIFY_TOKEN`
- Assinar os campos `messages` e `comments`.

Depois abra o painel > **Ajustes** > **Assinar mensagens e comentários**.

### 5. Avisos no celular
Instale o app **ntfy**, toque em + e assine o tópico do `NTFY_TOPIC`. No painel > Ajustes > **Mandar aviso de teste**.

## Revisão do app (se a Meta exigir)
Para receber comentários de qualquer pessoa, a Meta pede **Acesso avançado** em `instagram_business_manage_comments` (e às vezes em `manage_messages`). Isso passa por Revisão do App, com um vídeo curto mostrando o painel. Antes disso, os testes funcionam com contas que têm papel no app.

## Testes
```
pip install -r requirements.txt pytest
pytest -q
```
Os testes simulam a Meta e a IA. Nada é enviado de verdade.
