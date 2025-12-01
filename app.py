from flask import Flask, render_template, request, redirect, url_for, session, flash
import psycopg2
import hashlib
import os
from urllib.parse import urlparse
import socket
import requests
import time

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'pingr-pro-999-secret'

# === DATABASE CONNECT ===
def get_db():
    return psycopg2.connect(os.getenv('DATABASE_URL', 'postgresql://dataforgecloud_user:jfVwPL4m4rPPjw71nWQ95bSxQvVD6vsP@dpg-d43tb6ripnbc73caq2vg-a.oregon-postgres.render.com/dataforgecloud'))

# === HASH PASSWORD ===
def hash_password(pwd):
    return hashlib.sha256(pwd.encode()).hexdigest()

# === HOME ===
@app.route('/')
def home():
    return redirect('/login')

# === LOGIN ===
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        if not email or not password:
            flash('Missing email or password!')
            return render_template('login.html')
        
        pwd = hash_password(password)
        
        db = get_db()
        cur = db.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s AND password = %s", (email, pwd))
        user = cur.fetchone()
        db.close()
        
        if user:
            session['user_id'] = user[0]
            session['username'] = user[1]
            session['role'] = user[7]
            return redirect('/dashboard')
        flash('Wrong email or password!')
    return render_template('login.html')

# === SIGNUP ===
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not all([username, email, password]):
            flash('All fields required!')
            return render_template('signup.html')
        
        pwd = hash_password(password)
        
        db = get_db()
        cur = db.cursor()
        try:
            cur.execute("INSERT INTO users (username, email, password) VALUES (%s, %s, %s)",
                        (username, email, pwd))
            db.commit()
            flash('Account created! Login now.')
            return redirect('/login')
        except Exception as e:
            db.rollback()
            flash('Email or username already taken!')
        finally:
            db.close()
    return render_template('signup.html')
    
# === DASHBOARD ===
@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/login')
    
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT * FROM projects WHERE user_id = %s", (session['user_id'],))
    projects = cur.fetchall()
    db.close()
    
    html = open('dashboard.html').read()
    project_list = ""
    for p in projects:
        status = ping_url(p[3], p[4])  # url, type
        color = "green" if "OK" in status else "red"
        project_list += f"""
        <div class="project">
            <h3>{p[2]}</h3>
            <p>{p[3]} ({p[4]})</p>
            <p style="color:{color}; font-weight:bold;">{status}</p>
        </div>
        """
    return html.replace('<!-- PROJECTS -->', project_list)

# === ADD PROJECT ===
@app.route('/add', methods=['POST'])
def add_project():
    if 'user_id' not in session:
        return redirect('/login')
    
    name = request.form['name']
    url = request.form['url']
    ptype = request.form['type']
    
    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO projects (user_id, name, url, type) VALUES (%s, %s, %s, %s)",
                (session['user_id'], name, url, ptype))
    db.commit()
    db.close()
    return redirect('/dashboard')

# === PING FUNCTION ===
def ping_url(url, ptype):
    try:
        if ptype == 'http':
            start = time.time()
            r = requests.get(url, timeout=5)
            ms = int((time.time() - start) * 1000)
            return f"OK {r.status_code} ({ms}ms)"
        
        elif ptype == 'icmp':
            host = urlparse(url if '://' in url else 'http://'+url).hostname
            import subprocess
            result = subprocess.run(['ping', '-c', '1', host], capture_output=True, text=True)
            if '1 packets transmitted, 1 received' in result.stdout:
                return "ICMP OK"
            return "ICMP FAILED"
    except:
        return "DOWN"
    return "ERROR"

# === ADMIN PANEL ===
@app.route('/admin')
def admin():
    if session.get('role') != 'admin':
        return "ACCESS DENIED"
    
    db = get_db()
    cur = db.cursor()
    cur.execute("SELECT id, username, email, is_premium, is_banned FROM users")
    users = cur.fetchall()
    db.close()
    
    html = open('admin.html').read()
    user_list = ""
    for u in users:
        ban_btn = f"<a href='/ban/{u[0]}'>Ban</a>" if not u[4] else "BANNED"
        user_list += f"<tr><td>{u[1]}</td><td>{u[2]}</td><td>{ban_btn}</td><td><a href='/warn/{u[0]}'>Warn</a></td></tr>"
    
    return html.replace('<!-- USERS -->', user_list)

@app.route('/ban/<int:uid>')
def ban_user(uid):
    if session.get('role') == 'admin':
        db = get_db()
        cur = db.cursor()
        cur.execute("UPDATE users SET is_banned = TRUE WHERE id = %s", (uid,))
        db.commit()
        db.close()
    return redirect('/admin')

# === RUN ===
if __name__ == '__main__':
    # Create default admin
    try:
        db = get_db()
        cur = db.cursor()
        cur.execute("INSERT INTO users (username, email, password, role) VALUES (%s, %s, %s, %s)",
                    ('admin', 'admin@pingr.pro', hash_password('admin123'), 'admin'))
        db.commit()
        db.close()
        print("Admin created: admin@pingr.pro / admin123")
    except:
        pass
    
    app.run(host='0.0.0.0', port=5000, debug=True)
