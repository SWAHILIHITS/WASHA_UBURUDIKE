import os
import random
import secrets
import logging
from datetime import datetime, timedelta, timezone
from flask import Flask, render_template_string, request, redirect, session, Response
from pymongo import MongoClient

app = Flask(__name__)

# --- LOGGING INITIALIZATION ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("appLogger")

# --- ENVIRONMENT CONFIGURATION ---
app.secret_key = os.getenv("SECRET_KEY", secrets.token_hex(32))
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin123")
DEFAULT_GW_ADDRESS = os.getenv("DEFAULT_GW_ADDRESS", "192.168.0.46")

# Database URI (Reads from Fly.io Secret or falls back to Atlas)
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://swahilihit:swahilihit@cluster0.3nfk1.mongodb.net/myFirstDatabase?retryWrites=true&w=majority")

# --- DATABASE SETUP ---
try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client['swahilihit56']
    vouchers_col = db["vouchers"]
    sessions_col = db["sessions"]
    tokens_col = db["wifidog_tokens"]
    
    # Initialize indexes for performance and security
    vouchers_col.create_index("code", unique=True)
    tokens_col.create_index("created_at", expireAfterSeconds=600)
    sessions_col.create_index("expire_date")
    logger.info("Successfully connected to MongoDB and verified collection indexes.")
except Exception as e:
    logger.error(f"Failed to connect to MongoDB: {str(e)}")


# --- HELPER FUNCTIONS ---
def get_param(key, default=""):
    """Extract parameter from POST form or GET query string."""
    return request.form.get(key) or request.args.get(key) or default

def get_client_mac():
    """Detect client MAC address across ReyeeOS parameter keys."""
    for key in ['mac', 'usermac', 'client_mac', 'client-mac']:
        val = get_param(key)
        if val:
            return val.strip().upper()
    return f"UNKNOWN:{secrets.token_hex(4).upper()}"

def get_gateway_address():
    """Extract Access Point LAN IP. Falls back strictly to DEFAULT_GW_ADDRESS for cloud hosts."""
    for key in ['gw_address', 'gw_ip', 'gwaddress', 'router_ip']:
        val = get_param(key)
        if val and val.replace('.', '').isdigit():
            return val.strip()
    return DEFAULT_GW_ADDRESS

def generate_code(length=5):
    """Generates a 5-digit numeric voucher code."""
    return ''.join(random.choices('0123456789', k=length))


# ==========================================
# 🎨 HTML TEMPLATES (Embedded)
# ==========================================

