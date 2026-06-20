import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'database.db')

conn = sqlite3.connect(DATABASE)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS klasser (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    navn TEXT NOT NULL,
    laerer_id INTEGER NOT NULL,
    opprettet TEXT DEFAULT (datetime('now'))
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS klasse_elever (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    klasse_id INTEGER NOT NULL,
    elev_id INTEGER NOT NULL,
    UNIQUE(klasse_id, elev_id)
)
""")

conn.commit()
conn.close()
print("✅ Tabellene 'klasser' og 'klasse_elever' er opprettet!")
print("Du kan nå starte app.py på nytt.")
