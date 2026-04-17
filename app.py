from flask import Flask, jsonify, request, render_template, session, redirect, url_for
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
from apscheduler.schedulers.background import BackgroundScheduler
import sqlite3
import os
import atexit

from database import get_db
import simulation

app = Flask(__name__, static_folder="static", template_folder="static")
app.secret_key = '_____'
from datetime import datetime
import pytz

def is_market_open():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)

    # Market timings: 9 AM to 5 PM
    market_open = now.replace(hour=10, minute=0, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=0, second=0, microsecond=0)

    return market_open <= now <= market_close
# -- SCHEDULER SETUP --
scheduler = BackgroundScheduler()
scheduler.add_job(func=simulation.update_prices, trigger="interval", seconds=300)
scheduler.add_job(func=simulation.generate_news, trigger="interval", minutes=60)
scheduler.start()

# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown(wait=False))

# -- UTILITIES & DECORATORS --
def get_user_id():
    return session.get('user_id')

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            # Check if this is an API call
            if request.path.startswith('/api/'):
                return jsonify({"error": "Unauthorized"}), 401
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session or not session.get('is_admin'):
            if request.path.startswith('/api/'):
                return jsonify({"error": "Admin privileges required"}), 403
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


# -- AUTH ROUTES --
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')

    data = request.json
    username = data.get('username')
    password = data.get('password')

    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, password_hash, is_admin FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    conn.close()

    if user and check_password_hash(user['password_hash'], password):
        session['user_id'] = user['id']
        session['username'] = username
        session['is_admin'] = bool(user['is_admin'])
        return jsonify({"success": True})

    return jsonify({"error": "Invalid username or password"}), 401
@app.route('/signup', methods=['GET', 'POST'])
def signupold():
    if request.method == 'GET':
        return render_template('signup.html')




@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


# -- APP ROUTES --
@app.route('/')
def index():
    if 'user_id' not in session:
        return render_template('landing.html')
    return render_template('index.html')

@app.route('/api/user', methods=['GET'])
@login_required
def get_user():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, username, balance, is_admin FROM users WHERE id = ?", (get_user_id(),))
    user = cursor.fetchone()
    conn.close()
    if user:
        return jsonify(dict(user))
    return jsonify({"error": "User not found"}), 404

@app.route('/api/stocks', methods=['GET'])
@login_required
def get_stocks():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM stocks ORDER BY sector ASC, name ASC")
    stocks = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(stocks)

@app.route('/api/transactions/<int:stock_id>', methods=['GET'])
@login_required
def get_user_transactions(stock_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT type, quantity, price, timestamp
        FROM transactions
        WHERE user_id = ? AND stock_id = ?
        ORDER BY timestamp ASC
    ''', (get_user_id(), stock_id))
    txs = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(txs)

@app.route('/api/stocks/<int:stock_id>/history', methods=['GET'])
@login_required
def get_stock_history(stock_id):
    conn = get_db()
    cursor = conn.cursor()
    # Get last 200 data points for the graph (covers the entire backfilled week + live points)
    cursor.execute('''
        SELECT price, timestamp FROM price_history
        WHERE stock_id = ? ORDER BY id DESC LIMIT 200
    ''', (stock_id,))
    history = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(history[::-1])

@app.route('/api/portfolio', methods=['GET'])
@login_required
def get_portfolio():
    user_id = get_user_id()
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT p.stock_id, s.symbol, s.name, s.current_price, p.quantity, p.avg_buy_price
        FROM portfolio p
        JOIN stocks s ON p.stock_id = s.id
        WHERE p.user_id = ? AND p.quantity > 0
    ''', (user_id,))
    portfolio = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(portfolio)

@app.route('/api/news', methods=['GET'])
@login_required
def get_news():
    conn = get_db()
    cursor = conn.cursor()
    # Fetch recent 10 news events
    cursor.execute('''
        SELECT n.*, s.symbol FROM news_events n
        LEFT JOIN stocks s ON n.stock_id = s.id
        ORDER BY n.id DESC LIMIT 10
    ''')
    news = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(news)

