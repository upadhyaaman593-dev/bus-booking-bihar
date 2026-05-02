from flask import Flask, render_template, request, redirect, url_for, session
import os
import psycopg2
from psycopg2.extras import RealDictCursor

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'aman_bihar_final_v5')
ADMIN_PASS = "ADMIN@2026"

def get_db():
    DATABASE_URL = os.environ.get('DATABASE_URL')
    return psycopg2.connect(DATABASE_URL, sslmode='require')

@app.route('/')
def index():
    return render_template('index.html', search_done=False)

@app.route('/search', methods=['POST'])
def search():
    source, dest, travel_date = request.form.get('source'), request.form.get('destination'), request.form.get('travel_date')
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
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT * FROM buses WHERE id = %s", (bus_id,))
    bus = cur.fetchone()
    cur.execute("SELECT seat_no FROM bookings WHERE bus_id = %s", (bus_id,))
    booked = [r['seat_no'] for r in cur.fetchall()]
    cur.close()
    conn.close()
    
    # Window seats ko list format mein bhejna (Zaruri fix)
    w_list = bus['window_seats'].split(',') if bus.get('window_seats') else []
    return render_template('seats.html', bus=bus, booked_seats=booked, window_seats=w_list)

@app.route('/process_booking', methods=['POST'])
def process_booking():
    # Abhi ke liye Direct Database Entry (No Payment Gateway)
    bus_id = request.form.get('bus_id')
    seat = request.form.get('seat_no')
    name = request.form.get('p_name')
    mobile = request.form.get('p_mobile')
    
    conn = get_db()
    cur = conn.cursor()
    cur.execute("INSERT INTO bookings (bus_id, seat_no, p_name, p_mobile, payment_id, mode) VALUES (%s,%s,%s,%s,%s,%s)",
               (bus_id, seat, name, mobile, 'FREE-TRIAL', 'Confirmed'))
    conn.commit()
    cur.close()
    conn.close()
    
    return redirect(url_for('success', seat=seat))

@app.route('/success')
def success():
    return f"""
    <div style='text-align:center; padding:50px; font-family:sans-serif;'>
        <h2 style='color:green;'>🎉 Seat {request.args.get('seat')} Book Ho Gayi!</h2>
        <p>Aapka ticket confirm ho gaya hai. Driver aapse jald sampark karenge.</p>
        <a href='/' style='text-decoration:none; color:blue;'>Wapas Home par jayein</a>
    </div>
    """

# --- Footer Routes ---
@app.route('/contact')
def contact():
    return render_template('info.html', title="Contact Us", content="Email: <b>morrisaman7@gmail.com</b>")

@app.route('/terms')
def terms():
    return render_template('info.html', title="Terms", content="2 hours cancellation policy applied.")

@app.route('/refund')
def refund():
    return render_template('info.html', title="Refund", content="Refund process takes 5-7 days.")

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
