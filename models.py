from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Site(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    url = db.Column(db.String(255), nullable=False)
    password = db.Column(db.String(255))  # Optional
    method = db.Column(db.String(10), default='GET')
    interval_min = db.Column(db.Integer, default=30)
    interval_max = db.Column(db.Integer, default=60)
    active = db.Column(db.Boolean, default=True)
    fails = db.Column(db.Integer, default=0)
    last_ping = db.Column(db.DateTime)
    next_ping = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"<Site {self.url}>"