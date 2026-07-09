# Notícias de IA → pt-PT → Telegram

Recebe no Telegram, traduzidos para português europeu, os novos artigos de três fontes:

- **0xMovez** (movez.substack.com) — o conteúdo das contas @0xCodez / @0xMovez no X
- **TLDR AI** (tldr.tech/ai) — resumo diário técnico com os destaques do dia
- **Latent Space** (latent.space) — deep dives para quem constrói com IA + digest diário AINews

Conta com ~2 a 4 mensagens por dia no total.

Corre de graça no GitHub Actions — sem servidor, sem nada sempre ligado.

## Como funciona

1. A cada hora, o GitHub Actions acorda e corre o `main.py`
2. O script lê os três feeds RSS (lista `FEEDS` no `main.py`)
3. Se houver artigos novos, traduz título e resumo para pt-PT com a API do Claude (quando o feed não traz resumo, como o TLDR, o script extrai os destaques da própria página)
4. Envia cada artigo para o teu chat do Telegram com o link para o original
5. Guarda os IDs já enviados em `processed.json` para nunca repetir

Na primeira execução envia apenas os 2 artigos mais recentes de cada fonte (para não inundar o chat) e marca os restantes como já vistos.

## Configuração (uma vez só, ~15 minutos)

### 1. Criar o bot do Telegram

1. No Telegram, abre uma conversa com **@BotFather**
2. Envia `/newbot` e segue as instruções (dá-lhe um nome e um username terminado em `bot`)
3. Guarda o **token** que ele te dá (algo como `1234567890:AAF...`)

### 2. Descobrir o teu chat ID

1. Envia uma mensagem qualquer ao teu bot novo (ex.: "olá")
2. Abre no browser: `https://api.telegram.org/bot<O_TEU_TOKEN>/getUpdates`
3. Procura `"chat":{"id":123456789` — esse número é o teu **chat ID**

### 3. Obter uma chave da API do Claude

1. Vai a https://console.anthropic.com e cria uma conta
2. Em **API Keys**, cria uma chave nova e guarda-a
3. O custo é residual: traduzir títulos e resumos com o modelo Haiku custa cêntimos por mês

### 4. Criar o repositório no GitHub

1. Cria um repositório novo (pode ser privado) em https://github.com/new
2. Carrega para lá estes ficheiros mantendo a estrutura:
   ```
   main.py
   requirements.txt
   .github/workflows/substack-telegram.yml
   ```
   (Podes fazê-lo pelo browser: "Add file" → "Upload files". Para o workflow, cria o ficheiro com "Add file" → "Create new file" e escreve o caminho `.github/workflows/substack-telegram.yml`)

### 5. Configurar os segredos

No repositório: **Settings → Secrets and variables → Actions → New repository secret**. Cria estes três:

| Nome | Valor |
|---|---|
| `TELEGRAM_BOT_TOKEN` | o token do BotFather |
| `TELEGRAM_CHAT_ID` | o número do passo 2 |
| `ANTHROPIC_API_KEY` | a chave da consola Anthropic |

### 6. Testar

1. Vai ao separador **Actions** do repositório
2. Escolhe "Substack para Telegram" → **Run workflow**
3. Em ~1 minuto deves receber os 3 artigos mais recentes no Telegram

A partir daí corre sozinho a cada hora. Podes fechar tudo e esquecer.

## Personalizar

- **Adicionar ou remover fontes**: edita a lista `FEEDS` no `main.py` — qualquer feed RSS serve, basta acrescentar `("Nome", "https://.../feed")`
- **Traduzir o artigo inteiro** em vez do resumo: aumenta o `max_chars` em `clean_summary` (atenção ao limite de 4096 caracteres por mensagem do Telegram)
- **Melhor qualidade de tradução**: muda `ANTHROPIC_MODEL` para `claude-sonnet-4-6`
- **Frequência**: muda a linha `cron` no workflow (ex.: `0 */3 * * *` = a cada 3 horas)

## Notas

- O GitHub por vezes atrasa execuções agendadas alguns minutos — é normal
- Se o repositório ficar 60 dias sem atividade, o GitHub pausa os agendamentos; basta ir a Actions e reativar (ou o commit automático do `processed.json` trata disso enquanto houver artigos novos)
