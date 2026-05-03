from flask import Flask, render_template, request, redirect, url_for, session
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'aman_bihar_bus_2026')
ADMIN_PASS = "ADMIN@2026"

# Database Connection Function
def get_db():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    return psycopg2.connect(DATABASE_URL, sslmode='require', connect_timeout=10)

# Database Table Setup
def init_db():
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''CREATE TABLE IF NOT EXISTS buses 
                     (id SERIAL PRIMARY KEY, driver_name TEXT, driver_phone TEXT, 
                      password TEXT, bus_name TEXT, route_from TEXT, route_to TEXT, 
                      dep_date TEXT, arr_date TEXT, time TEXT, fare INTEGER,
                      window_seats TEXT DEFAULT '', is_online INTEGER DEFAULT 1)''')
        cur.execute('''CREATE TABLE IF NOT EXISTS bookings 
                     (id SERIAL PRIMARY KEY, bus_id INTEGER, seat_no TEXT, 
                      p_name TEXT, p_mobile TEXT, payment_id TEXT, mode TEXT)''')
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Init DB Error: {e}")
    finally:
        if conn: conn.close()

init_db()

# --- MAIN ROUTES ---

@app.route('/')
def index():
    return render_template('index.html', search_done=False)

@app.route('/search', methods=['POST'])
def search():
    source = request.form.get('source', '').strip()
    dest = request.form.get('destination', '').strip()
    travel_date = request.form.get('travel_date')
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM buses WHERE route_from ILIKE %s AND route_to ILIKE %s AND dep_date = %s AND is_online = 1", 
                ('%'+source+'%', '%'+dest+'%', travel_date))
    results = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', results=results, search_done=True, s_date=travel_date)

@app.route('/book/<int:bus_id>')
def book_bus(bus_id):
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM buses WHERE id = %s", (bus_id,))
        bus = cur.fetchone()
        cur.execute("SELECT seat_no FROM bookings WHERE bus_id = %s", (bus_id,))
        booked_rows = cur.fetchall()
        booked_seats = [r['seat_no'] for r in booked_rows]
        cur.close()
        
        if not bus: return "Bus details not found!", 404
        
        window_list = []
        if bus.get('window_seats'):
            window_list = [s.strip() for s in bus['window_seats'].split(',')]
            
        return render_template('seats.html', bus=bus, booked_seats=booked_seats, window_seats=window_list)
    except Exception as e:
        return f"Database Error: {str(e)}", 500
    finally:
        if conn: conn.close()

@app.route('/process_booking', methods=['POST'])
def process_booking():
    bus_id = request.form.get('bus_id')
    seat = request.form.get('seat_no')
    name = request.form.get('p_name')
    mobile = request.form.get('p_mobile')
    
    if not seat: return "Please select a seat!", 400

    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO bookings (bus_id, seat_no, p_name, p_mobile, payment_id, mode) VALUES (%s,%s,%s,%s,%s,%s)",
                   (bus_id, seat, name, mobile, 'WEB-BOOK', 'Online'))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('success', seat=seat, bus_id=bus_id))
    except Exception as e:
        return f"Booking Failed: {str(e)}"

@app.route('/success')
def success():
    seat = request.args.get('seat')
    bus_id = request.args.get('bus_id')
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM buses WHERE id = %s", (bus_id,))
    bus = cur.fetchone()
    cur.close()
    conn.close()
    return render_template('success.html', seat=seat, bus=bus)

# --- FOOTER ROUTES ---

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/refund')
def refund():
    return render_template('refund.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

# --- DRIVER & DASHBOARD ROUTES ---

@app.route('/toggle_status/<int:bus_id>', methods=['GET', 'POST'])
def toggle_status(bus_id):
    if 'driver_id' not in session: return redirect(url_for('driver_login'))
    conn = get_db()
    cur = conn.cursor()
    if request.method == 'POST':
        new_date = request.form.get('dep_date')
        new_time = request.form.get('dep_time')
        cur.execute("UPDATE buses SET is_online = 1, dep_date = %s, time = %s WHERE id = %s", (new_date, new_time, bus_id))
    else:
        cur.execute("UPDATE buses SET is_online = 0 WHERE id = %s", (bus_id,))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('driver_dashboard'))

@app.route('/driver_reg', methods=['GET', 'POST'])
def driver_reg():
    if request.method == 'POST':
        if request.form.get('admin_secret') != ADMIN_PASS: return "Wrong Admin Secret!"
        conn = get_db()
        cur = conn.cursor()
        cur.execute('''INSERT INTO buses (driver_name, driver_phone, password, bus_name, route_from, route_to,
                      dep_date, arr_date, time, fare, window_seats, is_online) 
                      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, 1)''',
                   (request.form.get('d_name'), request.form.get('d_phone'), request.form.get('d_pass'),
                    request.form.get('b_name'), request.form.get('from'), request.form.get('to'),
                    request.form.get('d_date'), request.form.get('d_date'), request.form.get('time'),
                    request.form.get('fare'), request.form.get('window_seats')))
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
        return "Login Failed!"
    return render_template('driver_login.html')

@app.route('/dashboard')
def driver_dashboard():
    if 'driver_id' not in session: return redirect(url_for('driver_login'))
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM buses WHERE id = %s", (session['driver_id'],))
    driver = cur.fetchone()
    cur.execute("SELECT * FROM bookings WHERE bus_id = %s ORDER BY id DESC", (session['driver_id'],))
    passengers = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('dashboard.html', driver=driver, passengers=passengers)

@app.route('/driver_direct_book', methods=['POST'])
def driver_direct_book():
    if 'driver_id' not in session: return redirect(url_for('driver_login'))
    bus_id = session['driver_id']
    seat = request.form.get('seat')
    name = request.form.get('name')
    mobile = request.form.get('mobile')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO bookings (bus_id, seat_no, p_name, p_mobile, payment_id, mode) VALUES (%s,%s,%s,%s,%s,%s)",
               (bus_id, seat, name, mobile, 'MANUAL-DRV', 'Offline'))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('driver_dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
    