PORTAL_TEMPLATE = """
<!DOCTYPE html>
<html lang="sw">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>HANS WIFI - Connect</title>
    <style>
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; 
            background-color: #f4f6f8; margin: 0; padding: 20px;
            display: flex; justify-content: center; align-items: center; min-height: 90vh;
        }
        .container { width: 100%; max-width: 350px; }
        .box { 
            background: white; padding: 30px 22px; border-radius: 16px; 
            border: 1px solid #e1e4e8; box-shadow: 0 4px 14px rgba(0,0,0,0.06); text-align: center; 
            box-sizing: border-box;
        }
        h2 { margin: 0; color: #0052cc; font-size: 24px; }
        p { color: #5e6c84; font-size: 14px; margin-top: 6px; margin-bottom: 20px; }
        label { font-weight: bold; font-size: 13px; color: #172b4d; display: block; margin-bottom: 8px; text-align: left; }
        input[type="text"] { 
            width: 100%; padding: 14px; font-size: 24px; border: 2px solid #dfe1e6; 
            border-radius: 8px; box-sizing: border-box; margin-bottom: 18px; 
            text-align: center; letter-spacing: 6px; font-weight: bold; color: #0052cc;
        }
        input[type="text"]:focus { border-color: #0052cc; outline: none; }
        button { 
            width: 100%; padding: 14px; background: #0052cc; color: white; 
            border: none; border-radius: 8px; font-weight: bold; font-size: 16px; cursor: pointer; 
            transition: background 0.2s;
        }
        button:hover { background: #0065ff; }
        .error { color: #de350b; background: #ffebe6; padding: 10px; border-radius: 6px; font-size: 13px; margin-bottom: 15px; }
        .mac-info { font-size: 11px; color: #888; margin-top: 15px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="box">
            <h2>HANS WIFI</h2>
            <p>Ingiza namba ya vocha kuunganisha intaneti</p>
            {% if error %}
                <div class="error">{{ error }}</div>
            {% endif %}
            <form action="/login" method="POST">
                <input type="hidden" name="mac" value="{{ mac }}">
                <input type="hidden" name="gw_address" value="{{ gw_address }}">
                <input type="hidden" name="gw_port" value="{{ gw_port }}">
                <input type="hidden" name="gw_id" value="{{ gw_id }}">
                <input type="hidden" name="userurl" value="{{ userurl }}">
                
                <label for="voucher">Namba ya Vocha (Digits 5):</label>
                <input 
                    type="text" 
                    id="voucher" 
                    name="voucher" 
                    maxlength="5" 
                    pattern="\\d{5}" 
                    placeholder="12345" 
                    inputmode="numeric"
                    required 
                    autofocus
                >
                <button type="submit">CONNECT INTERNET</button>
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
    <meta charset="UTF-8">
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
        .code-badge { background: #ebecf0; padding: 4px 8px; border-radius: 4px; font-weight: bold; letter-spacing: 2px; font-family: monospace; }
        .badge-active { background: #e3fcef; color: #006644; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }
        .badge-used { background: #ffebe6; color: #bf2600; padding: 4px 8px; border-radius: 12px; font-size: 11px; font-weight: bold; }
        .btn-revoke { color: #de350b; font-weight: bold; text-decoration: none; }
        .btn-revoke:hover { text-decoration: underline; }
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
            <form action="/admin/generate" method="POST" target="_blank">
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
                    <tr><th>MAC Address (_id)</th><th>Voucher Code</th><th>Activated Time</th><th>Expire Date</th><th>Action</th></tr>
                </thead>
                <tbody>
                    {% for s in active_sessions %}
                    <tr>
                        <td><b>{{ s._id }}</b></td>
                        <td><span class="code-badge">{{ s.code }}</span></td>
                        <td>{{ s.used_time.strftime('%Y-%m-%d %H:%M') if s.used_time else 'N/A' }}</td>
                        <td><span class="badge-active">{{ s.expire_date.strftime('%Y-%m-%d %H:%M') if s.expire_date else 'N/A' }}</span></td>
                        <td>
                            <a href="/admin/revoke/{{ s._id }}" class="btn-revoke" onclick="return confirm('Disconnect this device instantly?');">Disconnect</a>
                        </td>
                    </tr>
                    {% else %}
                    <tr><td colspan="5" style="text-align: center; color: var(--subtext);">No devices currently online.</td></tr>
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
<html lang="sw">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login - HANS WIFI</title>
    <style>
        body { font-family: sans-serif; background: #f4f6f8; display: flex; justify-content: center; align-items: center; height: 90vh; margin: 0; }
        .card { background: white; padding: 30px; border-radius: 12px; border: 1px solid #e1e4e8; width: 280px; text-align: center; box-shadow: 0 4px 10px rgba(0,0,0,0.05); }
        h3 { margin-top: 0; color: #0052cc; }
        input[type="password"] { width: 100%; padding: 12px; margin: 15px 0; border: 1px solid #ccc; border-radius: 6px; box-sizing: border-box; text-align: center; font-size: 16px; }
        button { width: 100%; padding: 12px; background: #0052cc; color: white; border: none; border-radius: 6px; font-weight: bold; cursor: pointer; }
        .error { color: red; font-size: 13px; margin-bottom: 10px; }
    </style>
</head>
<body>
    <div class="card">
        <h3>HANS WIFI Admin</h3>
        {% if error %}<div class="error">{{ error }}</div>{% endif %}
        <form action="/admin/login" method="POST">
            <input type="password" name="password" placeholder="Ingiza Nenosiri" required autofocus>
            <button type="submit">LOGIN</button>
        </form>
    </div>
</body>
</html>
"""

