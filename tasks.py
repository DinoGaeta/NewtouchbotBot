from __future__ import annotations
from datetime import datetime, timedelta
import os
import random
import html
import time as pytime

import requests
import feedparser
import redis
from dotenv import load_dotenv

from .celery_app import app  # Importa l'app Celery

# Carica le variabili d'ambiente
load_dotenv()

# ================== CONFIG ==================
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
START_HOUR = int(os.getenv("START_HOUR", "7"))
END_HOUR = int(os.getenv("END_HOUR", "22"))

SHUBUKAN_IMAGE_URL = os.getenv(
    "SHUBUKAN_IMAGE_URL",
    "https://raw.githubusercontent.com/openai-examples/assets/main/shubukan_orari.png"
)

UA_HEADERS = {"User-Agent": "TouchBot v6.0 (Celery-based)"}

# Connessione a Redis
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# ================== FEEDS & KEYWORDS ==================
FEEDS_TECH = [
    "https://www.ilpost.it/tecnologia/feed/",
    "https://www.tomshw.it/feed/",
    "https://www.dday.it/feed",
    "https://www.hdblog.it/rss.xml",
]
FEEDS_FINANCE = [
    "https://www.ilsole24ore.com/rss/finanza.xml",
    "https://www.ansa.it/sito/notizie/economia/economia_rss.xml",
    "https://it.investing.com/rss/news_285.rss",
]
FEEDS_GAMING = [
    "https://www.eurogamer.it/feed/rss",
    "https://www.spaziogames.it/feed",
]
FEEDS_CINEMA = [
    "https://www.badtaste.it/feed/cinema/",
    "https://www.cinematographe.it/feed/",
]
FEEDS_AGENCIES = [
    "https://www.ansa.it/sito/notizie/topnews/topnews_rss.xml",
    "https://www.ansa.it/sito/notizie/politica/politica_rss.xml",
]
ALERT_KEYWORDS = [
    "ultim'ora", "breaking", "allerta", "allarme", "urgente",
    "attentato", "terremoto", "guerra", "missili",
    "evacuazione", "blackout", "cyberattacco",
]

ROTATION = [FEEDS_TECH, FEEDS_FINANCE, FEEDS_GAMING, FEEDS_CINEMA, FEEDS_AGENCIES]

# ================== UTILS (non-task) ==================
def log(msg: str):
    safe = msg.encode("utf-8", "ignore").decode("utf-8")
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {safe}")

def clean_markdown(text: str) -> str:
    text = html.escape(text)
    text = text.replace("`", "").replace("_", "").replace("*", "")
    return text

def telegram_send(text: str):
    if not BOT_TOKEN or not CHAT_ID:
        log("⚠️ BOT_TOKEN o CHAT_ID non settati, skip telegram_send.")
        return
    safe_text = clean_markdown(text)
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": safe_text, "parse_mode": "Markdown"},
            timeout=10,
        )
        if not r.ok:
            log(f"⚠️ Telegram error: {r.text}")
    except Exception as e:
        log(f"⚠️ Telegram network error: {e}")

def fetch_feed_entries(feed_urls: list[str]):
    random.shuffle(feed_urls)
    all_entries = []
    for url in feed_urls:
        try:
            resp = requests.get(url, headers=UA_HEADERS, timeout=15)
            if not resp.ok:
                log(f"⚠️ HTTP {resp.status_code} su feed {url}")
                continue
            feed = feedparser.parse(resp.content)
            all_entries.extend(feed.entries)
        except Exception as ex:
            log(f"⚠️ Feed error ({url}): {ex}")
    return all_entries

def generate_comment_AI(title: str, summary: str) -> str:
    prompt = f'''Sei un analista di notizie acuto e imparziale. 
    Basandoti su questo titolo e sommario, scrivi un commento di una singola frase (massimo 20 parole) che ne catturi l'essenza o l'implicazione più importante. Sii originale.
    Titolo: {title}
    Sommario: {summary}
    Commento:'''
    try:
        response = requests.post(
            OLLAMA_API_URL,
            json={"model": "phi-3-mini", "prompt": prompt, "stream": False},
            timeout=20,
        )
        response.raise_for_status()
        return response.json()["response"].strip()
    except Exception as e:
        log(f"⚠️ Errore chiamata a Ollama: {e}")
        return "Un aggiornamento importante nel settore."

