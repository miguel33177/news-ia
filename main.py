"""
Feeds RSS -> Traducao pt-PT -> Telegram + Microsoft Teams
Verifica varios feeds, traduz artigos novos com a API do Claude
e envia-os para um chat do Telegram e/ou um canal do Teams.
"""

import html
import json
import os
import re
import sys

import feedparser
import requests

# ------------------------- Configuracao -------------------------

FEEDS = [
    ("0xMovez", "https://movez.substack.com/feed"),
    ("TLDR AI", "https://tldr.tech/api/rss/ai"),
    ("Latent Space", "https://www.latent.space/feed"),
]

STATE_FILE = "processed.json"
MAX_FIRST_RUN = 2  # na primeira execucao de um feed, envia no maximo 2

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"].strip()
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"].strip()
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"].strip()

# Opcional: se nao definires este segredo no GitHub, o envio para o Teams
# e simplesmente ignorado (o Telegram continua a funcionar na mesma).
TEAMS_WEBHOOK_URL = os.environ.get("TEAMS_WEBHOOK_URL", "").strip()

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}

# ------------------------- Estado -------------------------


def load_state() -> set:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_state(ids: set) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, indent=2, ensure_ascii=False)


# ------------------------- Obter feeds -------------------------


def get_entries(source: str, url: str) -> list:
    """
    Devolve uma lista de dicts {id, title, link, summary, published}.
    1) tenta descarregar o feed diretamente;
    2) se o site bloquear (pagina de verificacao em vez de XML),
       usa o conversor rss2json como fallback.
    """
    # tentativa direta
    try:
        resp = requests.get(url, timeout=30, headers=BROWSER_HEADERS)
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
        if feed.entries:
            return [
                {
                    "id": e.get("id", e.get("link")),
                    "title": e.get("title", "(sem titulo)"),
                    "link": e.get("link", ""),
                    "summary": e.get("summary", ""),
                    "published": e.get("published", ""),
                }
                for e in feed.entries
            ]
        print(f"[{source}] Feed direto sem artigos "
              f"(inicio da resposta: {resp.text[:120]!r}); a tentar rss2json...",
              file=sys.stderr)
    except Exception as exc:
        print(f"[{source}] Falha no download direto ({exc}); a tentar rss2json...",
              file=sys.stderr)

    # fallback: rss2json
    try:
        resp = requests.get(
            "https://api.rss2json.com/v1/api.json",
            params={"rss_url": url},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("status") != "ok":
            print(f"[{source}] rss2json devolveu: {data.get('status')}", file=sys.stderr)
            return []
        return [
            {
                "id": item.get("guid") or item.get("link"),
                "title": item.get("title", "(sem titulo)"),
                "link": item.get("link", ""),
                "summary": item.get("description", "") or item.get("content", ""),
                "published": item.get("pubDate", ""),
            }
            for item in data.get("items", [])
        ]
    except Exception as exc:
        print(f"[{source}] Fallback rss2json tambem falhou: {exc}", file=sys.stderr)
        return []


# ------------------------- Traducao -------------------------


def translate_pt_pt(title: str, summary: str) -> dict:
    """Traduz titulo e resumo para portugues europeu via API do Claude."""
    prompt = (
        "Traduz o titulo e o resumo abaixo para portugues europeu (pt-PT, "
        "nunca pt-BR). Manten termos tecnicos de IA/programacao em ingles "
        "quando for o habitual (ex.: 'prompt', 'loop', 'workflow', nomes de "
        "produtos e modelos). Manten emojis se existirem. Responde APENAS "
        "com JSON valido, sem markdown, no formato: "
        '{"titulo": "...", "resumo": "..."}\n\n'
        f"TITULO: {title}\n\nRESUMO: {summary}"
    )
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": ANTHROPIC_MODEL,
            "max_tokens": 1024,
            "messages": [{"role": "user", "content": prompt}],
        },
        timeout=60,
    )
    resp.raise_for_status()
    text = resp.json()["content"][0]["text"].strip()
    text = re.sub(r"^```(json)?|```$", "", text, flags=re.MULTILINE).strip()
    return json.loads(text)


# ------------------------- Telegram -------------------------


def send_telegram(message: str) -> None:
    resp = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
        json={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": False,
        },
        timeout=30,
    )
    if not resp.ok:
        raise RuntimeError(f"Telegram {resp.status_code}: {resp.text}")


# ------------------------- Microsoft Teams -------------------------


