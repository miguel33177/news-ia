"""
Feeds RSS -> Traducao pt-PT -> Telegram
"""

import html
import json
import os
import re
import sys

import feedparser
import requests

FEEDS = [
    ("0xMovez", "https://movez.substack.com/feed"),
    ("TLDR AI", "https://tldr.tech/api/rss/ai"),
    ("Latent Space", "https://www.latent.space/feed"),
]

STATE_FILE = "processed.json"
MAX_FIRST_RUN = 2

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"].strip()
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"].strip()
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"].strip()

ANTHROPIC_MODEL = "claude-haiku-4-5-20251001"

BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36",
    "Accept": "application/rss+xml, application/xml, text/xml, */*",
}


def load_state() -> set:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()


def save_state(ids: set) -> None:
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(sorted(ids), f, indent=2, ensure_ascii=False)


def translate_pt_pt(title: str, summary: str) -> dict:
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
        # mostra a razao exata do Telegram no log
        raise RuntimeError(f"Telegram {resp.status_code}: {resp.text}")


def fetch_page_highlights(link: str, max_items: int = 8) -> str:
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
    text = re.sub(r"<[^>]+>", " ", raw_html or "")
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + "…"
    return text


def fetch_feed(url: str):
    """Descarrega o feed com headers de browser e so depois faz o parse."""
    try:
        resp = requests.get(url, timeout=30, headers=BROWSER_HEADERS)
        resp.raise_for_status()
        return feedparser.parse(resp.content)
    except Exception as exc:
        print(f"Falha ao descarregar {url}: {exc}", file=sys.stderr)
        return feedparser.parse(url, agent=BROWSER_HEADERS["User-Agent"])


def process_feed(source: str, url: str, processed: set) -> int:
    feed = fetch_feed(url)
    if feed.bozo and not feed.entries:
        print(f"[{source}] Erro ao ler o feed: {feed.bozo_exception}", file=sys.stderr)
        return 0

    first_run_for_feed = not any(
        e.get("id", e.get("link")) in processed for e in feed.entries
    )

    new_entries = [e for e in feed.entries if e.get("id", e.get("link")) not in processed]

    if first_run_for_feed:
        for e in new_entries[MAX_FIRST_RUN:]:
            processed.add(e.get("id", e.get("link")))
        new_entries = new_entries[:MAX_FIRST_RUN]

    sent = 0
    for entry in reversed(new_entries):
        entry_id = entry.get("id", entry.get("link"))
        title = entry.get("title", "(sem titulo)")
        link = entry.get("link", "")
        summary = clean_summary(entry.get("summary", ""))
        if not summary:
            summary = fetch_page_highlights(link)
        published = entry.get("published", "")

        try:
            tr = translate_pt_pt(title, summary)
            titulo, resumo = tr["titulo"], tr["resumo"]
        except Exception as exc:
            print(f"[{source}] Falha na traducao ({exc}); envio o original.", file=sys.stderr)
            titulo, resumo = title, summary

        message = (
            f"📡 <b>{html.escape(source)}</b>\n"
            f"📰 <b>{html.escape(titulo)}</b>\n\n"
            f"{html.escape(resumo)}\n\n"
            f"🗓 {html.escape(published)}\n"
            f"🔗 {link}"
        )

        try:
            send_telegram(message)
            processed.add(entry_id)
            sent += 1
            print(f"[{source}] Enviado: {title}")
        except Exception as exc:
            print(f"[{source}] Falha no envio de '{title}': {exc}", file=sys.stderr)

    return sent


def main() -> None:
    processed = load_state()
    total = 0
    for source, url in FEEDS:
        total += process_feed(source, url, processed)
    save_state(processed)
    print(f"Concluido. {total} novo(s) enviado(s), {len(processed)} no historico.")


if __name__ == "__main__":
    main()