PRINT_TEMPLATE = """
<!DOCTYPE html>
<html lang="sw">
<head>
    <meta charset="UTF-8">
    <title>Print Vouchers - HANS WIFI</title>
    <style>
        body { font-family: sans-serif; padding: 20px; background: #f0f0f0; }
        .no-print { margin-bottom: 20px; text-align: center; }
        .voucher-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; background: white; padding: 20px; }
        .card { border: 2px dashed #333; border-radius: 8px; padding: 12px; text-align: center; background: #fff; page-break-inside: avoid; }
        .card h4 { margin: 0 0 5px 0; font-size: 13px; text-transform: uppercase; }
        .card .code { font-size: 26px; font-weight: bold; letter-spacing: 4px; background: #f4f6f8; padding: 6px; margin: 6px 0; border-radius: 4px; font-family: monospace; }
        .card .details { font-size: 11px; color: #555; }
        @media print { .no-print { display: none; } body { background: white; padding: 0; } .voucher-grid { padding: 0; } }
    </style>
</head>
<body onload="window.print()">
    <div class="no-print">
        <button onclick="window.print()" style="padding: 10px 20px; font-size: 16px; cursor: pointer; background: #0052cc; color: white; border: none; border-radius: 6px;">🖨️ Print Voucher Sheet</button>
        <a href="/admin" style="margin-left: 15px; text-decoration: none; color: #0052cc; font-weight: bold;">Back to Admin</a>
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
# 🌐 CAPTIVE PORTAL ROUTES
# ==========================================

@app.route('/')
@app.route('/portal')
@app.route('/portal/')
@app.route('/index.html')
@app.route('/login.html')
@app.route('/wifidog/portal')
@app.route('/wifidog/portal/')
@app.route('/api/wifidog/portal')
@app.route('/api/wifidog/portal/')
def captive_login_page():
    """Renders voucher entry page or auto-reconnects existing active MAC sessions."""
    mac = get_client_mac()
    gw_address = get_gateway_address()
    gw_port = get_param('gw_port', '2060')
    gw_id = get_param('gw_id', 'G1UQ6C8027360')
    userurl = get_param('url') or get_param('userurl') or 'http://www.google.com'

    logger.info(f"Portal page requested by MAC: {mac} via Gateway IP: {gw_address}")

    # --- AUTO-RECONNECT CHECK AFTER AP REBOOT ---
    now = datetime.now(timezone.utc)
    if mac and not mac.startswith("UNKNOWN"):
        try:
            active_session = sessions_col.find_one({"_id": mac, "expire_date": {"$gt": now}})
            if active_session:
                logger.info(f"Active session found for MAC: {mac}. Triggering auto-reconnect.")
                
                token = secrets.token_hex(16)
                tokens_col.insert_one({
                    "token": token,
                    "mac": mac,
                    "code": active_session.get("code"),
                    "expire_date": active_session.get("expire_date"),
                    "created_at": now
                })
                
                auth_action_url = f"http://{gw_address}:{gw_port}/wifidog/auth?token={token}"
                return redirect(auth_action_url)
        except Exception as e:
            logger.error(f"Error checking active session during portal load: {str(e)}")

    return render_template_string(
        PORTAL_TEMPLATE,
        mac=mac,
        gw_address=gw_address,
        gw_port=gw_port,
        gw_id=gw_id,
        userurl=userurl
    ), 200


@app.route('/favicon.ico')
def favicon():
    """Silence browser favicon requests with 204 No Content."""
    return Response(status=204)


@app.errorhandler(404)
def handle_404(e):
    """Catch routing errors without corrupting API background checks."""
    path = request.path.lower()
    
    if 'favicon.ico' in path:
        return Response(status=204)

    if path.startswith('/wifidog') or path.startswith('/api/wifidog') or 'auth' in path or 'ping' in path:
        logger.warning(f"Unhandled WifiDog API route requested: {request.path}")
        return Response("Not Found\n", status=404, mimetype='text/plain')
    
    logger.warning(f"404 redirect triggered for path: {request.path} from IP: {request.remote_addr}")
    return captive_login_page()


@app.route('/login', methods=['POST'])
def process_login():
    """Validates voucher and redirects client to local AP auth endpoint."""
    code = request.form.get('voucher', '').strip()
    mac = get_client_mac()
    gw_address = get_gateway_address()
    gw_port = get_param('gw_port', '2060')
    gw_id = get_param('gw_id', 'G1UQ6C8027360')
    userurl = get_param('userurl') or get_param('url') or 'http://www.google.com'

    logger.info(f"Voucher attempt submitted: Code '{code}' from MAC: {mac}")

    try:
        voucher = vouchers_col.find_one({"code": code, "status": "ACTIVE"})
    except Exception as e:
        logger.error(f"Database error while checking voucher {code}: {str(e)}")
        voucher = None

    if not voucher:
        logger.warning(f"Failed login attempt: Invalid or used voucher code '{code}' from MAC: {mac}")
        return render_template_string(
            PORTAL_TEMPLATE,
            mac=mac,
            gw_address=gw_address,
            gw_port=gw_port,
            gw_id=gw_id,
            userurl=userurl,
            error="Vocha hii siyo sahihi au ishatumika."
        )

    now = datetime.now(timezone.utc)
    duration_minutes = voucher['duration_minutes']
    expire_date = now + timedelta(minutes=duration_minutes)

    # 1. Create temporary token
    token = secrets.token_hex(16)
    tokens_col.insert_one({
        "token": token,
        "mac": mac,
        "code": code,
        "expire_date": expire_date,
        "created_at": now
    })

    # 2. Register Active MAC session
    sessions_col.replace_one(
        {"_id": mac},
        {
            "_id": mac,
            "code": code,
            "used_time": now,
            "expire_date": expire_date,
            "duration_minutes": duration_minutes,
            "status": "ACTIVE"
        },
        upsert=True
    )
    vouchers_col.update_one({"code": code}, {"$set": {"status": "USED", "used_by_mac": mac}})

    logger.info(f"Successful login: MAC {mac} redeemed voucher '{code}' for {duration_minutes} minutes.")

    # 3. Form destination URL pointing back to local AP
    auth_action_url = f"http://{gw_address}:{gw_port}/wifidog/auth?token={token}"

    return f"""
    <!DOCTYPE html>
    <html lang="sw">
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <meta http-equiv="refresh" content="0;url={auth_action_url}">
        <title>Inaunganisha...</title>
        <style>
            body {{ font-family: -apple-system, sans-serif; text-align: center; padding: 50px 20px; background: #f4f6f8; color: #172b4d; }}
            .card {{ background: white; padding: 30px 20px; border-radius: 12px; box-shadow: 0 4px 10px rgba(0,0,0,0.05); max-width: 320px; margin: 0 auto; }}
            .loader {{ border: 4px solid #dfe1e6; border-top: 4px solid #0052cc; border-radius: 50%; width: 40px; height: 40px; animation: spin 0.8s linear infinite; margin: 0 auto 20px auto; }}
            @keyframes spin {{ 0% {{ transform: rotate(0deg); }} 100% {{ transform: rotate(360deg); }} }}
            .btn {{ display: block; width: 100%; padding: 12px; background: #0052cc; color: white; text-decoration: none; font-weight: bold; border: none; border-radius: 6px; cursor: pointer; margin-top: 15px; font-size: 14px; box-sizing: border-box; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="loader"></div>
            <h3 style="margin: 0 0 8px 0; color: #0052cc;">Vocha Imekubaliwa!</h3>
            <p style="font-size: 14px; color: #5e6c84; margin-bottom: 10px;">Inaunganisha intaneti...</p>
            <a href="{auth_action_url}" class="btn">Bonyeza Hapa Kama Haujaunganishwa</a>
        </div>

        <script>
            setTimeout(function() {{
                window.location.replace("{auth_action_url}");
            }}, 100);
        </script>
    </body>
    </html>
    """


# ==========================================
# 🐶 REYEE / REYEEOS WIFIDOG PROTOCOL
# ==========================================

@app.route('/auth', methods=['GET'])
@app.route('/auth/', methods=['GET'])
@app.route('/wifidog/auth', methods=['GET'])
@app.route('/wifidog/auth/', methods=['GET'])
@app.route('/api/wifidog/auth', methods=['GET'])
@app.route('/api/wifidog/auth/', methods=['GET'])
def wifidog_auth_check():
    """ReyeeOS Background Auth Verification with strict expiration enforcement."""
    stage = request.args.get('stage', '').strip()
    token = request.args.get('token', '').strip()
    mac = request.args.get('mac', '').strip().upper()
    now = datetime.now(timezone.utc)

    # 1. Handle explicit client logout request
    if stage == 'logout':
        if mac:
            sessions_col.delete_one({"_id": mac})
            tokens_col.delete_many({"mac": mac})
            logger.info(f"Client logged out: MAC {mac}")
        return Response("Auth: 0\n", mimetype='text/plain')

    # 2. Check temporary token if provided
    if token:
        token_doc = tokens_col.find_one({"token": token})
        if token_doc:
            token_mac = token_doc.get("mac", "").upper()
            if not mac or mac == token_mac:
                return Response("Auth: 1\n", mimetype='text/plain')

    # 3. Strict Session Lookup
    session_doc = sessions_col.find_one({"_id": mac}) if mac else None

    if session_doc:
        exp = session_doc.get('expire_date')
        if exp and exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)

        # Active session found -> Allow access
        if exp and exp > now:
            return Response("Auth: 1\n", mimetype='text/plain')

    # 4. If session is missing or expired, clean up and deny access
    if mac:
        tokens_col.delete_many({"mac": mac})
        sessions_col.delete_one({"_id": mac})

    logger.warning(f"WifiDog Auth denied/expired for MAC: '{mac}'. Returning Auth: 0")
    return Response("Auth: 0\n", mimetype='text/plain')


@app.route('/ping', methods=['GET'])
@app.route('/ping/', methods=['GET'])
@app.route('/wifidog/ping', methods=['GET'])
@app.route('/wifidog/ping/', methods=['GET'])
@app.route('/api/wifidog/ping', methods=['GET'])
@app.route('/api/wifidog/ping/', methods=['GET'])
def wifidog_ping():
    """Periodic Reyee AP Heartbeat."""
    gw_id = request.args.get('gw_id', 'Unknown')
    logger.debug(f"Ping received from Access Point Gateway ID: {gw_id}")
    return Response("Pong\n", mimetype='text/plain')


@app.route('/gw_message', methods=['GET'])
@app.route('/gw_message/', methods=['GET'])
@app.route('/wifidog/gw_message', methods=['GET'])
@app.route('/wifidog/gw_message/', methods=['GET'])
@app.route('/api/wifidog/gw_message', methods=['GET'])
@app.route('/api/wifidog/gw_message/', methods=['GET'])
def wifidog_gw_message():
    """Displays router-level status messages."""
    msg = request.args.get('message', 'Unknown Error')
    logger.warning(f"Gateway status message: {msg}")
    return f"""
    <div style="font-family:sans-serif; text-align:center; padding: 40px;">
        <h2>WifiDog Gateway Status</h2>
        <p>Message: <b>{msg}</b></p>
        <a href="/">Try Again</a>
    </div>
    """, 200


# ==========================================
# 📊 ADMIN PANEL ROUTES
# ==========================================

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin'] = True
            logger.info("Admin login successful.")
            return redirect('/admin')
        logger.warning(f"Failed admin login attempt from IP: {request.remote_addr}")
        return render_template_string(ADMIN_LOGIN_TEMPLATE, error="Nenosiri sio sahihi!")
    return render_template_string(ADMIN_LOGIN_TEMPLATE)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin', None)
    logger.info("Admin logged out.")
    return redirect('/admin/login')


@app.route('/admin')
def admin_dashboard():
    if not session.get('admin'):
        return redirect('/admin/login')

    now = datetime.now(timezone.utc)
    vouchers = list(vouchers_col.find().sort("_id", -1).limit(50))
    active_sessions = list(sessions_col.find({"expire_date": {"$gt": now}}))

    rev_agg = list(vouchers_col.aggregate([
        {"$match": {"status": "USED"}},
        {"$group": {"_id": None, "total": {"$sum": "$price"}}}
    ]))
    total_rev = rev_agg[0]['total'] if rev_agg else 0.0

    return render_template_string(
        ADMIN_TEMPLATE,
        vouchers=vouchers,
        active_sessions=active_sessions,
        active_vouchers_count=vouchers_col.count_documents({"status": "ACTIVE"}),
        used_vouchers_count=vouchers_col.count_documents({"status": "USED"}),
        active_sessions_count=len(active_sessions),
        total_revenue=f"{total_rev:,.0f}"
    )


@app.route('/admin/revoke/<mac>')
def revoke_session(mac):
    """Instantly revokes a device's access from the admin dashboard."""
    if not session.get('admin'):
        return redirect('/admin/login')

    mac = mac.strip().upper()
    sessions_col.delete_one({"_id": mac})
    tokens_col.delete_many({"mac": mac})
    
    logger.info(f"Admin manually revoked internet access for MAC: {mac}")
    return redirect('/admin')


@app.route('/admin/generate', methods=['POST'])
def generate_vouchers():
    if not session.get('admin'):
        return redirect('/admin/login')

    qty = int(request.form.get('quantity', 8))
    duration = int(request.form.get('duration', 360))
    price = float(request.form.get('price', 500))

    existing_codes = set(v["code"] for v in vouchers_col.find({}, {"code": 1}))
    new_vouchers = []
    
    while len(new_vouchers) < qty and len(existing_codes) < 90000:
        code = generate_code(5)
        if code not in existing_codes:
            existing_codes.add(code)
            doc = {
                "code": code,
                "duration_minutes": duration,
                "price": price,
                "status": "ACTIVE",
                "created_at": datetime.now(timezone.utc)
            }
            new_vouchers.append(doc)

    if new_vouchers:
        vouchers_col.insert_many(new_vouchers)
        logger.info(f"Generated {len(new_vouchers)} new vouchers (Duration: {duration} mins, Price: TZS {price})")

    return render_template_string(PRINT_TEMPLATE, vouchers=new_vouchers)


# ==========================================
# 🚀 SERVER STARTUP
# ==========================================

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    logger.info(f"Starting HANS WIFI Portal server on port {port}")
    app.run(host='0.0.0.0', port=port)
