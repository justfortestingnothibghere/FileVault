import os
import random
from datetime import datetime, timedelta
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, IntegerField
from wtforms.validators import DataRequired, URL, NumberRange, Optional
from models import db, Site
from scheduler import ping_site
from apscheduler.schedulers.background import BackgroundScheduler

# ======================
# Flask App Setup
# ======================
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'change-me-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

# Background Scheduler
scheduler = BackgroundScheduler()
scheduler.start()

# ======================
# Forms
# ======================
class SiteForm(FlaskForm):
    url = StringField('Website URL', validators=[DataRequired(), URL()])
    password = PasswordField('Password (Optional)', validators=[Optional()])
    method = SelectField('Method', choices=[('GET', 'GET'), ('POST', 'POST'), ('HEAD', 'HEAD')], default='GET')
    interval_min = IntegerField('Min Interval (sec)', validators=[DataRequired(), NumberRange(5, 600)], default=30)
    interval_max = IntegerField('Max Interval (sec)', validators=[DataRequired(), NumberRange(5, 600)], default=60)


# ======================
# Routes
# ======================

@app.route('/', methods=['GET', 'POST'])
def add_site():
    form = SiteForm()
    if form.validate_on_submit():
        url = form.url.data.strip().rstrip('/')
        existing = Site.query.filter_by(url=url).first()
        if existing:
            flash(f'Site already exists: {url}', 'warning')
            return redirect(url_for('add_site'))

        site = Site(
            url=url,
            password=form.password.data,
            method=form.method.data,
            interval_min=form.interval_min.data,
            interval_max=form.interval_max.data,
            active=True
        )
        db.session.add(site)
        db.session.commit()

        # Schedule first ping
        delay = random.randint(site.interval_min, site.interval_max)
        run_at = datetime.utcnow() + timedelta(seconds=delay)
        site.next_ping = run_at
        db.session.commit()
        scheduler.add_job(
            ping_site,
            'date',
            run_date=run_at,
            args=[site.id],
            id=f"ping_{site.id}"
        )

        flash(f'KeepAlive started: {url}', 'success')
        return redirect(url_for('dashboard'))

    return render_template('index.html', form=form)


@app.route('/dashboard')
def dashboard():
    sites = Site.query.order_by(Site.created_at.desc()).all()
    return render_template('dashboard.html', sites=sites)


@app.route('/action/<int:site_id>/<action>')
def site_action(site_id, action):
    site = Site.query.get_or_404(site_id)

    if action == 'pause':
        site.active = False
        if scheduler.get_job(f"ping_{site.id}"):
            scheduler.remove_job(f"ping_{site.id}")
        flash(f'Paused: {site.url}', 'warning')

    elif action == 'resume':
        site.active = True
        site.fails = 0
        delay = random.randint(site.interval_min, site.interval_max)
        run_at = datetime.utcnow() + timedelta(seconds=delay)
        site.next_ping = run_at
        db.session.commit()
        scheduler.add_job(
            ping_site,
            'date',
            run_date=run_at,
            args=[site.id],
            id=f"ping_{site.id}"
        )
        flash(f'Resumed: {site.url}', 'success')

    elif action == 'redeploy':
        try:
            import requests
            requests.get(site.url, timeout=5)
            flash(f'Redeploy signal sent to {site.url}', 'info')
        except:
            flash(f'Could not reach {site.url}', 'danger')

    elif action == 'delete':
        if scheduler.get_job(f"ping_{site.id}"):
            scheduler.remove_job(f"ping_{site.id}")
        db.session.delete(site)
        db.session.commit()
        flash(f'Deleted: {site.url}', 'danger')
        return redirect(url_for('dashboard'))

    db.session.commit()
    return redirect(url_for('dashboard'))


@app.route('/api/stats')
def api_stats():
    total = Site.query.count()
    active = Site.query.filter_by(active=True).count()
    failed = Site.query.filter(Site.fails > 0).count()
    return jsonify({'total': total, 'active': active, 'failed': failed})


# ======================
# Database & Demo Site
# ======================
def init_db_and_demo():
    with app.app_context():
        db.create_all()

        demo_url = "https://filevault-61ij.onrender.com"
        if not Site.query.filter_by(url=demo_url).first():
            demo = Site(
                url=demo_url,
                method='GET',
                interval_min=30,
                interval_max=90,
                active=True
            )
            db.session.add(demo)
            db.session.commit()

            delay = random.randint(30, 90)
            run_at = datetime.utcnow() + timedelta(seconds=delay)
            demo.next_ping = run_at
            db.session.commit()

            scheduler.add_job(
                ping_site,
                'date',
                run_date=run_at,
                args=[demo.id],
                id=f"ping_{demo.id}"
            )
            print(f"[DEMO] Scheduled for {demo_url}")


# ======================
# Run App
# ======================
if __name__ == '__main__':
    init_db_and_demo()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
