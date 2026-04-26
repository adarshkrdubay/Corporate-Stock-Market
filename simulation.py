import random
import time
from database import get_db

NEWS_TEMPLATES = [
    # Positive
    ("Earnings report exceeds expectations for {}", 1.05),
    ("{} announces major new partnership", 1.08),
    ("Government policy favors {} sector", 1.03),
    ("New product launch by {} highly successful", 1.06),
    ("{} CEO wins industry leadership award", 1.02),
    # Negative
    ("{} faces unexpected supply chain issues", 0.95),
    ("Regulatory probe launched against {}", 0.92),
    ("Quarterly profits dip for {}", 0.96),
    ("{} loses key contract to competitor", 0.93),
    ("Broader market slump affects {}", 0.97)
]
from datetime import datetime
import pytz

def is_market_open():
    ist = pytz.timezone('Asia/Kolkata')
    now = datetime.now(ist)

    # Market timings: 9 AM to 5 PM
    market_open = now.replace(hour=10, minute=00, second=0, microsecond=0)
    market_close = now.replace(hour=15, minute=0, second=0, microsecond=0)

    return market_open <= now <= market_close
def update_prices():
    """Runs every 5-10 seconds to update all stock prices."""
    if not is_market_open():
        print("Market closed ❌ - skipping price update")
        return

    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM stocks")
    stocks = cursor.fetchall()

    for stock in stocks:
        stock_id = stock['id']
        current_price = stock['current_price']
        volatility = stock['volatility']

        # 1. Random walk fluctuation
        # We want small, frequent changes. Volatility is annualized roughly. Let's make it a small random percentage.
        # e.g. normal distribution centered at 0 with standard deviation = volatility / 10
        change_pct = random.gauss(0, volatility / 10)
        new_price = current_price * (1 + change_pct)

        # 2. Check for active news impacts (delay of 30 seconds)
        # We look for news events for this stock that are active and older than 30 seconds
        cursor.execute('''
            SELECT id, impact_multiplier FROM news_events
            WHERE stock_id = ? AND is_active = 1
            AND (julianday('now', '+05:30') - julianday(timestamp)) * 86400 > 30 -- seconds difference
        ''', (stock_id,))
        active_news = cursor.fetchall()

        for news in active_news:
            # Apply the impact
            new_price = new_price * news['impact_multiplier']
            # Mark news as resolved (inactive)
            cursor.execute("UPDATE news_events SET is_active = 0 WHERE id = ?", (news['id'],))

        # Ensure price doesn't drop below 1
        new_price = max(1.0, round(new_price, 2))

        # Update stock price
        cursor.execute("UPDATE stocks SET current_price = ? WHERE id = ?", (new_price, stock_id))

        # Add to history
        cursor.execute("INSERT INTO price_history (stock_id, price) VALUES (?, ?)", (stock_id, new_price))

    conn.commit()
    conn.close()

def generate_news():
    """Runs occasionally to generate a new market event."""
    if not is_market_open():
        return
    conn = get_db()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, sector FROM stocks ORDER BY RANDOM() LIMIT 1")
    stock = cursor.fetchone()
    if not stock:
        return

    template, impact = random.choice(NEWS_TEMPLATES)
    headline = template.format(stock['name'])

    cursor.execute('''
        INSERT INTO news_events (stock_id, sector, headline, impact_multiplier)
        VALUES (?, ?, ?, ?)
    ''', (stock['id'], stock['sector'], headline, impact))

    conn.commit()
    conn.close()
    print(f"📰 NEWS EVENT: {headline}")
