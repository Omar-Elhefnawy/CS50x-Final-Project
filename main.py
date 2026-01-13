import serial
import serial.tools.list_ports
from flask import Flask, render_template, jsonify, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
import datetime
from threading import Thread, Lock
import time
import sys
import signal

# App initialization
app = Flask(__name__)
app.secret_key = 'cs50-smart-desk-2025'
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

ser_lock = Lock()
ser = None
current_session_start = None
session_lock = Lock()
work_sessions = []  # In-memory (start_time, end_time)

# Prefer current logged-in user if available; fall back to None (or a default)
user_id = None
try:
    # current_user is a proxy; in a background thread it will usually be anonymous
    if getattr(current_user, "is_authenticated", False):
        user_id = current_user.id
except Exception:
    user_id = None

# User class
class User(UserMixin):
    def __init__(self, id, username):
        self.id = id
        self.username = username

@login_manager.user_loader
def load_user(user_id):
    try:
        conn = sqlite3.connect('data.db')
        c = conn.cursor()
        c.execute('SELECT id, username FROM users WHERE id = ?', (user_id,))
        user = c.fetchone()
        conn.close()
        if user:
            return User(user[0], user[1])
        print("User loader: No user found for ID", user_id)
        return None
    except Exception as e:
        print(f"User loader error: {e}")
        return None

# ROUTES
@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        try:
            conn = sqlite3.connect('data.db')
            c = conn.cursor()
            c.execute('SELECT id FROM users WHERE username = ?', (username,))
            if c.fetchone():
                conn.close()
                flash('Username already exists. Choose another.')
                return render_template('register.html')
            c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                      (username, generate_password_hash(password)))
            conn.commit()
            conn.close()
            print(f"User {username} registered.")
            flash('Registration successful! Please log in.')
            return redirect(url_for('login'))
        except Exception as e:
            print(f"Register error: {e}")
            flash('Registration failed. Try again.')
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        try:
            conn = sqlite3.connect('data.db')
            c = conn.cursor()
            c.execute('SELECT id, username, password_hash FROM users WHERE username = ?', (username,))
            user_data = c.fetchone()
            conn.close()
            if user_data and check_password_hash(user_data[2], password):
                user = User(user_data[0], user_data[1])
                login_user(user)
                print(f"User {username} logged in.")
                return redirect(url_for('index'))
            flash('Invalid username or password')
        except Exception as e:
            print(f"Login error: {e}")
            flash('Login failed. Try again.')
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    print("User logged out.")
    with session_lock:
        global current_session_start
        current_session_start = None
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    with session_lock:
        sync_db_to_memory(current_user.id)
        # work_sessions now holds (id, start, end)
        total_hours = 0.0
        for _sid, start, end in work_sessions:
            if end:
                total_hours += (end - start).total_seconds() / 3600.0
        return render_template('index.html', sessions=work_sessions, total_hours=total_hours)

@app.route('/timer')
@login_required
def timer():
    with session_lock:
        if current_session_start is None:
            print("Timer: No active session")
            return jsonify({"status": "not_working", "elapsed": 0})
        elapsed = (datetime.datetime.now() - current_session_start).total_seconds()
        print(f"Timer: Active session, elapsed {elapsed:.1f}s")
        return jsonify({"status": "working", "elapsed": elapsed})

@app.route('/debug_session', methods=['POST'])
@login_required
def debug_session():
    """Manually start/stop session for debugging"""
    action = request.form.get('action')
    with session_lock:
        global current_session_start
        if action == 'start' and current_session_start is None:
            current_session_start = datetime.datetime.now()
            print(f"Debug: Manual session started at {current_session_start}")
        elif action == 'stop' and current_session_start is not None:
            start_time = current_session_start
            end_time = datetime.datetime.now()
            # persist to DB
            try:
                conn = sqlite3.connect('data.db')
                c = conn.cursor()
                c.execute('INSERT INTO sessions (start, end, user_id) VALUES (?, ?, ?)',
                          (start_time.strftime('%Y-%m-%d %H:%M:%S'), end_time.strftime('%Y-%m-%d %H:%M:%S'), current_user.id))
                conn.commit()
                conn.close()
                print("Debug: Manual session ended and saved")
            except Exception as e:
                print(f"Debug save error: {e}")
            # refresh memory from DB so we have ids
            sync_db_to_memory(current_user.id)
            current_session_start = None
    return redirect(url_for('index'))

