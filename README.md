# Notícias de IA → pt-PT → Telegram + Teams

Recebe, traduzidos para português europeu, os novos artigos de três fontes:

- **0xMovez** (movez.substack.com) — o conteúdo das contas @0xCodez / @0xMovez no X
- **TLDR AI** (tldr.tech/ai) — resumo diário técnico com os destaques do dia
- **Latent Space** (latent.space) — deep dives para quem constrói com IA + digest diário AINews

Entrega em dois canais em simultâneo:
- **Telegram** (canal ou chat privado)
- **Microsoft Teams** (opcional — só ativo se configurares o webhook)

Corre de graça no GitHub Actions, **2x por dia** (08h17 e 19h17, hora de Portugal) — sem servidor, sem nada sempre ligado.

## Como funciona

1. Duas vezes por dia, o GitHub Actions acorda e corre o `main.py`
2. O script lê os três feeds RSS (lista `FEEDS` no `main.py`)
   - Se um site bloquear o pedido direto (caso comum do Substack), tenta automaticamente o conversor `rss2json` como alternativa
3. Se houver artigos novos, traduz título e resumo para pt-PT com a API do Claude (quando o feed não traz resumo, como o TLDR, o script extrai os destaques da própria página)
4. Envia cada artigo para o **Telegram** e, se configurado, também para o **Teams**, com o link para o original
5. Guarda os IDs já enviados em `processed.json` para nunca repetir

Na primeira execução de cada fonte, envia apenas os 2 artigos mais recentes (para não inundar o chat) e marca os restantes como já vistos.

## Configuração (uma vez só)

### 1. Criar o bot do Telegram

1. No Telegram, abre uma conversa com **@BotFather**
2. Envia `/newbot` e segue as instruções (dá-lhe um nome e um username terminado em `bot`)
3. Guarda o **token** que ele te dá (algo como `1234567890:AAF...`)

### 2. Escolher o destino no Telegram: chat privado ou canal

**Chat privado (mais simples, só para ti):**
1. Envia uma mensagem qualquer ao teu bot (ex.: `/start`)
2. Abre no browser: `https://api.telegram.org/bot<O_TEU_TOKEN>/getUpdates`
3. Procura `"chat":{"id":123456789` — esse número é o teu **chat ID**

**Canal (para partilhares com mais pessoas):**
1. Cria um canal no Telegram e adiciona o bot como **administrador** (Administradores → Adicionar administrador → procura o bot pelo `@username` exato — só funciona pela app móvel, evita o desktop/web para este passo)
2. Publica uma mensagem qualquer no canal
3. Abre `https://api.telegram.org/bot<O_TEU_TOKEN>/getUpdates` e procura `"channel_post"` → dentro dele, `"chat":{"id":-100...` — o ID de canais começa sempre por `-100`
4. Usa esse número **completo, incluindo o sinal de menos** (ex.: `-1001234567890`)

Quem quiseres que receba as notícias basta entrar no canal — não precisas de mexer em nada de cada vez que alguém adere.

### 3. Obter uma chave da API do Claude

1. Vai a https://console.anthropic.com e cria uma conta
2. Em **API Keys**, cria uma chave nova e guarda-a
3. O custo é residual: traduzir títulos e resumos com o modelo Haiku custa cêntimos por mês

### 4. (Opcional) Configurar o Microsoft Teams

1. No canal do Teams onde queres receber as notícias, clica nos **três pontinhos (...)** ao lado do nome do canal → **Fluxos de trabalho** (Workflows)
2. Procura o modelo **"Enviar alertas de webhook para um canal"**
3. Escolhe a equipa e o canal de destino → **Criar fluxo**
4. Copia o **URL do webhook** gerado no fim (é longo, termina em `&sig=...`)

Se não quiseres usar o Teams, ignora este passo — o script funciona na mesma só com o Telegram.

### 5. Criar o repositório no GitHub

