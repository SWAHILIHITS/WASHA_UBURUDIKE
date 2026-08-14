import os
import random
from datetime import datetime, timedelta
from flask import Flask, render_template_string, request, redirect, session, url_for
from pymongo import MongoClient

app = Flask(__name__)

# --- ENVIRONMENT VARIABLES (Read from Fly.io Secrets) ---
app.secret_key = os.getenv("SECRET_KEY", "fallback_secret_key_change_me")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")

# MongoDB Connection
client = MongoClient(MONGO_URI)
db = client["hotspot_db"]

vouchers_col = db["vouchers"]
sessions_col = db["sessions"]

def generate_code(length=5):
    """Generates a 5-digit numeric voucher code."""
    chars = '0123456789'
    return ''.join(random.choice(chars) for _ in range(length))


# ==========================================
# 🎨 HTML TEMPLATES
# ==========================================

PORTAL_TEMPLATE = """
<!DOCTYPE html>
<html lang="sw">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HANS WIFI - Connect</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            background-color: #f4f6f8; 
            margin: 0; padding: 20px;
            display: flex; justify-content: center; align-items: center; min-height: 90vh;
        }
        .container { width: 100%; max-width: 360px; }
        .header { text-align: center; margin-bottom: 20px; }
        .header h2 { margin: 0; color: #0052cc; font-size: 24px; }
        .header p { color: #5e6c84; font-size: 14px; margin-top: 5px; }
        .voucher-box { 
            background: white; padding: 25px 20px; border-radius: 16px; 
            border: 1px solid #e1e4e8; box-shadow: 0 4px 12px rgba(0,0,0,0.05); text-align: center; 
        }
        label { font-weight: bold; font-size: 14px; color: #172b4d; display: block; margin-bottom: 10px; }
        input[type="text"] { 
            width: 100%; padding: 14px; font-size: 24px; border: 2px solid #dfe1e6; 
            border-radius: 8px; box-sizing: border-box; margin-bottom: 15px; 
            text-align: center; letter-spacing: 6px; font-weight: bold; color: #0052cc;
        }
        button.btn-connect { 
            width: 100%; padding: 14px; background: #0052cc; color: white; 
            border: none; border-radius: 8px; font-weight: bold; font-size: 16px; cursor: pointer; 
        }
        button.btn-connect:hover { background: #0065ff; }
        .mac-info { font-size: 11px; color: #888; margin-top: 12px; }
        .error { color: #de350b; background: #ffebe6; padding: 10px; border-radius: 6px; font-size: 14px; margin-bottom: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>HANS WIFI</h2>
            <p>Ingiza namba ya vocha kuunganisha intaneti</p>
        </div>
        <div class="voucher-box">
            {% if error %}
                <div class="error">{{ error }}</div>
            {% endif %}
            <form action="/login" method="POST">
                <input type="hidden" name="mac" value="{{ mac }}">
                <label for="voucher">Namba ya Vocha (Digits 5)</label>
                <input 
                    type="text" 
                    id="voucher" 
                    name="voucher" 
                    maxlength="5" 
                    pattern="\d{5}" 
                    placeholder="12345" 
                    inputmode="numeric"
                    required 
                    autofocus
                >
                <button type="submit" class="btn-connect">CONNECT INTERNET</button>
            </form>
            <div class="mac-info">Device MAC: {{ mac }}</div>
        </div>
    </div>
</body>
</html>
"""

