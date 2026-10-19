# Publicador do @roquecneto

Os posts entram neste repositório. Uma GitHub Action publica no Instagram pela API oficial da Meta.

## Como funciona

1. O Claude monta o carrossel e mostra para você no chat.
2. Quando você diz "publica", ele cria `posts/<data>-<slug>/` com os JPEGs e o `post.json` (status `aprovado`) e faz push.
3. A Action `Publicar no Instagram` roda, publica e grava de volta no `post.json` o status `publicado` e o link do post.
4. O Claude lê o `post.json` e te devolve o link.

Nada vai ao ar sem `status: "aprovado"`. Um post com status `publicando` ou `publicado` nunca é reenviado, então não tem risco de duplicar.

### Formato do post.json

```json
{
  "status": "aprovado",
  "imagens": ["01.jpg", "02.jpg", "03.jpg"],
  "legenda": "Texto da legenda com #hashtags"
}
```

Status possíveis: `rascunho`, `aprovado`, `publicando`, `publicado`, `erro` (com o campo `erro` explicando). Para tentar de novo depois de um erro, volte para `aprovado`.

## Configuração (uma vez só)

### 1. Conta do Instagram

O @roquecneto precisa ser conta **profissional** (Criador de conteúdo ou Empresa). No app: Configurações > Tipo de conta e ferramentas > Mudar para conta profissional. Não precisa de Página do Facebook.

### 2. App na Meta

1. Em developers.facebook.com, crie um app (tipo Empresa) ou reaproveite um seu.
2. Adicione o produto **Instagram** e escolha "API com login do Instagram".
3. Em Funções do app > Testadores do Instagram, adicione o @roquecneto e aceite o convite no Instagram (Configurações > Apps e sites > Convites de testador).
4. Com o app em modo de desenvolvimento, as permissões funcionam para contas com função no app. Não precisa de App Review para publicar no seu próprio perfil.

### 3. Token e id da conta

1. No painel do produto Instagram, em "Gerar tokens de acesso", conecte o @roquecneto e gere o token com `instagram_business_basic` e `instagram_business_content_publish`.
2. Esse token já é de longa duração (60 dias).
3. Para achar o id da conta, abra no navegador:
   `https://graph.instagram.com/me?fields=user_id,username&access_token=SEU_TOKEN`
   O valor de `user_id` é o `IG_USER_ID`.

### 4. Segredos no GitHub

Em Settings > Secrets and variables > Actions:

| Segredo | Valor |
|---|---|
| `IG_USER_ID` | o `user_id` do passo anterior |
| `IG_ACCESS_TOKEN` | o token |
| `GH_PAT` | token fine-grained do GitHub só deste repo, com "Secrets: Read and write" (usado para renovar o token todo mês) |

Opcional: a variável `IG_API_VERSION` (padrão `v23.0`) se a Meta descontinuar essa versão.

### 5. Repositório público

A Meta precisa baixar as imagens de um endereço público. As imagens saem via jsDelivr apontando para o commit, então o repositório precisa ser **público**. Como só entra aqui o que foi aprovado para publicar, nada vaza antes da hora.

### 6. Teste

Em Actions > Publicar no Instagram > Run workflow, marque "Só validar". Se passar, o próximo post aprovado sai de verdade.

## Limites da API

- Carrossel: 2 a 10 imagens, JPEG.
- Legenda: até 2.200 caracteres e 30 hashtags.
- A Meta limita quantas publicações a API faz por 24h; para um perfil pessoal não chega perto.
- O token vence em 60 dias se não for renovado; a Action `Renovar token do Instagram` cuida disso no dia 1 de cada mês.