def hourly_brand_for(hour_idx: int) -> tuple[str, list[str]]:
    group = ROTATION[hour_idx % len(ROTATION)]
    if group is FEEDS_TECH:
        return (" Touch Tech — Morning Spark", FEEDS_TECH)
    if group is FEEDS_FINANCE:
        return (" Touch Finance — Lunch Byte", FEEDS_FINANCE)
    if group is FEEDS_GAMING:
        return ("⚡ Touch Gaming — Brain Snack", FEEDS_GAMING)
    if group is FEEDS_CINEMA:
        return (" Touch Cinema — Insight", FEEDS_CINEMA)
    return (" Touch Top News — Agenzie", FEEDS_AGENCIES)

# ================== TASKS CELERY ==================

@app.task
def send_sponsor_photo():
    if not BOT_TOKEN or not CHAT_ID:
        log("⚠️ BOT_TOKEN o CHAT_ID non settati, salto sponsor.")
        return
    try:
        caption = (
            "<b>Shubukan Torino — Kendo Jodo Iaido Naginata</b>\n"
            "Allenamenti a Torino e Carmagnola. Lezione di prova gratuita.\n"
            "<i>Allenati alla calma nel movimento.</i>\n"
            ' <a href="https://www.shubukan.it">Visita il sito</a>'
        )
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={
                "chat_id": CHAT_ID,
                "photo": SHUBUKAN_IMAGE_URL,
                "caption": caption,
                "parse_mode": "HTML",
            },
            timeout=15,
        )
        if not r.ok:
            log(f"⚠️ Telegram photo error: {r.text}")
    except Exception as e:
        log(f"⚠️ Errore rete foto sponsor: {e}")

@app.task
def send_article(feed_group: list[str], brand_name: str):
    entries = fetch_feed_entries(feed_group)
    random.shuffle(entries)
    
    for e in entries[:8]:
        link = getattr(e, "link", "")
        if link and redis_client.sismember("sent_links", link):
            continue
        title = getattr(e, "title", "").strip()
        if not title:
            continue
        
        # Trovato un articolo valido, ora lo processiamo
        summary = getattr(e, "summary", "").strip()[:400]
        comment = f"\n *Commento AI:* {generate_comment_AI(title, summary)}"

        msg = f"*{brand_name}*\n\n *{title}*\n{summary}\n {link}{comment}"
        telegram_send(msg)
        
        # Invia lo sponsor subito dopo
        send_sponsor_photo.delay()

        if link:
            redis_client.sadd("sent_links", link)
        log(f"[OK] Inviato: {brand_name} - {title}")
        return True # Indica successo

    log(f"⚠️ Nessuna notizia fresca trovata per {brand_name}.")
    telegram_send(f"⚠️ Nessuna notizia trovata per *{brand_name}*.")
    return False # Indica fallimento

@app.task
def send_alerts():
    entries = fetch_feed_entries(FEEDS_AGENCIES)
    sent_any = False
    for e in entries[:15]:
        try:
            link = getattr(e, "link", "") or getattr(e, "id", "")
            if not link or redis_client.sismember("alert_sent_ids", link):
                continue

            published_time = getattr(e, "published_parsed", None)
            if published_time:
                published = datetime.fromtimestamp(pytime.mktime(published_time))
                if datetime.now() - published > timedelta(minutes=60):
                    continue
            
            txt = (getattr(e, "title", "") + " " + getattr(e, "summary", "")).lower()
            if not any(k in txt for k in ALERT_KEYWORDS):
                continue

            title = getattr(e, "title", "Aggiornamento").strip()
            summary = getattr(e, "summary", "").strip()[:400]
            msg = f" *ALLERTA IMPORTANTE* — fonte agenzia\n\n️ *{title}*\n{summary}\n {link}"
            
            telegram_send(msg)
            redis_client.sadd("alert_sent_ids", link)
            log(f" ALERT: {title}")
            sent_any = True
        except Exception as ex:
            log(f"⚠️ Errore invio alert: {ex}")
    return sent_any

@app.task
def reset_daily_tasks():
    redis_client.delete("sent_today_hours", "sent_links", "alert_sent_ids")
    log(" Reset giornaliero dei task completato (chiavi Redis pulite).")

@app.task
def hourly_publication_manager():
    now = datetime.now()
    h = now.hour
    key = f"{h:02d}:00"

    # Controlla se l'ora è nel range e se non è già stata pubblicata
    if START_HOUR <= h <= END_HOUR and not redis_client.sismember("sent_today_hours", key):
        log(f"Avvio pubblicazione oraria per le {h}:00")
        hour_idx = h - START_HOUR
        brand_name, feeds = hourly_brand_for(hour_idx)
        
        telegram_send(f" Pubblicazione oraria: *{brand_name}*")
        send_article.delay(feeds, brand_name)
        
        # Segna l'ora come pubblicata
        redis_client.sadd("sent_today_hours", key)
    else:
        log(f"Nessuna pubblicazione programmata per le {h}:00 o già eseguita.")