@app.route('/api/leaderboard', methods=['GET'])
@login_required
def get_leaderboard():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.username, u.balance,
               COALESCE(SUM(p.quantity * s.current_price), 0) as portfolio_value
        FROM users u
        LEFT JOIN portfolio p ON u.id = p.user_id
        LEFT JOIN stocks s ON p.stock_id = s.id
        WHERE u.is_admin = 0
        GROUP BY u.id
    ''')

    users_data = cursor.fetchall()
    conn.close()

    leaderboard = []
    for row in users_data:
        net_worth = row['balance'] + row['portfolio_value']
        profit = net_worth - 10000.0
        leaderboard.append({
            "username": row['username'],
            "profit": profit
        })

    leaderboard.sort(key=lambda x: x['profit'], reverse=True)
    return jsonify(leaderboard)

@app.route('/api/user/<username>/portfolio', methods=['GET'])
@login_required
def get_user_public_portfolio(username):
    conn = get_db()
    cursor = conn.cursor()

    # First get user id
    cursor.execute("SELECT id FROM users WHERE username = ? AND is_admin = 0", (username,))
    user = cursor.fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "User not found or is admin"}), 404

    user_id = user['id']
    cursor.execute('''
        SELECT s.symbol, s.name, p.quantity, p.avg_buy_price, s.current_price
        FROM portfolio p
        JOIN stocks s ON p.stock_id = s.id
        WHERE p.user_id = ? AND p.quantity > 0
    ''', (user_id,))

    portfolio = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return jsonify(portfolio)

@app.route('/api/buy', methods=['POST'])
@login_required
def buy_stock():
    data = request.json
    stock_id = data.get('stock_id')
    quantity = int(data.get('quantity', 0))
    user_id = get_user_id()

    if session.get('is_admin'):
        return jsonify({"error": "Administrators are not allowed to trade."}), 403
    if not is_market_open():
        return jsonify({
        "error": "Market is closed. Trading allowed only between 9:00 AM to 5:00 PM IST."
        }), 403

    if quantity <= 0:
        return jsonify({"error": "Invalid quantity"}), 400

    conn = get_db()
    cursor = conn.cursor()

    # Get stock current price
    cursor.execute("SELECT current_price FROM stocks WHERE id = ?", (stock_id,))
    stock = cursor.fetchone()
    if not stock:
        return jsonify({"error": "Stock not found"}), 404

    price = stock['current_price']
    total_cost = price * quantity

    # Check balance
    cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    if user['balance'] < total_cost:
        conn.close()
        return jsonify({"error": "Insufficient balance"}), 400

    # Deduct balance
    new_balance = user['balance'] - total_cost
    cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))

    # Add to portfolio
    cursor.execute("SELECT * FROM portfolio WHERE user_id = ? AND stock_id = ?", (user_id, stock_id))
    port = cursor.fetchone()
    if port:
        old_qty = port['quantity']
        old_avg = port['avg_buy_price']
        new_qty = old_qty + quantity
        new_avg = ((old_avg * old_qty) + total_cost) / new_qty
        cursor.execute("UPDATE portfolio SET quantity = ?, avg_buy_price = ? WHERE id = ?", (new_qty, new_avg, port['id']))
    else:
        cursor.execute("INSERT INTO portfolio (user_id, stock_id, quantity, avg_buy_price) VALUES (?, ?, ?, ?)",
                       (user_id, stock_id, quantity, price))

    # Record transaction
    cursor.execute("INSERT INTO transactions (user_id, stock_id, type, quantity, price) VALUES (?, ?, 'BUY', ?, ?)",
                   (user_id, stock_id, quantity, price))

    conn.commit()
    conn.close()

    return jsonify({"message": "Purchase successful", "new_balance": new_balance})

@app.route('/api/sell', methods=['POST'])
@login_required
def sell_stock():
    data = request.json
    stock_id = data.get('stock_id')
    quantity = int(data.get('quantity', 0))
    user_id = get_user_id()

    if session.get('is_admin'):
        return jsonify({"error": "Administrators are not allowed to trade."}), 403
    if not is_market_open():
        return jsonify({
        "error": "Market is closed. Trading allowed only between 9:00 AM to 5:00 PM IST."
        }), 403

    if quantity <= 0:
        return jsonify({"error": "Invalid quantity"}), 400

    conn = get_db()
    cursor = conn.cursor()

    # Check portfolio
    cursor.execute("SELECT * FROM portfolio WHERE user_id = ? AND stock_id = ?", (user_id, stock_id))
    port = cursor.fetchone()

    if not port or port['quantity'] < quantity:
        conn.close()
        return jsonify({"error": "Insufficient quantity in portfolio"}), 400

    # Get stock current price
    cursor.execute("SELECT current_price FROM stocks WHERE id = ?", (stock_id,))
    stock = cursor.fetchone()
    price = stock['current_price']

    total_earned = price * quantity

    # Add to balance
    cursor.execute("SELECT balance FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    new_balance = user['balance'] + total_earned
    cursor.execute("UPDATE users SET balance = ? WHERE id = ?", (new_balance, user_id))

    # Deduct from portfolio
    new_qty = port['quantity'] - quantity
    if new_qty == 0:
        cursor.execute("DELETE FROM portfolio WHERE id = ?", (port['id'],))
    else:
        cursor.execute("UPDATE portfolio SET quantity = ? WHERE id = ?", (new_qty, port['id']))

    # Record transaction
    cursor.execute("INSERT INTO transactions (user_id, stock_id, type, quantity, price) VALUES (?, ?, 'SELL', ?, ?)",
                   (user_id, stock_id, quantity, price))

    conn.commit()
    conn.close()

    return jsonify({"message": "Sale successful", "new_balance": new_balance})

@app.route('/api/market-status')
def market_status():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)

    open_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
    close_time = now.replace(hour=17, minute=0, second=0, microsecond=0)

    status = "OPEN" if open_time <= now <= close_time else "CLOSED"

    return jsonify({
        "status": status,
        "current_time": now.strftime("%I:%M %p"),
        "open_time": "09:00 AM",
        "close_time": "05:00 PM"
    })


if __name__ == '__main__':
    app.run(host="0.0.0.0",debug=True, use_reloader=False)
