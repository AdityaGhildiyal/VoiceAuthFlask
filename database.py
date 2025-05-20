import sqlite3
import os

def init_db():
    """Initialize SQLite database."""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,
        voice_data BLOB,
        phrase_data BLOB,
        key_data BLOB
    )''')
    conn.commit()
    conn.close()

def save_user_data(email, voice_data, phrase_data, key_data):
    """Save user data to database."""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('''INSERT OR REPLACE INTO users (email, voice_data, phrase_data, key_data)
                 VALUES (?, ?, ?, ?)''', (email, voice_data, phrase_data, key_data))
    conn.commit()
    conn.close()

def get_user_data(email):
    """Retrieve user data by email."""
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT voice_data, phrase_data, key_data FROM users WHERE email = ?', (email,))
    result = c.fetchone()
    conn.close()
    return result