ADMIN_TEMPLATE = """
<!DOCTYPE html>
<html lang="sw">
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HANS WIFI - Admin Dashboard</title>
    <style>
        :root { --primary: #0052cc; --bg: #f4f6f8; --card-bg: #ffffff; --text: #172b4d; --subtext: #5e6c84; --border: #e1e4e8; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; background: var(--bg); color: var(--text); margin: 0; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; }
        .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
        .top-bar h1 { margin: 0; font-size: 22px; color: var(--primary); }
        .btn-logout { background: #ff5630; color: white; padding: 8px 16px; border-radius: 6px; text-decoration: none; font-weight: bold; font-size: 13px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 25px; }
        .stat-card { background: var(--card-bg); padding: 18px; border-radius: 12px; border: 1px solid var(--border); box-shadow: 0 2px 6px rgba(0,0,0,0.03); }
        .stat-card .label { font-size: 12px; color: var(--subtext); font-weight: bold; text-transform: uppercase; }
        .stat-card .value { font-size: 24px; font-weight: 800; color: var(--primary); margin-top: 6px; }
        .card { background: var(--card-bg); border-radius: 12px; border: 1px solid var(--border); padding: 20px; margin-bottom: 25px; }
        .card h3 { margin-top: 0; font-size: 16px; border-bottom: 1px solid var(--border); padding-bottom: 10px; }
        .form-group { display: flex; gap: 10px; flex-wrap: wrap; margin-bottom: 10px; }
        .form-group div { flex: 1; min-width: 140px; }
        label { font-size: 12px; font-weight: bold; color: var(--subtext); display: block; margin-bottom: 4px; }
        input[type="number"] { width: 100%; padding: 10px; border: 1px solid var(--border); border-radius: 6px; box-sizing: border-box; }
        .btn-primary { background: var(--primary); color: white; padding: 12px 20px; border: none; border-radius: 8px; font-weight: bold; cursor: pointer; width: 100%; margin-top: 10px; }
        table { width: 100%; border-collapse: collapse; margin-top: 10px; font-size: 13px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid var(--border); }
        th { background: #fafbfc; color: var(--subtext); font-weight: 600; }
        .code-badge { background: #ebecf0; padding: 4px 8px; border-radius: 4px; font-weight: bold; letter-spacing: 2px; }
        .badge-active { background: #e3fcef; color: #006644; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }
        .badge-used { background: #ffebe6; color: #bf2600; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }
    </style>
</head>
<body>
    <div class="container">
        <div class="top-bar">
            <h1>HANS WIFI Admin Panel</h1>
            <a href="/admin/logout" class="btn-logout">Logout</a>
        </div>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">Total Revenue</div>
                <div class="value">TZS {{ total_revenue }}</div>
            </div>
            <div class="stat-card">
                <div class="label">Online Devices (MACs)</div>
                <div class="value">{{ active_sessions_count }}</div>
            </div>
            <div class="stat-card">
                <div class="label">Active Vouchers</div>
                <div class="value">{{ active_vouchers_count }}</div>
            </div>
            <div class="stat-card">
                <div class="label">Used Vouchers</div>
                <div class="value">{{ used_vouchers_count }}</div>
            </div>
        </div>
        <div class="card">
            <h3>🖨️ Generate 5-Digit Vouchers</h3>
            <form action="/admin/generate" method="POST">
                <div class="form-group">
                    <div>
                        <label>Quantity</label>
                        <input type="number" name="quantity" value="8" min="1" required>
                    </div>
                    <div>
                        <label>Duration (Minutes)</label>
                        <input type="number" name="duration" value="360" required>
                    </div>
                    <div>
                        <label>Price per Voucher (TZS)</label>
                        <input type="number" name="price" value="500" required>
                    </div>
                </div>
                <button type="submit" class="btn-primary">Generate & Prepare Printable Sheet</button>
            </form>
        </div>
        <div class="card">
            <h3>📡 Connected Devices (Active MAC Sessions)</h3>
            <table>
                <thead>
                    <tr><th>MAC Address (_id)</th><th>Voucher Code</th><th>Activated Time</th><th>Expire Date</th></tr>
                </thead>
                <tbody>
                    {% for s in active_sessions %}
                    <tr>
                        <td><b>{{ s._id }}</b></td>
                        <td><span class="code-badge">{{ s.code }}</span></td>
                        <td>{{ s.used_time.strftime('%Y-%m-%d %H:%M') if s.used_time else 'N/A' }}</td>
                        <td><span class="badge-active">{{ s.expire_date.strftime('%Y-%m-%d %H:%M') if s.expire_date else 'N/A' }}</span></td>
                    </tr>
                    {% else %}
                    <tr><td colspan="4" style="text-align: center; color: var(--subtext);">No devices currently online.</td></tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        <div class="card">
            <h3>🎟️ Recent Voucher Inventory</h3>
            <table>
                <thead>
                    <tr><th>5-Digit Code</th><th>Duration</th><th>Price</th><th>Status</th><th>Used By MAC</th></tr>
                </thead>
                <tbody>
                    {% for v in vouchers %}
                    <tr>
                        <td><span class="code-badge">{{ v.code }}</span></td>
                        <td>{{ v.duration_minutes }} mins</td>
                        <td>TZS {{ v.price }}</td>
                        <td>
                            {% if v.status == 'ACTIVE' %}
                                <span class="badge-active">ACTIVE</span>
                            {% else %}
                                <span class="badge-used">USED</span>
                            {% endif %}
                        </td>
                        <td>{{ v.used_by_mac if v.used_by_mac else '-' }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

ADMIN_LOGIN_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login - HANS WIFI</title>
    <style>
        body { font-family: sans-serif; background: #f4f6f8; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }
        .card { background: white; padding: 30px; border-radius: 12px; border: 1px solid #e1e4e8; width: 280px; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
        input[type="password"] { width: 100%; padding: 12px; margin: 15px 0; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; text-align: center; font-size: 16px; }
        button { width: 100%; padding: 12px; background: #0052cc; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; }
        .error { color: red; font-size: 13px; }
    </style>
</head>
<body>
    <div class="card">
        <h3>HANS WIFI Admin</h3>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form action="/admin/login" method="POST">
            <input type="password" name="password" placeholder="Enter Admin Password" required autofocus>
            <button type="submit">LOGIN</button>
        </form>
    </div>
</body>
</html>
"""

