from flask import Flask, render_template, request, redirect, url_for, session
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'bihar_bus_2026_secret')
ADMIN_PASS = "ADMIN@2026"

def get_db():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    conn = psycopg2.connect(DATABASE_URL, sslmode='require')
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute('''CREATE TABLE IF NOT EXISTS buses 
                 (id SERIAL PRIMARY KEY, driver_name TEXT, driver_phone TEXT, 
                  password TEXT, bus_name TEXT, route_from TEXT, route_to TEXT, 
                  dep_date TEXT, arr_date TEXT, time TEXT, fare INTEGER,
                  lower_count INTEGER DEFAULT 20, upper_count INTEGER DEFAULT 20,
                  window_seats TEXT DEFAULT '', is_online INTEGER DEFAULT 1)''')
    
    cur.execute('''CREATE TABLE IF NOT EXISTS bookings 
                 (id SERIAL PRIMARY KEY, bus_id INTEGER, seat_no TEXT, 
                  p_name TEXT, p_mobile TEXT, payment_id TEXT, mode TEXT)''')
    conn.commit()
    cur.close()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html', search_done=False)

@app.route('/search', methods=['POST'])
def search():
    source = request.form.get('source', '').strip()
    dest = request.form.get('destination', '').strip()
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM buses WHERE route_from ILIKE %s AND route_to ILIKE %s AND is_online = 1", 
                ('%'+source+'%', '%'+dest+'%'))
    results = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', results=results, search_done=True)

@app.route('/toggle_status')
def toggle_status():
    if 'driver_id' not in session: return redirect(url_for('driver_login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT is_online FROM buses WHERE id = %s", (session['driver_id'],))
    driver = cur.fetchone()
    new_status = 0 if driver['is_online'] == 1 else 1
    cur.execute("UPDATE buses SET is_online = %s WHERE id = %s", (new_status, session['driver_id']))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('driver_dashboard'))

@app.route('/driver_reg', methods=['GET', 'POST'])
def driver_reg():
    if request.method == 'POST':
        if request.form.get('admin_secret') != ADMIN_PASS: return "Galat Admin Code!"
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''INSERT INTO buses (driver_name, driver_phone, password, bus_name, route_from, route_to,
                      dep_date, arr_date, time, fare, window_seats) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''',
                   (request.form.get('d_name'), request.form.get('d_phone'), request.form.get('d_pass'),
                    request.form.get('b_name'), request.form.get('from'), request.form.get('to'),
                    request.form.get('d_date'), request.form.get('d_date'), request.form.get('time'),
                    request.form.get('fare', 0), request.form.get('window_seats', '')))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('driver_login'))
    return render_template('driver_reg.html')

@app.route('/driver_login', methods=['GET', 'POST'])
def driver_login():
    if request.method == 'POST':
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM buses WHERE driver_phone = %s AND password = %s",
                            (request.form.get('phone'), request.form.get('password')))
        driver = cur.fetchone()
        cur.close()
        conn.close()
        if driver:
            session['driver_id'] = driver['id']
            return redirect(url_for('driver_dashboard'))
        return "Invalid Login!"
    return render_template('driver_login.html')

@app.route('/book/<int:bus_id>')
def book_seat(bus_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM buses WHERE id = %s", (bus_id,))
    bus = cur.fetchone()
    cur.execute("SELECT seat_no FROM bookings WHERE bus_id = %s", (bus_id,))
    booked = [row['seat_no'] for row in cur.fetchall()]
    cur.close()
    conn.close()
    windows = bus['window_seats'].split(',') if bus['window_seats'] else []
    return render_template('seats.html', bus=bus, booked_seats=booked, windows=windows)

@app.route('/process_booking', methods=['POST'])
def process_booking():
    bus_id = request.form.get('bus_id')
    seat = request.form.get('seat_no')
    name = request.form.get('p_name')
    mobile = request.form.get('p_mobile')
    pay_id = request.form.get('pay_id', 'OFFLINE')
    mode = request.form.get('mode', 'Online')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO bookings (bus_id, seat_no, p_name, p_mobile, payment_id, mode) VALUES (%s,%s,%s,%s,%s,%s)",
               (bus_id, seat, name, mobile, pay_id, mode))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('success', id=pay_id, seat=seat))

@app.route('/success')
def success():
    return render_template('success.html', payment_id=request.args.get('id'), seat=request.args.get('seat'))

@app.route('/dashboard')
def driver_dashboard():
    if 'driver_id' not in session: return redirect(url_for('driver_login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM buses WHERE id = %s", (session['driver_id'],))
    driver = cur.fetchone()
    cur.execute("SELECT * FROM bookings WHERE bus_id = %s", (session['driver_id'],))
    passengers = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('dashboard.html', driver=driver, passengers=passengers)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

    