@app.route('/delete_session', methods=['POST'])
@login_required
def delete_session():
    """Delete a session owned by the current user."""
    session_id = request.form.get('session_id')
    if not session_id:
        flash('No session id provided.')
        return redirect(url_for('index'))
    with session_lock:
        try:
            conn = sqlite3.connect('data.db')
            c = conn.cursor()
            c.execute('SELECT user_id FROM sessions WHERE id = ?', (session_id,))
            row = c.fetchone()
            if not row:
                flash('Session not found.')
            elif row[0] != current_user.id:
                flash('Cannot delete a session you do not own.')
            else:
                c.execute('DELETE FROM sessions WHERE id = ?', (session_id,))
                conn.commit()
                flash('Session deleted.')
            conn.close()
        except Exception as e:
            print(f"Delete session error: {e}")
            flash('Failed to delete session.')
    return redirect(url_for('index'))

@app.route('/daily_hours')
@login_required
def daily_hours():
    """Return last 7 days dates and total work hours per day (JSON)."""
    with session_lock:
        sync_db_to_memory(current_user.id)
        today = datetime.date.today()
        dates = []
        day_map = {}
        for days_ago in range(6, -1, -1):
            d = today - datetime.timedelta(days=days_ago)
            key = d.strftime('%Y-%m-%d')
            dates.append(key)
            day_map[key] = 0.0
        # work_sessions holds (id, start, end)
        for _sid, start, end in work_sessions:
            if not end:
                continue
            day_key = start.date().strftime('%Y-%m-%d')
            if day_key in day_map:
                day_map[day_key] += (end - start).total_seconds() / 3600.0
        hours = [round(day_map[d], 2) for d in dates]
        details = [{'date': d, 'hours': h} for d, h in zip(dates, hours)]
        return jsonify({'dates': dates, 'hours': hours, 'details': details})

print("Registered endpoints:", [rule.endpoint for rule in app.url_map.iter_rules()])

