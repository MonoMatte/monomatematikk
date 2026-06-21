import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'database.db')

conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS tildelinger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    klasse_id INTEGER NOT NULL,
    laerer_id INTEGER NOT NULL,
    tema TEXT NOT NULL,
    nivaa TEXT NOT NULL,
    id_base INTEGER NOT NULL,
    frist TEXT,
    melding TEXT,
    opprettet TEXT DEFAULT (datetime('now'))
)
""")

conn.commit()
conn.close()
print("✅ Tabellen 'tildelinger' er opprettet!")
print("Du kan nå starte app.py på nytt.")
