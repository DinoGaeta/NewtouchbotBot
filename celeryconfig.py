from __future__ import annotations
from celery.schedules import crontab

# ================== CONFIGURAZIONE CELERY BEAT ==================
# Questo file definisce i task periodici (lo "scheduler")

# Fuso orario per la programmazione
beat_timezone = "Europe/Rome"

beat_schedule = {
    # Esegue il task di reset giornaliero ogni giorno a mezzanotte e un minuto
    "reset-daily": {
        "task": "newtouchbot.tasks.reset_daily_tasks",
        "schedule": crontab(hour=0, minute=1),
    },
    
    # Esegue il controllo delle allerte ogni 5 minuti
    "check-alerts-every-5-minutes": {
        "task": "newtouchbot.tasks.send_alerts",
        "schedule": crontab(minute="*/5"),
    },
    
    # Esegue il gestore delle pubblicazioni orarie ogni ora, al minuto 0
    "hourly-publication": {
        "task": "newtouchbot.tasks.hourly_publication_manager",
        "schedule": crontab(minute=0, hour="7-22"), # Esegue dalle 7 alle 22
    },
}
