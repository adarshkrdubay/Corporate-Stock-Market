import sqlite3
import os

DATABASE_PATH = os.path.join(os.path.dirname(__file__), 'market.db')

def get_db():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # Create Users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            balance REAL NOT NULL DEFAULT 10000.0,
            is_admin BOOLEAN DEFAULT 0
        )
    ''')

    # Create Stocks table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            sector TEXT NOT NULL,
            base_price REAL NOT NULL,
            current_price REAL NOT NULL,
            volatility REAL NOT NULL DEFAULT 0.02
        )
    ''')

    # Create Price History table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id INTEGER NOT NULL,
            price REAL NOT NULL,
            timestamp DATETIME DEFAULT (datetime('now', '+05:30')),
            FOREIGN KEY (stock_id) REFERENCES stocks(id)
        )
    ''')

    # Create Portfolio table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS portfolio (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            stock_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL DEFAULT 0,
            avg_buy_price REAL NOT NULL DEFAULT 0.0,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (stock_id) REFERENCES stocks(id)
        )
    ''')

    # Create Transactions table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            stock_id INTEGER NOT NULL,
            type TEXT NOT NULL, -- BUY or SELL
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            timestamp DATETIME DEFAULT (datetime('now', '+05:30')),
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (stock_id) REFERENCES stocks(id)
        )
    ''')

    # Create NewsEvents table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS news_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id INTEGER,
            sector TEXT,
            headline TEXT NOT NULL,
            impact_multiplier REAL NOT NULL,
            timestamp DATETIME DEFAULT (datetime('now', '+05:30')),
            is_active INTEGER DEFAULT 1,
            FOREIGN KEY (stock_id) REFERENCES stocks(id)
        )
    ''')

    conn.commit()
    conn.close()

if __name__ == '__main__':
    init_db()
    print("Database initialized.")
