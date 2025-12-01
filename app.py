from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, IntegerField, BooleanField
from wtforms.validators import DataRequired, URL, NumberRange, Optional
from models import db, Site
from scheduler import ping_site
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timedelta
import random

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-change-in-prod'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
scheduler = BackgroundScheduler()
scheduler.start()

# Forms
class SiteForm(FlaskForm):
    url = StringField('Website URL', validators=[DataRequired(), URL()])
    password = PasswordField('Password (Optional)', validators=[Optional()])
    method = SelectField('Method', choices=[('GET', 'GET'), ('POST', 'POST'), ('HEAD', 'HEAD')], default='GET')
    interval_min = IntegerField('Min Interval (sec)', validators=[DataRequired(), NumberRange(5, 600)], default=30)
    interval_max = IntegerField('Max Interval (sec)', validators=[DataRequired(), NumberRange(5, 600)], default=60)
    active = BooleanField('Start Immediately', default=True)

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/add', methods=['GET', 'POST'])
def add_site():
    form = SiteForm()
    if form.validate_on_submit():
        site = Site(
            url=form.url.data.strip().rstrip('/'),
            password=form.password.data,
            method=form.method.data,
            interval_min=form.interval_min.data,
            interval_max=form.interval_max.data,
            active=form.active.data
        )
        db.session.add(site)
        db.session.commit()

        if site.active:
            delay = random.randint(site.interval_min, site.interval_max)
            run_at = datetime.utcnow() + timedelta(seconds=delay)
            site.next_ping = run_at
            db.session.commit()
            scheduler.add_job(ping_site, 'date', run_date=run_at, args=[site.id], id=f"ping_{site.id}")

        flash(f'KeepAlive started for {site.url}', 'success')
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
        scheduler.remove_job(f"ping_{site.id}")
        flash(f'Paused: {site.url}', 'warning')
    elif action == 'resume':
        site.active = True
        site.fails = 0
        delay = random.randint(site.interval_min, site.interval_max)
        run_at = datetime.utcnow() + timedelta(seconds=delay)
        site.next_ping = run_at
        db.session.commit()
        scheduler.add_job(ping_site, 'date', run_date=run_at, args=[site.id], id=f"ping_{site.id}")
        flash(f'Resumed: {site.url}', 'success')
    elif action == 'redeploy':
        # Simulate redeploy by hitting / (or custom endpoint)
        try:
            requests.get(site.url, timeout=5)
            flash(f'Redeploy signal sent to {site.url}', 'info')
        except:
            flash(f'Could not reach {site.url} for redeploy', 'danger')
    elif action == 'delete':
        scheduler.remove_job(f"ping_{site.id}")
        db.session.delete(site)
        db.session.commit()
        flash(f'Deleted: {site.url}', 'danger')
        return redirect(url_for('dashboard'))

    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/logs')
def logs():
    # Simple log view (you can store logs in DB later)
    return render_template('projects.html')

@app.route('/api/stats')
def api_stats():
    total = Site.query.count()
    active = Site.query.filter_by(active=True).count()
    failed = Site.query.filter(Site.fails > 0).count()
    return jsonify({'total': total, 'active': active, 'failed': failed})

# Init DB
@app.before_request
def create_tables():
    db.create_all()
    # Load demo site
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
        scheduler.add_job(ping_site, 'date', run_date=datetime.utcnow() + timedelta(seconds=delay), args=[demo.id], id=f"ping_{demo.id}")

if __name__ == '__main__':
    with app.app_context():
        create_tables()
    app.run(debug=True, host='0.0.0.0', port=5000)