def send_teams(source: str, titulo: str, resumo: str, published: str, link: str) -> None:
    """
    Envia o artigo para o canal do Teams via webhook do Power Automate.
    Este tipo de fluxo ("Enviar alertas de webhook para um canal") exige
    um Adaptive Card completo em 'attachments' -- texto simples nao chega.
    Se TEAMS_WEBHOOK_URL nao estiver configurado, nao faz nada (Telegram
    continua a funcionar normalmente).
    """
    if not TEAMS_WEBHOOK_URL:
        return

    payload = {
        "type": "message",
        "attachments": [
            {
                "contentType": "application/vnd.microsoft.card.adaptive",
                "content": {
                    "type": "AdaptiveCard",
                    "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
                    "version": "1.4",
                    "body": [
                        {
                            "type": "TextBlock",
                            "text": f"📡 {source}",
                            "weight": "Bolder",
                            "size": "Small",
                            "color": "Accent",
                        },
                        {
                            "type": "TextBlock",
                            "text": titulo,
                            "weight": "Bolder",
                            "size": "Medium",
                            "wrap": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": resumo,
                            "wrap": True,
                        },
                        {
                            "type": "TextBlock",
                            "text": published,
                            "isSubtle": True,
                            "size": "Small",
                            "wrap": True,
                        },
                    ],
                    "actions": [
                        {
                            "type": "Action.OpenUrl",
                            "title": "Ler original",
                            "url": link,
                        }
                    ],
                },
            }
        ],
    }

    resp = requests.post(TEAMS_WEBHOOK_URL, json=payload, timeout=30)
    if not resp.ok:
        raise RuntimeError(f"Teams {resp.status_code}: {resp.text}")


# ------------------------- Utilidades -------------------------


def fetch_page_highlights(link: str, max_items: int = 8) -> str:
    """Fallback: extrai os titulos (h3) da pagina quando o feed nao tem resumo."""
    try:
        resp = requests.get(link, timeout=30, headers=BROWSER_HEADERS)
        resp.raise_for_status()
        titles = re.findall(r"<h3[^>]*>(.*?)</h3>", resp.text, re.DOTALL)
        clean = []
        for t in titles:
            t = html.unescape(re.sub(r"<[^>]+>", "", t)).strip()
            if t and "Sponsor" not in t:
                clean.append(t)
        return "\n".join(f"• {t}" for t in clean[:max_items])
    except Exception as exc:
        print(f"Falha ao extrair destaques de {link}: {exc}", file=sys.stderr)
        return ""


def clean_summary(raw_html: str, max_chars: int = 600) -> str:
    """Remove HTML e limita o tamanho do resumo."""
    text = re.sub(r"<[^>]+>", " ", raw_html or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"
    return text


def process_feed(source: str, url: str, processed: set) -> int:
    """Processa um feed; devolve o numero de artigos enviados."""
    entries = get_entries(source, url)
    if not entries:
        print(f"[{source}] Sem artigos disponiveis nesta execucao.", file=sys.stderr)
        return 0

    first_run_for_feed = not any(e["id"] in processed for e in entries)
    new_entries = [e for e in entries if e["id"] not in processed]

    if first_run_for_feed:
        for e in new_entries[MAX_FIRST_RUN:]:
            processed.add(e["id"])
        new_entries = new_entries[:MAX_FIRST_RUN]

    sent = 0
    for entry in reversed(new_entries):  # do mais antigo para o mais recente
        summary = clean_summary(entry["summary"])
        if not summary:
            summary = fetch_page_highlights(entry["link"])

        try:
            tr = translate_pt_pt(entry["title"], summary)
            titulo, resumo = tr["titulo"], tr["resumo"]
        except Exception as exc:
            print(f"[{source}] Falha na traducao ({exc}); envio o original.", file=sys.stderr)
            titulo, resumo = entry["title"], summary

        # ---- Telegram ----
        message = (
            f"📡 <b>{html.escape(source)}</b>\n"
            f"📰 <b>{html.escape(titulo)}</b>\n\n"
            f"{html.escape(resumo)}\n\n"
            f"🗓 {html.escape(entry['published'])}\n"
            f"🔗 {entry['link']}"
        )
        telegram_ok = True
        try:
            send_telegram(message)
            print(f"[{source}] Enviado (Telegram): {entry['title']}")
        except Exception as exc:
            telegram_ok = False
            print(f"[{source}] Falha no envio Telegram de '{entry['title']}': {exc}", file=sys.stderr)

        # ---- Microsoft Teams ----
        teams_ok = True
        try:
            send_teams(source, titulo, resumo, entry["published"], entry["link"])
            if TEAMS_WEBHOOK_URL:
                print(f"[{source}] Enviado (Teams): {entry['title']}")
        except Exception as exc:
            teams_ok = False
            print(f"[{source}] Falha no envio Teams de '{entry['title']}': {exc}", file=sys.stderr)

        # marca como processado se pelo menos um canal recebeu com sucesso
        if telegram_ok or teams_ok:
            processed.add(entry["id"])
            sent += 1

    return sent


# ------------------------- Fluxo principal -------------------------


def main() -> None:
    processed = load_state()
    total = 0
    for source, url in FEEDS:
        total += process_feed(source, url, processed)
    save_state(processed)
    print(f"Concluido. {total} novo(s) enviado(s), {len(processed)} no historico.")


if __name__ == "__main__":
    main()