# DB initialization
def init_db():
    try:
        conn = sqlite3.connect('data.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start TEXT NOT NULL,
            end TEXT,
            user_id INTEGER,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )''')
        # reminders table removed
        c.execute('SELECT COUNT(*) FROM users WHERE username = ?', ('admin',))
        if c.fetchone()[0] == 0:
            c.execute('INSERT INTO users (username, password_hash) VALUES (?, ?)',
                      ('admin', generate_password_hash('cs50project')))
        conn.commit()
        conn.close()
        print("DB initialized.")
    except Exception as e:
        print(f"DB init error: {e}")

init_db()

def sync_db_to_memory(user_id):
    """Load user-specific data from DB to in-memory lists"""
    global work_sessions
    try:
        conn = sqlite3.connect('data.db')
        c = conn.cursor()
        # Claim any unassigned sessions for the currently logged-in user (first-login claim).
        if user_id is not None:
            try:
                c.execute('UPDATE sessions SET user_id = ? WHERE user_id IS NULL', (user_id,))
                conn.commit()
            except Exception as e:
                print(f"Claim unassigned sessions error: {e}")
        # load id,start,end so front-end can delete by id
        c.execute('SELECT id, start, end FROM sessions WHERE user_id = ? ORDER BY start DESC', (user_id,))
        sessions_data = c.fetchall()
        work_sessions = []
        for sid, start, end in sessions_data:
            start_dt = datetime.datetime.strptime(start, '%Y-%m-%d %H:%M:%S')
            end_dt = datetime.datetime.strptime(end, '%Y-%m-%d %H:%M:%S') if end else None
            work_sessions.append((sid, start_dt, end_dt))
        conn.close()
        print(f"Synced DB for user {user_id}: {len(work_sessions)} sessions")
    except Exception as e:
        print(f"Sync error: {e}")

# Serial setup
def find_arduino_port():
    print("Scanning for Arduino ports...")
    try:
        ports = serial.tools.list_ports.comports()
        if ports is None:
            print("No ports found.")
            return None
        print(f"Found {len(ports)} ports.")
        for i, port in enumerate(ports):
            vid_str = str(port.vid) if port.vid else "None"
            desc = port.description or "No description"
            print(f"Port {i+1}: {port.device} | Desc: {desc} | VID: {vid_str}")
        for port in ports:
            if (port.description and "Arduino" in port.description) or \
               (port.vid and any(hex_id in str(port.vid).lower() for hex_id in ["2341", "9025"])):
                print(f"Found Arduino on {port.device}: {port.description}")
                return port.device
        print("No Arduino found.")
        return None
    except Exception as e:
        print(f"Port find error: {e}")
        return None

def open_serial(port):
    global ser
    with ser_lock:
        for attempt in range(3):
            try:
                print(f"Attempt {attempt+1}/3 to open {port}")
                ser = serial.Serial(port, 9600, timeout=1)
                ser.flushInput()
                print(f"Opened {port}!")
                return True
            except serial.SerialException as e:
                print(f"Serial error: {e}")
                if attempt < 2:
                    time.sleep(2)
        print(f"Failed to open {port}.")
        return False

port = find_arduino_port()
if port:
    if not open_serial(port):
        print("Running in web-only mode.")
else:
    print("No Arduino port. Web-only mode.")

def read_serial():
    global current_session_start, work_sessions
    while True:
        try:
            with ser_lock:
                if ser is None or not ser.is_open:
                    print("Serial closed. Reconnecting...")
                    port = find_arduino_port()
                    if port and open_serial(port):
                        continue
                    time.sleep(5)
                    continue
                raw_data = ser.readline()
                if not raw_data:
                    continue
                try:
                    line = raw_data.decode('utf-8').strip()
                except UnicodeDecodeError:
                    print("Decode error: Invalid bytes, skipping.")
                    continue
                if line:
                    print(f"Raw serial: '{line}'")
                    user_id = 1  # Default to admin (no Flask-Login context in thread)
                    current_time = datetime.datetime.now()
                    current_time_str = current_time.strftime('%Y-%m-%d %H:%M:%S')
                    if line.startswith("PRESENCE:"):
                        try:
                            parts = line.split(",TIME:")
                            if len(parts) != 2:
                                print(f"Invalid PRESENCE format: {line}")
                                continue
                            presence = int(parts[0].split(":")[1])
                            print(f"Parsed presence: {presence}, time: {parts[1]}")
                            with session_lock:
                                if presence == 1 and current_session_start is None:
                                    # Emulate pressing the "Start Session" debug button (sensor-only).
                                    current_session_start = current_time
                                    # add a single (start, None) entry
                                    work_sessions.append((current_session_start, None))
                                    print(f"Session started at {current_time_str} (sensor)")
                                elif presence == 0 and current_session_start is not None:
                                    # Emulate pressing the "Stop Session" debug button (sensor-only).
                                    start_time = current_session_start
                                    work_sessions[-1] = (start_time, current_time)
                                    conn = sqlite3.connect('data.db')
                                    # store user_id as NULL so the web app can claim unassigned sessions later
                                    c = conn.cursor()
                                    c.execute('INSERT INTO sessions (start, end, user_id) VALUES (?, ?, ?)',
                                              (start_time.strftime('%Y-%m-%d %H:%M:%S'), current_time_str, None))
                                    conn.commit()
                                    conn.close()
                                    current_session_start = None
                                    print(f"Session ended at {current_time_str}, saved to DB (unassigned)")
                        except (ValueError, IndexError) as e:
                            print(f"PRESENCE parse error: {e}, line: {line}")
        except Exception as e:
            print(f"Serial thread error: {e}")
            time.sleep(1)

if port:
    serial_thread = Thread(target=read_serial, daemon=True)
    serial_thread.start()

def signal_handler(sig, frame):
    print("Shutting down...")
    with ser_lock:
        if ser and ser.is_open:
            ser.close()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)

if __name__ == '__main__':
    try:
        app.run(debug=True, use_reloader=False, host='127.0.0.1', port=5000)
    except KeyboardInterrupt:
        signal_handler(None, None)
    finally:
        with ser_lock:
            if ser and ser.is_open:
                ser.close()
                print("Serial closed.")