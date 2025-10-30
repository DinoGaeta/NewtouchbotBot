from __future__ import annotations
import os
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Importa i task dal nostro modulo tasks
from . import tasks

# Carica le variabili d'ambiente
load_dotenv()

app = Flask(__name__)

# ================== SICUREZZA ==================
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN")

@app.before_request
def check_admin_token():
    # Protegge solo le route che iniziano con /forza
    if request.path.startswith('/forza'):
        if not ADMIN_TOKEN or request.headers.get('X-Admin-Token') != ADMIN_TOKEN:
            return "Access Denied", 403

# ================== DATI PER LE ROUTE ==================
# Questi dati sono necessari solo all'API per mappare gli slot ai task
FEEDS_TECH = tasks.FEEDS_TECH
FEEDS_FINANCE = tasks.FEEDS_FINANCE
FEEDS_GAMING = tasks.FEEDS_GAMING
FEEDS_CINEMA = tasks.FEEDS_CINEMA
FEEDS_AGENCIES = tasks.FEEDS_AGENCIES

# ================== ROUTES API ==================

@app.route("/")
def home() -> str:
    return "TouchBot v6.0 API Server — Celery Architecture ✅"

@app.route("/health")
def health() -> str:
    return "ok"

@app.route("/forza/<slot>")
def forza(slot: str) -> tuple[str, int]:
    slot = slot.lower().strip()

    if slot in ("alert", "alerts"):
        # Avvia il task per l'invio delle allerte in background
        tasks.send_alerts.delay()
        return f"✅ Task di ricerca allerte avviato in background.", 202

    mapping = {
        "tech": (" Touch Tech — Morning Spark", FEEDS_TECH),
        "finance": (" Touch Finance — Lunch Byte", FEEDS_FINANCE),
        "gaming": ("⚡ Touch Gaming — Brain Snack", FEEDS_GAMING),
        "cinema": (" Touch Cinema — Insight", FEEDS_CINEMA),
        "agenzie": (" Touch Top News — Agenzie", FEEDS_AGENCIES),
    }

    if slot not in mapping:
        return "❌ Slot non valido. Usa: tech, finance, gaming, cinema, agenzie, alert", 400

    brand_name, feeds = mapping[slot]
    
    # Invia un messaggio di notifica immediato e avvia il task in background
    tasks.telegram_send(f"⚡ Forzato (via API): *{brand_name}*")
    tasks.send_article.delay(feeds, brand_name)
    
    return f"✅ Task per \"{brand_name}\" avviato in background.", 202

@app.route("/forza/ads")
def forza_ads() -> tuple[str, int]:
    tasks.send_sponsor_photo.delay()
    return "✅ Task sponsor avviato in background.", 202

@app.route("/ping_telegram")
def ping_telegram() -> tuple[str, int]:
    tasks.telegram_send(" TouchBot API attiva e funzionante.")
    return "✅ Ping inviato.", 200

# La rotta /kick non è più necessaria con Celery, ma la lasciamo per compatibilità
@app.route("/kick")
def kick() -> str:
    return "✅ L'architettura Celery non richiede più kick manuali. Lo scheduler è gestito da Celery Beat."

# ================== AVVIO SERVER ==================

if __name__ == "__main__":
    # Questo permette di avviare il server API per il debug locale
    # Per la produzione, si userà un server WSGI come Gunicorn
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
