import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'database.db')

conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()

try:
    cursor.execute("ALTER TABLE progress ADD COLUMN timestamp TEXT")
    print("✅ Kolonnen 'timestamp' er lagt til i 'progress'-tabellen!")
except sqlite3.OperationalError as e:
    if "duplicate column" in str(e).lower():
        print("ℹ️ Kolonnen 'timestamp' finnes allerede – ingenting å gjøre.")
    else:
        raise

# Fyll inn dagens dato for gamle rader som mangler timestamp
cursor.execute("UPDATE progress SET timestamp = datetime('now') WHERE timestamp IS NULL")

conn.commit()
conn.close()
print("Du kan nå starte app.py på nytt.")
