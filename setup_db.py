import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    oppgave_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    UNIQUE(user_id, oppgave_id)
)
""")

# Legg til registreringsdato på users hvis den ikke finnes
try:
    cursor.execute("ALTER TABLE users ADD COLUMN created_at TEXT DEFAULT (datetime('now'))")
except:
    pass

# Kunngjøringer fra admin
cursor.execute("""
CREATE TABLE IF NOT EXISTS kunngjøringer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    melding TEXT NOT NULL,
    opprettet TEXT DEFAULT (datetime('now'))
)
""")

conn.commit()
conn.close()

print("Database oppdatert!")