1. Cria um repositório novo (pode ser privado) em https://github.com/new
2. Carrega para lá estes ficheiros mantendo a estrutura:
   ```
   main.py
   requirements.txt
   .github/workflows/substack-telegram.yml
   ```
   (Pelo browser: "Add file" → "Upload files" para o `main.py` e o `requirements.txt`. Para o workflow, "Add file" → "Create new file" e escreve o caminho completo `.github/workflows/substack-telegram.yml`)

### 6. Configurar os segredos

No repositório: **Settings → Secrets and variables → Actions → New repository secret**. Cria estes:

| Nome | Valor | Obrigatório? |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | o token do BotFather | Sim |
| `TELEGRAM_CHAT_ID` | o ID do passo 2 (chat privado ou canal) | Sim |
| `ANTHROPIC_API_KEY` | a chave da consola Anthropic | Sim |
| `TEAMS_WEBHOOK_URL` | o URL do passo 4 | Não (só se quiseres Teams) |

**Importante:** o ficheiro do workflow (`.github/workflows/substack-telegram.yml`) tem de passar cada segredo ao script na secção `env:` do passo "Correr o script". Se acrescentares o `TEAMS_WEBHOOK_URL` mais tarde, confirma que também o adicionas lá — só criar o segredo não chega.

### 7. Testar

1. Vai ao separador **Actions** do repositório
2. Escolhe **"Substack para Telegram"** na barra lateral → **Run workflow**
3. Em ~1 minuto deves receber os artigos mais recentes de cada fonte

A partir daí corre sozinho, duas vezes por dia. Podes fechar tudo e esquecer.

## Personalizar

- **Adicionar ou remover fontes**: edita a lista `FEEDS` no `main.py` — qualquer feed RSS serve, basta acrescentar `("Nome", "https://.../feed")`
- **Traduzir o artigo inteiro** em vez do resumo: aumenta o `max_chars` em `clean_summary` (atenção ao limite de 4096 caracteres por mensagem do Telegram)
- **Melhor qualidade de tradução**: muda `ANTHROPIC_MODEL` para `claude-sonnet-4-6`
- **Frequência**: muda a linha `cron` no workflow. Exemplos:
  ```yaml
  - cron: "17 7,18 * * *"   # atual: 2x por dia, 08h17 e 19h17 em PT
  - cron: "17 7-22 * * *"   # de hora a hora, mas só entre as 08h e as 23h
  - cron: "17 7 * * *"      # 1x por dia, só de manhã
  ```
  Nota: o GitHub usa sempre UTC. Em Portugal isto significa +1h no horário de verão e +0h no de inverno — os horários acima "deslizam" uma hora quando muda a hora oficial.
- **Desativar o Teams temporariamente**: basta apagar (ou não definir) o segredo `TEAMS_WEBHOOK_URL`; o script deteta a ausência e ignora esse envio sem dar erro.

## Notas e limitações conhecidas

- O GitHub não garante pontualidade em execuções agendadas — atrasos de alguns minutos (por vezes mais, em picos de carga) são normais. Evitar o minuto `0` do cron (como já está configurado, no minuto 17) ajuda a reduzir isto.
- O feed do 0xMovez (Substack) por vezes bloqueia pedidos vindos de servidores — o script tenta automaticamente um serviço alternativo (`rss2json`), mas se ambos falharem numa execução, essa fonte fica simplesmente sem novidades nessa ronda; volta a tentar na próxima.
- Se o repositório ficar 60 dias sem atividade, o GitHub pausa os agendamentos; basta ir a Actions e reativar manualmente.
- Para o Teams, o fluxo do tipo "Enviar alertas de webhook para um canal" exige um **Adaptive Card** completo no corpo do pedido — texto simples não é aceite por este modelo. O `main.py` já trata disto automaticamente.
- **Segurança**: nunca partilhes o `TELEGRAM_BOT_TOKEN`, a `ANTHROPIC_API_KEY` ou o `TEAMS_WEBHOOK_URL` em conversas, capturas de ecrã ou repositórios públicos. Se algum for exposto, revoga-o e gera um novo (`/revoke` no @BotFather para o Telegram; nova chave na consola da Anthropic; recriar o fluxo no Power Automate para o Teams).
