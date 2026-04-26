import sqlite3
from database import get_db, init_db
from werkzeug.security import generate_password_hash

STOCKS = [
    # Financial Services
    ('HDFCBANK', 'HDFC Bank Ltd.', 'Financial Services', 1500.0, 0.015),
    ('ICICIBANK', 'ICICI Bank Ltd.', 'Financial Services', 1000.0, 0.02),
    ('SBIN', 'State Bank of India', 'Financial Services', 750.0, 0.025),
    # Technology (IT)
    ('TCS', 'Tata Consultancy Services Ltd.', 'Technology (IT)', 3500.0, 0.01),
    ('INFY', 'Infosys Ltd.', 'Technology (IT)', 1400.0, 0.015),
    ('HCLTECH', 'HCL Technologies Ltd.', 'Technology (IT)', 1300.0, 0.015),
    # Energy & Oil/Gas
    ('RELIANCE', 'Reliance Industries Ltd.', 'Energy & Oil/Gas', 2800.0, 0.015),
    ('NTPC', 'NTPC Ltd.', 'Energy & Oil/Gas', 300.0, 0.01),
    ('ADANIPOWER', 'Adani Power Ltd.', 'Energy & Oil/Gas', 500.0, 0.04),
    # Automobile
    ('TATAMOTORS', 'Tata Motors Ltd.', 'Automobile', 900.0, 0.025),
    ('MANDM', 'Mahindra & Mahindra Ltd.', 'Automobile', 1800.0, 0.02),
    ('MARUTI', 'Maruti Suzuki India Ltd.', 'Automobile', 1500.0, 0.015),
    # Consumer Goods & Telecom
    ('BHARTIARTL', 'Bharti Airtel Ltd.', 'Consumer Goods & Telecom', 1100.0, 0.02),
    ('HINDUNILVR', 'Hindustan Unilever Ltd.', 'Consumer Goods & Telecom', 2500.0, 0.01),
    ('ITC', 'ITC Ltd.', 'Consumer Goods & Telecom', 450.0, 0.01)
]

def seed():
    # Initialize schema
    init_db()

    conn = get_db()
    cursor = conn.cursor()

    
    cursor.execute("DELETE FROM transactions")
    cursor.execute("DELETE FROM portfolio")
    cursor.execute("DELETE FROM price_history")
    cursor.execute("DELETE FROM news_events")
    cursor.execute("DELETE FROM stocks")
    cursor.execute("DELETE FROM users")

    
    admin_pw = generate_password_hash('*******')
    

    cursor.execute("INSERT INTO users (username, password_hash, balance, is_admin) VALUES ('*****', ?, 100000.0, 1)", (admin_pw,))

    for symbol, name, sector, base_price, volatility in STOCKS:
        cursor.execute('''
            INSERT INTO stocks (symbol, name, sector, base_price, current_price, volatility)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (symbol, name, sector, base_price, base_price, volatility))

       
        import random
        from datetime import datetime, timedelta

        stock_id = cursor.lastrowid
        history_points = []
        current_history_price = base_price * (1 + random.uniform(-0.1, 0.1)) # Start +/- 10% 7 days ago
        now = datetime.now()

        for i in range(168, 0, -1):
            current_history_price = max(1.0, current_history_price * (1 + random.gauss(0, volatility / 5)))
            timestamp = (now - timedelta(hours=i)).strftime('%Y-%m-%d %H:%M:%S')
            history_points.append((stock_id, current_history_price, timestamp))

        history_points.append((stock_id, current_history_price, now.strftime('%Y-%m-%d %H:%M:%S')))

        
        cursor.execute("UPDATE stocks SET current_price = ?, base_price = ? WHERE id = ?", (current_history_price, current_history_price, stock_id))

        cursor.executemany('''
            INSERT INTO price_history (stock_id, price, timestamp)
            VALUES (?, ?, ?)
        ''', history_points)

    conn.commit()
    conn.close()
    print("Database seeded successfully with default user and 15 stocks.")

if __name__ == '__main__':
    seed()
