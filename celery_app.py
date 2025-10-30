from __future__ import annotations
import os
from celery import Celery
from dotenv import load_dotenv

# Carica le variabili d'ambiente da .env
load_dotenv()

# Recupera l'URL di Redis dalle variabili d'ambiente
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

# Crea l'istanza dell'applicazione Celery
# Il primo argomento è il nome del modulo corrente.
# Il broker è il nostro Redis, che fa da intermediario per i messaggi dei task.
# Il backend è anch'esso Redis, usato per memorizzare i risultati dei task.
app = Celery(
    "newtouchbot",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["newtouchbot.tasks"]  # Specifica dove trovare i nostri task
)

# Carica la configurazione dal modulo celeryconfig (per Celery Beat)
app.config_from_object("newtouchbot.celeryconfig")

# Opzionale: configurazione aggiuntiva di Celery
app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Europe/Rome",
    enable_utc=True,
)

if __name__ == "__main__":
    app.start()
