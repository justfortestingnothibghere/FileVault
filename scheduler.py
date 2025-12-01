import random
import requests
from datetime import datetime, timedelta
from models import db, Site

def ping_site(site_id):
    site = Site.query.get(site_id)
    if not site or not site.active:
        return

    headers = {'Cache-Control': 'no-cache', 'User-Agent': 'KeepAlive-TeamDev'}
    data = None
    if site.password and site.method == 'POST':
        data = {'password': site.password}

    try:
        response = requests.request(
            site.method, site.url, headers=headers, data=data, timeout=10
        )
        site.fails = 0
        site.last_ping = datetime.utcnow()
        print(f"[SUCCESS] {site.url} -> {response.status_code}")
    except Exception as e:
        site.fails += 1
        print(f"[FAILED] {site.url} -> {e}")
        if site.fails >= 5:
            site.active = False
            print(f"[AUTO-PAUSED] {site.url} after 5 fails")

    db.session.commit()

    # Schedule next ping
    if site.active:
        delay = random.randint(site.interval_min, site.interval_max)
        site.next_ping = datetime.utcnow() + timedelta(seconds=delay)
        db.session.commit()
        from app import scheduler
        scheduler.add_job(
            ping_site,
            'date',
            run_date=site.next_ping,
            args=[site.id],
            id=f"ping_{site.id}",
            replace_existing=True
        )