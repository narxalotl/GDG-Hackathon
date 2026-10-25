# database.py
import sqlite3

DB_FILE = "hackathon_app.db"

def init_db():
    """Creates the database and table if they don't exist yet."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_name TEXT,
            unit TEXT,
            room_name TEXT,
            jurisdiction TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_report(tenant_name, unit, room_name, jurisdiction):
    """Saves a tenant report submission into SQLite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO reports (tenant_name, unit, room_name, jurisdiction)
        VALUES (?, ?, ?, ?)
    ''', (tenant_name, unit, room_name, jurisdiction))
    conn.commit()
    conn.close()

def get_all_reports():
    """Fetches all submitted reports for the Landlord dashboard."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT tenant_name, unit, room_name, jurisdiction, created_at FROM reports ORDER BY id DESC')
    rows = cursor.fetchall()
    conn.close()
    return rows