PRINT_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Print Vouchers - HANS WIFI</title>
    <style>
        body { font-family: sans-serif; padding: 20px; background: #f0f0f0; }
        .no-print { margin-bottom: 20px; }
        .voucher-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; background: white; padding: 20px; }
        .card { border: 2px dashed #333; border-radius: 8px; padding: 12px; text-align: center; background: #fff; }
        .card h4 { margin: 0 0 5px 0; font-size: 13px; text-transform: uppercase; }
        .card .code { font-size: 26px; font-weight: bold; letter-spacing: 4px; background: #f4f6f8; padding: 6px; margin: 6px 0; border-radius: 4px; }
        .card .details { font-size: 11px; color: #555; }
        @media print { .no-print { display: none; } body { background: white; padding: 0; } .voucher-grid { padding: 0; } }
    </style>
</head>
<body>
    <div class="no-print">
        <button onclick="window.print()" style="padding: 10px 20px; font-size: 16px; cursor: pointer;">🖨️ Print Voucher Sheet</button>
        <a href="/admin" style="margin-left: 15px;">Back to Admin</a>
    </div>
    <div class="voucher-grid">
        {% for v in vouchers %}
        <div class="card">
            <h4>HANS WIFI PASS</h4>
            <div class="code">{{ v.code }}</div>
            <div class="details">Muda: <b>{{ v.duration_minutes }} Mins</b> | Bei: <b>TZS {{ v.price }}</b></div>
        </div>
        {% endfor %}
    </div>
</body>
</html>
"""

# ==========================================
# 🚀 ROUTES
# ==========================================

@app.route('/')
def home():
    mac_address = request.args.get('mac', 'DEMO:MAC:00:11:22').upper()
    return render_template_string(PORTAL_TEMPLATE, mac=mac_address)

@app.route('/login', methods=['POST'])
def login():
    code = request.form.get('voucher', '').strip()
    mac_address = request.form.get('mac', '').strip().upper()
    
    voucher = vouchers_col.find_one({"code": code, "status": "ACTIVE"})

    if not voucher:
        return render_template_string(PORTAL_TEMPLATE, mac=mac_address, error="Vocha hii siyo sahihi au ishatumika.")

    now = datetime.now()
    duration_minutes = voucher['duration_minutes']
    expire_date = now + timedelta(minutes=duration_minutes)

    session_data = {
        "_id": mac_address,
        "code": code,
        "used_time": now,
        "expire_date": expire_date,
        "duration_minutes": duration_minutes,
        "status": "ACTIVE"
    }
    sessions_col.replace_one({"_id": mac_address}, session_data, upsert=True)
    vouchers_col.update_one({"code": code}, {"$set": {"status": "USED", "used_by_mac": mac_address}})

    return f"""
    <div style="font-family: sans-serif; text-align: center; margin-top: 80px;">
        <h1 style="color: #36b37e; font-size: 48px;">✅</h1>
        <h2>IMEFANIKIWA!</h2>
        <p>Device (<b>{mac_address}</b>) imeunganishwa na intaneti.</p>
        <p>Muda wa kuisha: <b>{expire_date.strftime('%Y-%m-%d %H:%M')}</b></p>
    </div>
    """

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect('/admin')
        return render_template_string(ADMIN_LOGIN_TEMPLATE, error="Incorrect Password")
    return render_template_string(ADMIN_LOGIN_TEMPLATE)

@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect('/admin/login')

@app.route('/admin')
def admin_dashboard():
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')

    now = datetime.now()
    all_vouchers = list(vouchers_col.find().sort("_id", -1).limit(50))
    active_sessions = list(sessions_col.find({"expire_date": {"$gt": now}}))

    active_vouchers_count = vouchers_col.count_documents({"status": "ACTIVE"})
    used_vouchers_count = vouchers_col.count_documents({"status": "USED"})
    active_sessions_count = len(active_sessions)

    revenue_pipeline = [
        {"$match": {"status": "USED"}},
        {"$group": {"_id": None, "total": {"$sum": "$price"}}}
    ]
    revenue_result = list(vouchers_col.aggregate(revenue_pipeline))
    total_revenue = revenue_result[0]['total'] if revenue_result else 0.0

    return render_template_string(
        ADMIN_TEMPLATE,
        vouchers=all_vouchers,
        active_sessions=active_sessions,
        active_vouchers_count=active_vouchers_count,
        used_vouchers_count=used_vouchers_count,
        active_sessions_count=active_sessions_count,
        total_revenue=f"{total_revenue:,.0f}"
    )

@app.route('/admin/generate', methods=['POST'])
def generate():
    if not session.get('admin_logged_in'):
        return redirect('/admin/login')

    quantity = int(request.form.get('quantity'))
    duration = int(request.form.get('duration'))
    price = float(request.form.get('price'))

    new_vouchers = []
    for _ in range(quantity):
        while True:
            code = generate_code(5)
            if not vouchers_col.find_one({"code": code}):
                doc = {
                    "code": code,
                    "duration_minutes": duration,
                    "price": price,
                    "status": "ACTIVE",
                    "created_at": datetime.now()
                }
                vouchers_col.insert_one(doc)
                new_vouchers.append(doc)
                break

    return render_template_string(PRINT_TEMPLATE, vouchers=new_vouchers)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)
