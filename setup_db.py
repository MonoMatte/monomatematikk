import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# 1. СОЗДАЕМ ТАБЛИЦУ ПОЛЬЗОВАТЕЛЕЙ (добавил все нужные колонки)
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT DEFAULT 'user',
    created_at TEXT DEFAULT (datetime('now'))
)
""")

# 2. ТАБЛИЦА ПРОГРЕССА
cursor.execute("""
CREATE TABLE IF NOT EXISTS progress (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    oppgave_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    UNIQUE(user_id, oppgave_id)
)
""")

# 3. ТАБЛИЦА УВЕДОМЛЕНИЙ
cursor.execute("""
CREATE TABLE IF NOT EXISTS kunngjøringer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    melding TEXT NOT NULL,
    opprettet TEXT DEFAULT (datetime('now'))
)
""")

conn.commit()
conn.close()
print("База данных полностью пересоздана и готова!")