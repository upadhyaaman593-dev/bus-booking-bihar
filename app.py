from flask import Flask, render_template, request, redirect, url_for, session
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from instamojo_wrapper import Instamojo

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'bihar_bus_2026_secret')
ADMIN_PASS = "ADMIN@2026"

# Instamojo Setup (Test Mode)
API_KEY = os.environ.get('INSTAMOJO_API_KEY', 'test_f98...') 
AUTH_TOKEN = os.environ.get('INSTAMOJO_AUTH_TOKEN', 'test_87a...')
api = Instamojo(api_key=API_KEY, auth_token=AUTH_TOKEN, endpoint='https://test.instamojo.com/api/1.1/')

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
    travel_date = request.form.get('travel_date')
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("""SELECT * FROM buses 
                   WHERE route_from ILIKE %s AND route_to ILIKE %s 
                   AND dep_date = %s AND is_online = 1""", 
                ('%'+source+'%', '%'+dest+'%', travel_date))
    results = cur.fetchall()
    cur.close()
    conn.close()
    return render_template('index.html', results=results, search_done=True, s_date=travel_date)

@app.route('/book/<int:bus_id>')
def book_bus(bus_id):
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM buses WHERE id = %s", (bus_id,))
    bus = cur.fetchone()
    cur.close()
    conn.close()
    if not bus: return "Bus details not found!"
    return render_template('booking.html', bus=bus)

@app.route('/update_status', methods=['POST'])
def update_status():
    if 'driver_id' not in session: return redirect(url_for('driver_login'))
    new_status = int(request.form.get('status'))
    conn = get_db()
    cur = conn.cursor()
    if new_status == 1:
        new_date = request.form.get('new_date')
        new_time = request.form.get('new_time')
        cur.execute("UPDATE buses SET is_online = %s, dep_date = %s, time = %s WHERE id = %s",
                   (new_status, new_date, new_time, session['driver_id']))
    else:
        cur.execute("UPDATE buses SET is_online = %s WHERE id = %s", (new_status, session['driver_id']))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('driver_dashboard'))

# --- NAYA ROUTE: Driver Offline Booking ---
@app.route('/driver_offline_book', methods=['POST'])
def driver_offline_book():
    if 'driver_id' not in session: return redirect(url_for('driver_login'))
    bus_id = session['driver_id']
    seat = request.form.get('seat_no')
    name = request.form.get('p_name')
    mobile = request.form.get('p_mobile')
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO bookings (bus_id, seat_no, p_name, p_mobile, payment_id, mode) VALUES (%s,%s,%s,%s,%s,%s)",
               (bus_id, seat, name, mobile, 'OFFLINE-BY-DRIVER', 'Offline'))
    conn.commit()
    cur.close()
    conn.close()
    return redirect(url_for('driver_dashboard'))

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

@app.route('/process_booking', methods=['POST'])
def process_booking():
    bus_id = request.form.get('bus_id')
    seat = request.form.get('seat_no')
    name = request.form.get('p_name')
    mobile = request.form.get('p_mobile')
    fare = request.form.get('fare')
    try:
        response = api.payment_request_create(
            amount=fare,
            purpose=f"Ticket {seat}",
            buyer_name=name,
            phone=mobile,
            redirect_url=url_for('payment_status', bus_id=bus_id, seat=seat, name=name, mobile=mobile, _external=True)
        )
        return redirect(response['payment_request']['longurl'])
    except Exception as e:
        return f"Payment Error: {str(e)}"

@app.route('/payment_status')
def payment_status():
    pay_req_id = request.args.get('payment_request_id')
    res = api.payment_request_status(pay_req_id)
    if res['payment_request']['status'] == 'Completed':
        conn = get_db()
        cur = conn.cursor()
        cur.execute("INSERT INTO bookings (bus_id, seat_no, p_name, p_mobile, payment_id, mode) VALUES (%s,%s,%s,%s,%s,%s)",
                   (request.args.get('bus_id'), request.args.get('seat'), request.args.get('name'), request.args.get('mobile'), request.args.get('payment_id'), 'Online'))
        conn.commit()
        cur.close()
        conn.close()
        return redirect(url_for('success', id=request.args.get('payment_id'), seat=request.args.get('seat')))
    return "Payment Failed!"

@app.route('/success')
def success():
    return render_template('success.html', payment_id=request.args.get('id'), seat=request.args.get('seat'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
    
