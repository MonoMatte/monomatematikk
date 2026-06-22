from flask import Flask, render_template, request, session, redirect
from flask_babel import Babel, get_locale as babel_get_locale
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE = os.path.join(BASE_DIR, 'database.db')

app = Flask(__name__)
app.secret_key = "noe_hemmelig_her"


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect("/login")
        return f(*args, **kwargs)
    return wrapper


# DATABASE
def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# REGISTRERING
@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        try:
            conn.execute(
                "INSERT INTO users (username, password_hash, role) VALUES (?, ?, ?)",
                (username, generate_password_hash(password), 'user')
            )
            conn.commit()
        except Exception as e:
            print(f"Feil ved registrering: {e}")
            return render_template("register.html", error="Brukernavn er allerede tatt")

        return redirect("/login")

    return render_template("register.html")


# LOGG INN
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]

        conn = get_db()
        user = conn.execute(
            "SELECT * FROM users WHERE username = ?", (username,)
        ).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["username"] = user["username"]
            session["role"] = user["role"]
            return redirect("/dashboard")

        return "Feil brukernavn eller passord"

    return render_template("login.html")


# DASHBOARD
@app.route("/dashboard")
@login_required
def dashboard():
    conn = get_db()

    total = conn.execute(
        "SELECT COUNT(*) as cnt FROM progress WHERE user_id = ?",
        (session["user_id"],)
    ).fetchone()["cnt"]

    # Regnerekkefølge per nivå
    rnivaa1 = conn.execute(
        "SELECT COUNT(*) as cnt FROM progress WHERE user_id = ? AND oppgave_id BETWEEN 1 AND 30",
        (session["user_id"],)
    ).fetchone()["cnt"]

    rnivaa2 = conn.execute(
        "SELECT COUNT(*) as cnt FROM progress WHERE user_id = ? AND oppgave_id BETWEEN 2001 AND 2030",
        (session["user_id"],)
    ).fetchone()["cnt"]

    rnivaa3 = conn.execute(
        "SELECT COUNT(*) as cnt FROM progress WHERE user_id = ? AND oppgave_id BETWEEN 3001 AND 3030",
        (session["user_id"],)
    ).fetchone()["cnt"]

    # Hele tall per nivå
    hnivaa1 = conn.execute(
        "SELECT COUNT(*) as cnt FROM progress WHERE user_id = ? AND oppgave_id BETWEEN 4001 AND 4030",
        (session["user_id"],)
    ).fetchone()["cnt"]

    hnivaa2 = conn.execute(
        "SELECT COUNT(*) as cnt FROM progress WHERE user_id = ? AND oppgave_id BETWEEN 5001 AND 5030",
        (session["user_id"],)
    ).fetchone()["cnt"]

    hnivaa3 = conn.execute(
        "SELECT COUNT(*) as cnt FROM progress WHERE user_id = ? AND oppgave_id BETWEEN 6001 AND 6030",
        (session["user_id"],)
    ).fetchone()["cnt"]

    kunngjøring = conn.execute("SELECT * FROM kunngjøringer ORDER BY id DESC LIMIT 1").fetchone()

    # Hent tildelinger fra klasser eleven er medlem av
    mine_tildelinger_rows = conn.execute(
        "SELECT t.* FROM tildelinger t "
        "JOIN klasse_elever ke ON ke.klasse_id = t.klasse_id "
        "WHERE ke.elev_id = ? ORDER BY t.id DESC",
        (session["user_id"],)
    ).fetchall()

    mine_tildelinger = []
    for t in mine_tildelinger_rows:
        id_base = t["id_base"]
        loste = conn.execute(
            "SELECT COUNT(*) as cnt FROM progress WHERE user_id = ? AND status = 'riktig' "
            "AND oppgave_id > ? AND oppgave_id <= ?",
            (session["user_id"], id_base, id_base + 200)
        ).fetchone()["cnt"]
        mine_tildelinger.append({
            "tema": t["tema"],
            "nivaa": t["nivaa"],
            "frist": t["frist"],
            "melding": t["melding"],
            "loste": loste,
            "ferdig": loste >= 5,
            "link": f"/oppgaver/{t['tema']}/{'nivaa1' if t['nivaa'] == 'Nivå 1' else 'nivaa2' if t['nivaa'] == 'Nivå 2' else 'nivaa3'}",
        })

    return render_template("dashboard.jinja2",
        username=session["username"],
        role=session.get("role", "user"),
        total=total,
        mine_tildelinger=mine_tildelinger,
        nivaa1=rnivaa1,
        nivaa2=rnivaa2,
        nivaa3=rnivaa3,
        hnivaa1=hnivaa1,
        hnivaa2=hnivaa2,
        hnivaa3=hnivaa3,
        kunngjøring=kunngjøring
    )


# ADMIN PANEL
@app.route("/admin")
@login_required
def admin():
    if session.get("role") != "admin":
        return redirect("/dashboard")

    conn = get_db()
    søk = request.args.get("søk", "").strip()

    if søk:
        users = conn.execute("""
            SELECT u.id, u.username, u.role, u.created_at,
                   COUNT(p.id) as løste
            FROM users u
            LEFT JOIN progress p ON p.user_id = u.id
            WHERE u.username LIKE ?
            GROUP BY u.id
            ORDER BY u.created_at DESC
        """, (f"%{søk}%",)).fetchall()
    else:
        users = conn.execute("""
            SELECT u.id, u.username, u.role, u.created_at,
                   COUNT(p.id) as løste
            FROM users u
            LEFT JOIN progress p ON p.user_id = u.id
            GROUP BY u.id
            ORDER BY u.created_at DESC
        """).fetchall()

    totalt_brukere = conn.execute("SELECT COUNT(*) as cnt FROM users").fetchone()["cnt"]
    totalt_løste = conn.execute("SELECT COUNT(*) as cnt FROM progress").fetchone()["cnt"]
    kunngjøring = conn.execute("SELECT * FROM kunngjøringer ORDER BY id DESC LIMIT 1").fetchone()

    return render_template("admin.html",
        users=users,
        totalt_brukere=totalt_brukere,
        totalt_løste=totalt_løste,
        current_user_id=session["user_id"],
        søk=søk,
        kunngjøring=kunngjøring
    )


@app.route("/admin/slett/<int:user_id>", methods=["POST"])
@login_required
def admin_slett_bruker(user_id):
    if session.get("role") != "admin":
        return redirect("/dashboard")
    conn = get_db()
    conn.execute("DELETE FROM progress WHERE user_id = ?", (user_id,))
    conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
    conn.commit()
    return redirect("/admin")


@app.route("/admin/rolle/<int:user_id>", methods=["POST"])
@login_required
def admin_endre_rolle(user_id):
    if session.get("role") != "admin":
        return redirect("/dashboard")
    ny_rolle = request.form.get("rolle")
    if ny_rolle in ["user", "admin", "teacher"]:
        conn = get_db()
        conn.execute("UPDATE users SET role = ? WHERE id = ?", (ny_rolle, user_id))
        conn.commit()
    return redirect("/admin")


@app.route("/admin/nullstill/<int:user_id>", methods=["POST"])
@login_required
def admin_nullstill_progresjon(user_id):
    if session.get("role") != "admin":
        return redirect("/dashboard")
    conn = get_db()
    conn.execute("DELETE FROM progress WHERE user_id = ?", (user_id,))
    conn.commit()
    return redirect("/admin")


@app.route("/admin/kunngjøring", methods=["POST"])
@login_required
def admin_kunngjøring():
    if session.get("role") != "admin":
        return redirect("/dashboard")
    melding = request.form.get("melding", "").strip()
    if melding:
        conn = get_db()
        conn.execute("DELETE FROM kunngjøringer")
        conn.execute("INSERT INTO kunngjøringer (melding) VALUES (?)", (melding,))
        conn.commit()
    return redirect("/admin")


# LOGG UT
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# SPRÅK
def get_locale():
    return request.args.get("lang", "nb")

babel = Babel(app, locale_selector=get_locale)

@app.context_processor
def inject_locale():
    return {"get_locale": get_locale}


# INDEX
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/about')
@login_required
def about():
    return render_template('about.html')


# OPPGAVER – VELG TEMA
@app.route('/oppgaver')
@login_required
def oppgaver():
    return render_template('oppgaver.html')


@app.route('/oppgaver/trinn/<int:trinn>')
@login_required
def oppgaver_trinn(trinn):
    if trinn == 8:
        return render_template("oppgaver_trinn_8.html")
    elif trinn == 9:
        return render_template("oppgaver_trinn_9.html")
    elif trinn == 10:
        return render_template("oppgaver_trinn_10.html")
    else:
        return "Ugyldig trinn", 404


# ─────────────────────────────────────────────
# REGNEREKKEFØLGE
# ─────────────────────────────────────────────

@app.route('/oppgaver/algebra')
def oppgaver_algebra():
    undertemaer = [
        {"navn": "Regnerekkefølge", "link": "/oppgaver/algebra/regnerekkefolge"},
        {"navn": "Likninger", "link": "/oppgaver/algebra/likninger"},
    ]
    return render_template("oppgaver_algebra.html", undertemaer=undertemaer)


@app.route('/oppgaver/algebra/regnerekkefolge')
def regnerekkefolge():
    undertemaer = [
        {"navn": "Regnerekkefølge", "link": "/oppgaver/algebra/regnerekkefolge"},
        {"navn": "Likninger", "link": "/oppgaver/algebra/likninger"},
    ]
    return render_template("oppgaver_algebra_regnerekkefolge.html", undertemaer=undertemaer)


# REGNEREKKEFØLGE NIVÅ 1 (ID 1–30)
@app.route('/oppgaver/Regnerekkefølge/nivaa1', methods=['GET', 'POST'])
@login_required
def regnerekkefolge_nivaa1_route():
    oppgaver = [
        ("2 + 3 ⋅ 2", "8"), ("4 + 6 : 2", "7"), ("5 ⋅ 2 + 1", "11"),
        ("8 - 3 + 2", "7"), ("10 : 2 + 4", "9"), ("3 + 4 ⋅ 2", "11"),
        ("6 + 8 : 4", "8"), ("7 - 2 + 5", "10"), ("9 ⋅ 1 + 3", "12"),
        ("12 : 3 + 2", "6"), ("4 ⋅ 2 + 6", "14"), ("15 - 6 + 1", "10"),
        ("18 : 3 + 1", "7"), ("2 + 5 ⋅ 3", "17"), ("20 : 5 + 4", "8"),
        ("3 ⋅ 3 + 2", "11"), ("14 - 4 + 3", "13"), ("16 : 4 + 6", "10"),
        ("5 + 2 ⋅ 4", "13"), ("9 + 12 : 3", "13"), ("7 ⋅ 2 - 3", "11"),
        ("8 + 9 : 3", "11"), ("6 ⋅ 2 + 5", "17"), ("21 : 3 + 2", "9"),
        ("4 + 3 ⋅ 3", "13"), ("10 - 2 ⋅ 3", "4"), ("18 : 2 - 4", "5"),
        ("3 + 6 ⋅ 2", "15"), ("5 ⋅ 3 - 4", "11"), ("12 : 4 + 7", "10"),
    ]

    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)

    if nummer > total:
        return render_template("ferdig.html", tittel="Nivå 1 – Regnerekkefølge", melding="Du fullførte nivå 1! Bra jobba 🎉")

    oppgave, fasit = oppgaver[nummer - 1]
    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], nummer, "riktig"))
            conn.commit()
            riktige_oppgaver.add(nummer)
        elif svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    return render_template("regnerekkefolge_nivaa1.html",
        oppgave=oppgave, nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=list(range(1, total + 1)),
        riktige_oppgaver=riktige_oppgaver
    )


# REGNEREKKEFØLGE NIVÅ 2 (ID 2001–2030)
regnerekkefolge_nivaa2 = [
    ("(3 + 2) ⋅ 4", "20"), ("6 ⋅ (2 + 1)", "18"), ("(8 - 3) ⋅ 2", "10"),
    ("4 + (6 : 2)", "7"), ("(10 - 4) + 3", "9"), ("2 ⋅ (5 + 3)", "16"),
    ("(12 : 3) + 5", "9"), ("7 + (4 ⋅ 2)", "15"), ("(9 - 1) : 2", "4"),
    ("3 + (8 - 5)", "6"), ("(6 + 2) ⋅ 3", "24"), ("(15 - 9) + 4", "10"),
    ("4 ⋅ (3 + 1)", "16"), ("(18 : 2) - 4", "5"), ("5 + (12 : 3)", "9"),
    ("(7 + 3) ⋅ 2", "20"), ("(20 - 8) : 4", "3"), ("6 + (9 - 2)", "13"),
    ("(14 : 2) + 6", "13"), ("3 ⋅ (4 + 2)", "18"), ("(16 - 6) : 2", "5"),
    ("8 + (3 ⋅ 3)", "17"), ("(5 + 7) - 4", "8"), ("2 + (10 : 2)", "7"),
    ("(9 - 3) ⋅ 3", "18"), ("4 + (15 : 3)", "9"), ("(8 + 4) : 2", "6"),
    ("6 ⋅ (3 - 1)", "12"), ("(10 - 2) + 5", "13"), ("3 + (14 : 2)", "10"),
]


@app.route('/oppgaver/Regnerekkefølge/nivaa2', methods=['GET', 'POST'])
@login_required
def regnerekkefolge_nivaa2_route():
    oppgaver = regnerekkefolge_nivaa2
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 2000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Nivå 2 – Regnerekkefølge", melding="Du fullførte nivå 2! Sterkt jobba 🔥")

    oppgave, fasit = oppgaver[nummer - 1]
    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 2000 + i, "link": f"/oppgaver/Regnerekkefølge/nivaa2?n={i}"} for i in range(1, total + 1)]

    return render_template("regnerekkefolge_nivaa2.html",
        oppgave=oppgave, nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny,
        riktige_oppgaver=riktige_oppgaver,
        undertemaer=[
            {"navn": "Regnerekkefølge", "link": "/oppgaver/algebra/regnerekkefolge"},
            {"navn": "Likninger", "link": "/oppgaver/algebra/likninger"},
        ]
    )


# REGNEREKKEFØLGE NIVÅ 3 (ID 3001–3030)
regnerekkefolge_nivaa3 = [
    ("(3 + 2) ⋅ (4 - 1)", "15"), ("6 ⋅ (2 + 1) - 4", "14"), ("(8 - 3) ⋅ (2 + 2)", "20"),
    ("4 + (6 : 2) ⋅ 3", "13"), ("(10 - 4) + (3 ⋅ 2)", "12"), ("2 ⋅ (5 + 3) - 6", "10"),
    ("(12 : 3) + (5 ⋅ 2)", "14"), ("7 + (4 ⋅ 2) ⋅ 2", "23"), ("(9 - 1) : 2 + 7", "11"),
    ("3 + (8 - 5) ⋅ 4", "15"), ("(6 + 2) ⋅ 3 - 5", "19"), ("(15 - 9) + (4 ⋅ 3)", "18"),
    ("4 ⋅ (3 + 1) ⋅ 2", "32"), ("(18 : 2) - 4 + 9", "14"), ("5 + (12 : 3) ⋅ 4", "21"),
    ("(7 + 3) ⋅ 2 ⋅ 2", "40"), ("(20 - 8) : 4 + 9", "12"), ("6 + (9 - 2) ⋅ 3", "27"),
    ("(14 : 2) + 6 ⋅ 2", "20"), ("3 ⋅ (4 + 2) ⋅ 2", "36"), ("(16 - 6) : 2 ⋅ 5", "25"),
    ("8 + (3 ⋅ 3) ⋅ 2", "26"), ("(5 + 7) - 4 ⋅ 3", "0"), ("2 + (10 : 2) ⋅ 4", "22"),
    ("(9 - 3) ⋅ 3 ⋅ 2", "36"), ("4 + (15 : 3) ⋅ 5", "29"), ("(8 + 4) : 2 ⋅ 6", "36"),
    ("6 ⋅ (3 - 1) ⋅ 3", "36"), ("(10 - 2) + 5 ⋅ 4", "28"), ("3 + (14 : 2) ⋅ 3", "24"),
]


@app.route('/oppgaver/Regnerekkefølge/nivaa3', methods=['GET', 'POST'])
@login_required
def regnerekkefolge_nivaa3_route():
    nummer = int(request.args.get("n", 1))
    total = len(regnerekkefolge_nivaa3)
    oppgave_id = 3000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Nivå 3 – Regnerekkefølge", melding="Du fullførte nivå 3! Monstersterkt 💪🔥")

    oppgave, fasit = regnerekkefolge_nivaa3[nummer - 1]
    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 3000 + i, "link": f"/oppgaver/Regnerekkefølge/nivaa3?n={i}"} for i in range(1, total + 1)]

    return render_template("regnerekkefolge_nivaa3.html",
        oppgave=oppgave, nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny,
        riktige_oppgaver=riktige_oppgaver,
        undertemaer=[
            {"navn": "Regnerekkefølge", "link": "/oppgaver/algebra/regnerekkefolge"},
            {"navn": "Likninger", "link": "/oppgaver/algebra/likninger"},
        ]
    )


# ─────────────────────────────────────────────
# HELE TALL
# ─────────────────────────────────────────────

@app.route('/oppgaver/hele_tall')
@login_required
def hele_tall():
    return render_template('oppgaver_hele_tall.html')


# HELE TALL NIVÅ 1 – addisjon og subtraksjon (ID 4001–4030)
hele_tall_nivaa1_oppgaver = [
    ("45 + 32", "77"), ("78 - 34", "44"), ("123 + 456", "579"),
    ("200 - 87", "113"), ("67 + 48", "115"), ("150 - 63", "87"),
    ("234 + 321", "555"), ("500 - 246", "254"), ("89 + 76", "165"),
    ("300 - 158", "142"), ("412 + 239", "651"), ("600 - 347", "253"),
    ("55 + 98", "153"), ("1000 - 432", "568"), ("178 + 265", "443"),
    ("750 - 389", "361"), ("64 + 87", "151"), ("900 - 564", "336"),
    ("345 + 278", "623"), ("400 - 173", "227"), ("56 + 99", "155"),
    ("800 - 425", "375"), ("167 + 384", "551"), ("250 - 138", "112"),
    ("93 + 47", "140"), ("700 - 312", "388"), ("428 + 195", "623"),
    ("550 - 264", "286"), ("72 + 58", "130"), ("1000 - 789", "211"),
]


@app.route('/oppgaver/Hele tall/nivaa1', methods=['GET', 'POST'])
@login_required
def hele_tall_nivaa1_route():
    oppgaver = hele_tall_nivaa1_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 4000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Hele tall – Nivå 1", melding="Du fullførte nivå 1! Bra jobba 🎉")

    oppgave, fasit = oppgaver[nummer - 1]
    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 4000 + i, "link": f"/oppgaver/Hele tall/nivaa1?n={i}"} for i in range(1, total + 1)]

    return render_template("hele_tall_nivaa1.html",
        oppgave=oppgave, nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny,
        riktige_oppgaver=riktige_oppgaver
    )


# HELE TALL NIVÅ 2 – multiplikasjon og divisjon (ID 5001–5030)
hele_tall_nivaa2_oppgaver = [
    ("7 ⋅ 8", "56"), ("63 : 9", "7"), ("12 ⋅ 11", "132"),
    ("144 : 12", "12"), ("6 ⋅ 15", "90"), ("120 : 8", "15"),
    ("9 ⋅ 13", "117"), ("196 : 14", "14"), ("8 ⋅ 17", "136"),
    ("225 : 15", "15"), ("14 ⋅ 12", "168"), ("252 : 18", "14"),
    ("7 ⋅ 19", "133"), ("288 : 16", "18"), ("13 ⋅ 14", "182"),
    ("315 : 21", "15"), ("11 ⋅ 16", "176"), ("324 : 18", "18"),
    ("6 ⋅ 23", "138"), ("360 : 24", "15"), ("15 ⋅ 13", "195"),
    ("416 : 16", "26"), ("9 ⋅ 21", "189"), ("480 : 20", "24"),
    ("8 ⋅ 24", "192"), ("504 : 21", "24"), ("17 ⋅ 12", "204"),
    ("532 : 28", "19"), ("7 ⋅ 26", "182"), ("600 : 25", "24"),
]


@app.route('/oppgaver/Hele tall/nivaa2', methods=['GET', 'POST'])
@login_required
def hele_tall_nivaa2_route():
    oppgaver = hele_tall_nivaa2_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 5000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Hele tall – Nivå 2", melding="Du fullførte nivå 2! Sterkt jobba 🔥")

    oppgave, fasit = oppgaver[nummer - 1]
    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 5000 + i, "link": f"/oppgaver/Hele tall/nivaa2?n={i}"} for i in range(1, total + 1)]

    return render_template("hele_tall_nivaa2.html",
        oppgave=oppgave, nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny,
        riktige_oppgaver=riktige_oppgaver
    )


# HELE TALL NIVÅ 3 – negative tall og blandede operasjoner (ID 6001–6030)
hele_tall_nivaa3_oppgaver = [
    ("-5 + 8", "3"), ("-12 + 7", "-5"), ("6 - (-4)", "10"),
    ("-9 - (-3)", "-6"), ("-7 ⋅ 4", "-28"), ("-6 ⋅ (-5)", "30"),
    ("(-36) : (-9)", "4"), ("(-48) : 6", "-8"), ("-15 + (-9)", "-24"),
    ("20 - (-13)", "33"), ("-8 ⋅ 7", "-56"), ("(-72) : (-8)", "9"),
    ("-23 + 45", "22"), ("(-11) ⋅ (-6)", "66"), ("-34 - (-18)", "-16"),
    ("(-90) : 9", "-10"), ("-17 + (-14)", "-31"), ("(-13) ⋅ 5", "-65"),
    ("(-84) : (-12)", "7"), ("38 - (-25)", "63"), ("-42 + 19", "-23"),
    ("(-15) ⋅ (-4)", "60"), ("(-96) : 8", "-12"), ("-28 - (-35)", "7"),
    ("-9 + (-16)", "-25"), ("(-14) ⋅ 6", "-84"), ("(-110) : (-11)", "10"),
    ("52 - (-48)", "100"), ("-33 + 17", "-16"), ("(-18) ⋅ (-5)", "90"),
]


@app.route('/oppgaver/Hele tall/nivaa3', methods=['GET', 'POST'])
@login_required
def hele_tall_nivaa3_route():
    oppgaver = hele_tall_nivaa3_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 6000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Hele tall – Nivå 3", melding="Du fullførte nivå 3! Monstersterkt 💪🔥")

    oppgave, fasit = oppgaver[nummer - 1]
    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 6000 + i, "link": f"/oppgaver/Hele tall/nivaa3?n={i}"} for i in range(1, total + 1)]

    return render_template("hele_tall_nivaa3.html",
        oppgave=oppgave, nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny,
        riktige_oppgaver=riktige_oppgaver
    )


# ─────────────────────────────────────────────
# DESIMALTALL
# ─────────────────────────────────────────────

@app.route('/oppgaver/desimaltall')
@login_required
def desimaltall():
    return render_template('oppgaver_desimaltall.html')


# DESIMALTALL NIVÅ 1 – addisjon og subtraksjon (ID 7001–7030)
desimaltall_nivaa1_oppgaver = [
    ("1,2 + 2,3", "3,5"), ("4,5 - 1,2", "3,3"), ("3,7 + 2,1", "5,8"),
    ("6,8 - 3,4", "3,4"), ("2,5 + 1,5", "4,0"), ("7,3 - 4,1", "3,2"),
    ("0,6 + 0,8", "1,4"), ("5,9 - 2,7", "3,2"), ("3,4 + 4,4", "7,8"),
    ("8,7 - 5,3", "3,4"), ("1,8 + 3,6", "5,4"), ("9,5 - 4,2", "5,3"),
    ("2,4 + 5,3", "7,7"), ("6,1 - 2,8", "3,3"), ("4,7 + 1,9", "6,6"),
    ("7,4 - 3,6", "3,8"), ("0,9 + 0,7", "1,6"), ("5,2 - 1,4", "3,8"),
    ("3,6 + 2,8", "6,4"), ("8,3 - 4,7", "3,6"), ("1,1 + 7,9", "9,0"),
    ("6,5 - 2,9", "3,6"), ("4,2 + 3,9", "8,1"), ("9,1 - 5,6", "3,5"),
    ("2,7 + 4,6", "7,3"), ("7,8 - 3,9", "3,9"), ("0,5 + 0,9", "1,4"),
    ("5,6 - 2,3", "3,3"), ("3,3 + 5,8", "9,1"), ("8,4 - 4,5", "3,9"),
]


@app.route('/oppgaver/Desimaltall/nivaa1', methods=['GET', 'POST'])
@login_required
def desimaltall_nivaa1_route():
    oppgaver = desimaltall_nivaa1_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 7000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Desimaltall – Nivå 1", melding="Du fullførte nivå 1! Bra jobba 🎉")

    oppgave, fasit = oppgaver[nummer - 1]
    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip().replace(".", ",")
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 7000 + i, "link": f"/oppgaver/Desimaltall/nivaa1?n={i}"} for i in range(1, total + 1)]
    return render_template("desimaltall_nivaa1.html",
        oppgave=oppgave, nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny,
        riktige_oppgaver=riktige_oppgaver
    )


# DESIMALTALL NIVÅ 2 – multiplikasjon og divisjon (ID 8001–8030)
desimaltall_nivaa2_oppgaver = [
    ("1,2 ⋅ 3", "3,6"), ("4,8 : 2", "2,4"), ("2,5 ⋅ 4", "10,0"),
    ("7,2 : 3", "2,4"), ("3,4 ⋅ 2", "6,8"), ("9,6 : 4", "2,4"),
    ("1,5 ⋅ 6", "9,0"), ("8,4 : 7", "1,2"), ("2,3 ⋅ 3", "6,9"),
    ("6,5 : 5", "1,3"), ("4,2 ⋅ 2", "8,4"), ("7,8 : 6", "1,3"),
    ("1,4 ⋅ 5", "7,0"), ("9,9 : 9", "1,1"), ("3,6 ⋅ 3", "10,8"),
    ("8,8 : 8", "1,1"), ("2,4 ⋅ 4", "9,6"), ("7,5 : 5", "1,5"),
    ("1,8 ⋅ 5", "9,0"), ("6,4 : 4", "1,6"), ("3,2 ⋅ 3", "9,6"),
    ("9,1 : 7", "1,3"), ("2,6 ⋅ 4", "10,4"), ("8,1 : 9", "0,9"),
    ("4,5 ⋅ 2", "9,0"), ("7,0 : 5", "1,4"), ("1,6 ⋅ 6", "9,6"),
    ("9,6 : 8", "1,2"), ("3,5 ⋅ 4", "14,0"), ("8,4 : 6", "1,4"),
]


@app.route('/oppgaver/Desimaltall/nivaa2', methods=['GET', 'POST'])
@login_required
def desimaltall_nivaa2_route():
    oppgaver = desimaltall_nivaa2_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 8000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Desimaltall – Nivå 2", melding="Du fullførte nivå 2! Sterkt jobba 🔥")

    oppgave, fasit = oppgaver[nummer - 1]
    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip().replace(".", ",")
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 8000 + i, "link": f"/oppgaver/Desimaltall/nivaa2?n={i}"} for i in range(1, total + 1)]
    return render_template("desimaltall_nivaa2.html",
        oppgave=oppgave, nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny,
        riktige_oppgaver=riktige_oppgaver
    )


# DESIMALTALL NIVÅ 3 – blandede operasjoner (ID 9001–9030)
desimaltall_nivaa3_oppgaver = [
    ("1,5 + 2,3 ⋅ 2", "6,1"), ("(3,2 + 1,8) ⋅ 2", "10,0"),
    ("4,8 : 2 + 1,6", "4,0"), ("(5,4 - 2,4) ⋅ 3", "9,0"),
    ("2,5 ⋅ 4 - 3,2", "6,8"), ("(1,6 + 2,4) : 2", "2,0"),
    ("6,3 - 1,2 ⋅ 3", "2,7"), ("(4,5 + 1,5) ⋅ 2", "12,0"),
    ("9,6 : 4 + 2,3", "4,7"), ("(7,2 - 3,2) : 2", "2,0"),
    ("3,4 ⋅ 2 + 1,8", "8,6"), ("(2,8 + 4,2) ⋅ 2", "14,0"),
    ("8,5 : 5 - 0,3", "1,4"), ("(6,0 - 2,4) ⋅ 3", "10,8"),
    ("1,2 ⋅ 5 + 2,4", "8,4"), ("(3,6 + 2,4) : 3", "2,0"),
    ("7,5 - 2,4 ⋅ 2", "2,7"), ("(5,6 + 1,4) ⋅ 2", "14,0"),
    ("9,0 : 6 + 3,5", "5,0"), ("(8,4 - 5,4) ⋅ 4", "12,0"),
    ("2,4 ⋅ 3 - 1,2", "6,0"), ("(1,8 + 5,2) ⋅ 2", "14,0"),
    ("6,6 : 3 + 2,8", "5,0"), ("(9,0 - 4,5) ⋅ 2", "9,0"),
    ("4,6 ⋅ 2 - 3,2", "6,0"), ("(2,4 + 3,6) : 2", "3,0"),
    ("5,4 - 1,2 ⋅ 3", "1,8"), ("(7,2 + 0,8) ⋅ 2", "16,0"),
    ("8,4 : 4 + 4,5", "6,6"), ("(6,3 - 3,3) ⋅ 5", "15,0"),
]


@app.route('/oppgaver/Desimaltall/nivaa3', methods=['GET', 'POST'])
@login_required
def desimaltall_nivaa3_route():
    oppgaver = desimaltall_nivaa3_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 9000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Desimaltall – Nivå 3", melding="Du fullførte nivå 3! Monstersterkt 💪🔥")

    oppgave, fasit = oppgaver[nummer - 1]
    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip().replace(".", ",")
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 9000 + i, "link": f"/oppgaver/Desimaltall/nivaa3?n={i}"} for i in range(1, total + 1)]
    return render_template("desimaltall_nivaa3.html",
        oppgave=oppgave, nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny,
        riktige_oppgaver=riktige_oppgaver
    )


# ─────────────────────────────────────────────
# PROSENT
# ─────────────────────────────────────────────

@app.route('/oppgaver/prosent')
@login_required
def prosent():
    return render_template('oppgaver_prosent.html')


# PROSENT NIVÅ 1 – finn prosenten av et tall (ID 10001–10030)
prosent_nivaa1_oppgaver = [
    ("Hva er 10% av 80?", "8"), ("Hva er 50% av 60?", "30"),
    ("Hva er 25% av 40?", "10"), ("Hva er 20% av 150?", "30"),
    ("Hva er 75% av 200?", "150"), ("Hva er 10% av 350?", "35"),
    ("Hva er 50% av 90?", "45"), ("Hva er 25% av 120?", "30"),
    ("Hva er 20% av 250?", "50"), ("Hva er 10% av 500?", "50"),
    ("Hva er 30% av 100?", "30"), ("Hva er 40% av 50?", "20"),
    ("Hva er 15% av 200?", "30"), ("Hva er 60% av 150?", "90"),
    ("Hva er 5% av 400?", "20"), ("Hva er 80% av 75?", "60"),
    ("Hva er 25% av 80?", "20"), ("Hva er 50% av 300?", "150"),
    ("Hva er 10% av 1000?", "100"), ("Hva er 20% av 400?", "80"),
    ("Hva er 30% av 200?", "60"), ("Hva er 75% av 400?", "300"),
    ("Hva er 40% av 250?", "100"), ("Hva er 5% av 600?", "30"),
    ("Hva er 15% av 300?", "45"), ("Hva er 60% av 500?", "300"),
    ("Hva er 25% av 160?", "40"), ("Hva er 10% av 750?", "75"),
    ("Hva er 50% av 480?", "240"), ("Hva er 20% av 600?", "120"),
]


@app.route('/oppgaver/Prosent/nivaa1', methods=['GET', 'POST'])
@login_required
def prosent_nivaa1_route():
    oppgaver = prosent_nivaa1_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 10000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Prosent – Nivå 1", melding="Du fullførte nivå 1! Bra jobba 🎉")

    oppgave, fasit = oppgaver[nummer - 1]
    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 10000 + i, "link": f"/oppgaver/Prosent/nivaa1?n={i}"} for i in range(1, total + 1)]
    return render_template("prosent_nivaa1.html",
        oppgave=oppgave, nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny,
        riktige_oppgaver=riktige_oppgaver
    )


# PROSENT NIVÅ 2 – finn hvor mange prosent (ID 11001–11030)
prosent_nivaa2_oppgaver = [
    ("Hvor mange prosent er 10 av 100?", "10"), ("Hvor mange prosent er 25 av 50?", "50"),
    ("Hvor mange prosent er 30 av 150?", "20"), ("Hvor mange prosent er 12 av 60?", "20"),
    ("Hvor mange prosent er 45 av 180?", "25"), ("Hvor mange prosent er 8 av 40?", "20"),
    ("Hvor mange prosent er 60 av 200?", "30"), ("Hvor mange prosent er 15 av 75?", "20"),
    ("Hvor mange prosent er 18 av 90?", "20"), ("Hvor mange prosent er 40 av 160?", "25"),
    ("Hvor mange prosent er 6 av 30?", "20"), ("Hvor mange prosent er 50 av 250?", "20"),
    ("Hvor mange prosent er 35 av 140?", "25"), ("Hvor mange prosent er 9 av 45?", "20"),
    ("Hvor mange prosent er 72 av 360?", "20"), ("Hvor mange prosent er 25 av 100?", "25"),
    ("Hvor mange prosent er 14 av 70?", "20"), ("Hvor mange prosent er 80 av 400?", "20"),
    ("Hvor mange prosent er 3 av 15?", "20"), ("Hvor mange prosent er 55 av 220?", "25"),
    ("Hvor mange prosent er 16 av 80?", "20"), ("Hvor mange prosent er 90 av 300?", "30"),
    ("Hvor mange prosent er 21 av 105?", "20"), ("Hvor mange prosent er 48 av 240?", "20"),
    ("Hvor mange prosent er 7 av 35?", "20"), ("Hvor mange prosent er 120 av 400?", "30"),
    ("Hvor mange prosent er 24 av 120?", "20"), ("Hvor mange prosent er 36 av 180?", "20"),
    ("Hvor mange prosent er 5 av 25?", "20"), ("Hvor mange prosent er 100 av 500?", "20"),
]


@app.route('/oppgaver/Prosent/nivaa2', methods=['GET', 'POST'])
@login_required
def prosent_nivaa2_route():
    oppgaver = prosent_nivaa2_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 11000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Prosent – Nivå 2", melding="Du fullførte nivå 2! Sterkt jobba 🔥")

    oppgave, fasit = oppgaver[nummer - 1]
    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip().replace("%", "")
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 11000 + i, "link": f"/oppgaver/Prosent/nivaa2?n={i}"} for i in range(1, total + 1)]
    return render_template("prosent_nivaa2.html",
        oppgave=oppgave, nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny,
        riktige_oppgaver=riktige_oppgaver
    )


# PROSENT NIVÅ 3 – prosentvis økning og nedgang (ID 12001–12030)
prosent_nivaa3_oppgaver = [
    ("En jakke koster 400 kr. Den er satt ned 25%. Hva er den nye prisen?", "300"),
    ("En sykkel koster 1000 kr. Den øker med 10%. Hva er den nye prisen?", "1100"),
    ("En telefon koster 800 kr. Den er satt ned 20%. Hva er den nye prisen?", "640"),
    ("En bok koster 200 kr. Den øker med 50%. Hva er den nye prisen?", "300"),
    ("En skjorte koster 300 kr. Den er satt ned 30%. Hva er den nye prisen?", "210"),
    ("En datamaskin koster 5000 kr. Den er satt ned 15%. Hva er den nye prisen?", "4250"),
    ("En bil koster 200 000 kr. Den øker med 5%. Hva er den nye prisen?", "210000"),
    ("Et klesplagg koster 600 kr. Den er satt ned 40%. Hva er den nye prisen?", "360"),
    ("En leilighet koster 2 000 000 kr. Den øker med 10%. Hva er den nye prisen?", "2200000"),
    ("En lampe koster 500 kr. Den er satt ned 10%. Hva er den nye prisen?", "450"),
    ("En restaurant øker prisene med 8%. En rett kostet 150 kr. Hva koster den nå?", "162"),
    ("En vare koster 250 kr. Den er satt ned 20%. Hva er den nye prisen?", "200"),
    ("En reise koster 3000 kr. Den øker med 15%. Hva er den nye prisen?", "3450"),
    ("En TV koster 2000 kr. Den er satt ned 25%. Hva er den nye prisen?", "1500"),
    ("En klubb øker kontingenten med 20%. Den kostet 500 kr. Hva koster den nå?", "600"),
    ("En genser koster 400 kr. Den er satt ned 50%. Hva er den nye prisen?", "200"),
    ("En leiepris øker med 12%. Den var 8000 kr. Hva er den nye leieprisen?", "8960"),
    ("En sko koster 900 kr. Den er satt ned 10%. Hva er den nye prisen?", "810"),
    ("En kurs koster 1200 kr. Den øker med 25%. Hva er den nye prisen?", "1500"),
    ("En bil koster 150 000 kr. Den er satt ned 30%. Hva er den nye prisen?", "105000"),
    ("En vare koster 80 kr. Den øker med 75%. Hva er den nye prisen?", "140"),
    ("Et abonnement koster 99 kr. Det øker med 10%. Hva koster det nå?", "108,9"),
    ("En hytte koster 1 500 000 kr. Den øker med 20%. Hva er den nye prisen?", "1800000"),
    ("En konsert koster 350 kr. Den er satt ned 20%. Hva er den nye prisen?", "280"),
    ("En kino koster 120 kr. Den øker med 25%. Hva er den nye prisen?", "150"),
    ("En sykkel koster 2500 kr. Den er satt ned 15%. Hva er den nye prisen?", "2125"),
    ("En avis koster 40 kr. Den øker med 50%. Hva er den nye prisen?", "60"),
    ("En dress koster 3000 kr. Den er satt ned 35%. Hva er den nye prisen?", "1950"),
    ("En gave koster 180 kr. Den øker med 10%. Hva er den nye prisen?", "198"),
    ("En stol koster 1200 kr. Den er satt ned 25%. Hva er den nye prisen?", "900"),
]


@app.route('/oppgaver/Prosent/nivaa3', methods=['GET', 'POST'])
@login_required
def prosent_nivaa3_route():
    oppgaver = prosent_nivaa3_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 12000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Prosent – Nivå 3", melding="Du fullførte nivå 3! Monstersterkt 💪🔥")

    oppgave, fasit = oppgaver[nummer - 1]
    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip().replace(" ", "").replace("kr", "").replace(",", ".")
        fasit_norm = fasit.replace(" ", "").replace(",", ".")
        if svar == fasit_norm:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 12000 + i, "link": f"/oppgaver/Prosent/nivaa3?n={i}"} for i in range(1, total + 1)]
    return render_template("prosent_nivaa3.html",
        oppgave=oppgave, nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny,
        riktige_oppgaver=riktige_oppgaver
    )


# ─────────────────────────────────────────────
# NEGATIVE TALL
# ─────────────────────────────────────────────

@app.route('/oppgaver/negative_tall')
@login_required
def negative_tall():
    return render_template('oppgaver_negative_tall.html')


# NEGATIVE TALL NIVÅ 1 – addisjon og subtraksjon (ID 13001–13030)
negative_tall_nivaa1_oppgaver = [
    ("-3 + 5", "2"), ("-7 + 3", "-4"), ("4 + (-6)", "-2"),
    ("-2 + (-5)", "-7"), ("8 - 11", "-3"), ("-4 - 3", "-7"),
    ("6 + (-9)", "-3"), ("-5 + 8", "3"), ("-1 - 6", "-7"),
    ("3 + (-8)", "-5"), ("-9 + 4", "-5"), ("2 - 10", "-8"),
    ("-6 + 6", "0"), ("5 + (-12)", "-7"), ("-3 - 5", "-8"),
    ("-11 + 7", "-4"), ("1 - 9", "-8"), ("-4 + (-4)", "-8"),
    ("7 + (-10)", "-3"), ("-8 + 3", "-5"), ("0 - 7", "-7"),
    ("-2 + (-9)", "-11"), ("6 - 14", "-8"), ("-5 + 9", "4"),
    ("-12 + 5", "-7"), ("3 - 13", "-10"), ("-7 + (-3)", "-10"),
    ("4 + (-11)", "-7"), ("-6 + 2", "-4"), ("-9 - 4", "-13"),
]


@app.route('/oppgaver/Negative tall/nivaa1', methods=['GET', 'POST'])
@login_required
def negative_tall_nivaa1_route():
    oppgaver = negative_tall_nivaa1_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 13000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Negative tall – Nivå 1", melding="Du fullførte nivå 1! Bra jobba 🎉")

    oppgave, fasit = oppgaver[nummer - 1]
    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 13000 + i, "link": f"/oppgaver/Negative tall/nivaa1?n={i}"} for i in range(1, total + 1)]
    return render_template("negative_tall_nivaa1.html",
        oppgave=oppgave, nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny,
        riktige_oppgaver=riktige_oppgaver
    )


# NEGATIVE TALL NIVÅ 2 – multiplikasjon og divisjon (ID 14001–14030)
negative_tall_nivaa2_oppgaver = [
    ("-3 ⋅ 4", "-12"), ("(-5) ⋅ 2", "-10"), ("(-6) ⋅ (-3)", "18"),
    ("4 ⋅ (-7)", "-28"), ("(-8) ⋅ 3", "-24"), ("(-4) ⋅ (-5)", "20"),
    ("(-12) : 4", "-3"), ("20 : (-5)", "-4"), ("(-18) : (-6)", "3"),
    ("(-9) ⋅ 4", "-36"), ("(-15) : 3", "-5"), ("(-7) ⋅ (-6)", "42"),
    ("(-24) : 8", "-3"), ("6 ⋅ (-9)", "-54"), ("(-36) : (-4)", "9"),
    ("(-11) ⋅ 3", "-33"), ("(-40) : 5", "-8"), ("(-8) ⋅ (-7)", "56"),
    ("(-30) : (-6)", "5"), ("(-5) ⋅ 9", "-45"), ("(-56) : 7", "-8"),
    ("(-12) ⋅ (-4)", "48"), ("(-63) : 9", "-7"), ("(-6) ⋅ 11", "-66"),
    ("(-48) : (-8)", "6"), ("(-13) ⋅ 3", "-39"), ("(-72) : 8", "-9"),
    ("(-9) ⋅ (-9)", "81"), ("(-100) : (-5)", "20"), ("(-14) ⋅ 4", "-56"),
]


@app.route('/oppgaver/Negative tall/nivaa2', methods=['GET', 'POST'])
@login_required
def negative_tall_nivaa2_route():
    oppgaver = negative_tall_nivaa2_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 14000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Negative tall – Nivå 2", melding="Du fullførte nivå 2! Sterkt jobba 🔥")

    oppgave, fasit = oppgaver[nummer - 1]
    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 14000 + i, "link": f"/oppgaver/Negative tall/nivaa2?n={i}"} for i in range(1, total + 1)]
    return render_template("negative_tall_nivaa2.html",
        oppgave=oppgave, nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny,
        riktige_oppgaver=riktige_oppgaver
    )


# NEGATIVE TALL NIVÅ 3 – blandede og sammensatte uttrykk (ID 15001–15030)
negative_tall_nivaa3_oppgaver = [
    ("-3 + 4 ⋅ (-2)", "-11"), ("(-6 + 2) ⋅ 3", "-12"),
    ("5 - (-3) ⋅ 2", "11"), ("(-4) ⋅ (-3) - 8", "4"),
    ("(-20) : 4 + (-3)", "-8"), ("3 ⋅ (-5) + 9", "-6"),
    ("(-2 + 8) ⋅ (-3)", "-18"), ("(-16) : (-4) - 7", "-3"),
    ("-7 + (-3) ⋅ (-4)", "5"), ("(5 - 9) ⋅ (-6)", "24"),
    ("(-24) : 6 + (-5)", "-9"), ("(-3) ⋅ 4 - (-6)", "-6"),
    ("(-8 + 3) ⋅ (-4)", "20"), ("2 ⋅ (-7) + (-4)", "-18"),
    ("(-35) : (-5) - 12", "-5"), ("(-6) ⋅ (-3) + (-10)", "8"),
    ("(−4 − 6) : (−2)", "5"), ("−5 ⋅ (3 − 7)", "20"),
    ("(-9) ⋅ 2 - (-4)", "-14"), ("(-15 + 6) : (-3)", "3"),
    ("4 ⋅ (-8) + (-6)", "-38"), ("(-3 + 7) ⋅ (-5)", "-20"),
    ("(-42) : 7 - (-8)", "2"), ("(-5) ⋅ (-4) - 30", "-10"),
    ("(-2 - 4) ⋅ (-7)", "42"), ("(-8) ⋅ 3 + (-4)", "-28"),
    ("(-36) : (-9) + (-8)", "-4"), ("(-7 + 2) ⋅ (-6)", "30"),
    ("3 ⋅ (-9) - (-15)", "-12"), ("(-4) ⋅ (-5) + (-25)", "-5"),
]


@app.route('/oppgaver/Negative tall/nivaa3', methods=['GET', 'POST'])
@login_required
def negative_tall_nivaa3_route():
    oppgaver = negative_tall_nivaa3_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 15000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Negative tall – Nivå 3", melding="Du fullførte nivå 3! Monstersterkt 💪🔥")

    oppgave, fasit = oppgaver[nummer - 1]
    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 15000 + i, "link": f"/oppgaver/Negative tall/nivaa3?n={i}"} for i in range(1, total + 1)]
    return render_template("negative_tall_nivaa3.html",
        oppgave=oppgave, nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny,
        riktige_oppgaver=riktige_oppgaver
    )


# ─────────────────────────────────────────────
# BRØK
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
# BRØK
# ─────────────────────────────────────────────

@app.route('/oppgaver/brok')
@login_required
def brok():
    return render_template('oppgaver_brok.html')


def b(t, n):
    """Lag HTML for én brøk."""
    return f'<span class="inline-brok"><span class="ib-t">{t}</span><span class="ib-s"></span><span class="ib-n">{n}</span></span>'


def sjekk_brok(t_svar, n_svar, t_fasit, n_fasit):
    try:
        t = int(str(t_svar).strip())
        n = int(str(n_svar).strip())
        tf = int(t_fasit)
        nf = int(n_fasit)
        if n == 0 or nf == 0:
            return False
        return t * nf == tf * n
    except:
        return False


def sjekk_flervalg(svar_str, t_fasit, n_fasit):
    try:
        deler = svar_str.split("/")
        return sjekk_brok(deler[0], deler[1], t_fasit, n_fasit)
    except:
        return False


# ── NIVÅ 1: Forkorting og grunnleggende brøkforståelse ──
# type: "skriv" = teller/nevner input, "flervalg" = 4 alternativer, "tekst" = tekstoppgave med skriv
# Format: (type, oppgave_tekst, oppgave_html, teller_fasit, nevner_fasit, alternativer_eller_None)

def _fv(riktig_t, riktig_n, gale):
    """Lag flervalg-alternativer: riktig + 3 gale, blandet."""
    import random
    alts = [{"t": riktig_t, "n": riktig_n}] + [{"t": g[0], "n": g[1]} for g in gale]
    random.shuffle(alts)
    return alts


brok_nivaa1_oppgaver = [
    # --- FORKORT ---
    ("skriv", "Forkort brøken:", f'Forkort brøken: {b(2,4)}', "1", "2", None),
    ("skriv", "Forkort brøken:", f'Forkort brøken: {b(3,9)}', "1", "3", None),
    ("flervalg", "", f'Forkort brøken: {b(4,8)}', "1", "2", [("2","4"),("3","4"),("1","4")]),
    ("skriv", "Forkort brøken:", f'Forkort brøken: {b(6,12)}', "1", "2", None),
    ("flervalg", "", f'Forkort brøken: {b(4,6)}', "2", "3", [("1","2"),("3","4"),("1","3")]),
    ("skriv", "Forkort brøken:", f'Forkort brøken: {b(6,9)}', "2", "3", None),
    ("flervalg", "", f'Forkort brøken: {b(8,12)}', "2", "3", [("4","6"),("3","4"),("1","2")]),
    ("skriv", "Forkort brøken:", f'Forkort brøken: {b(6,8)}', "3", "4", None),
    ("flervalg", "", f'Forkort brøken: {b(10,15)}', "2", "3", [("1","2"),("3","5"),("5","8")]),
    ("skriv", "Forkort brøken:", f'Forkort brøken: {b(4,10)}', "2", "5", None),
    # --- TEKST ---
    ("tekst", "En pizza er delt i 8 like deler. Kari spiser 4 deler. Hvilken brøk av pizzaen spiste Kari? Forkort svaret.", "", "1", "2", None),
    ("tekst", "En sjokolade har 12 biter. Jonas spiser 6 biter. Hvilken forkortet brøk er dette?", "", "1", "2", None),
    ("flervalg", "", f'Forkort brøken: {b(9,12)}', "3", "4", [("2","3"),("1","2"),("6","8")]),
    ("skriv", "Forkort brøken:", f'Forkort brøken: {b(10,20)}', "1", "2", None),
    ("tekst", "En klasse har 30 elever. 10 elever er borte. Hvilken forkortet brøk av klassen er borte?", "", "1", "3", None),
    ("flervalg", "", f'Forkort brøken: {b(12,16)}', "3", "4", [("2","3"),("6","8"),("1","2")]),
    ("skriv", "Forkort brøken:", f'Forkort brøken: {b(15,20)}', "3", "4", None),
    ("flervalg", "", f'Forkort brøken: {b(6,15)}', "2", "5", [("1","3"),("3","7"),("4","9")]),
    ("skriv", "Forkort brøken:", f'Forkort brøken: {b(12,18)}', "2", "3", None),
    ("tekst", "En flaske er 3/4 full. Skriv dette som en forkortet brøk (den er allerede forkortet — hva er telleren?)", "", "3", "4", None),
    ("flervalg", "", f'Forkort brøken: {b(14,21)}', "2", "3", [("7","10"),("1","2"),("3","4")]),
    ("skriv", "Forkort brøken:", f'Forkort brøken: {b(10,25)}', "2", "5", None),
    ("flervalg", "", f'Forkort brøken: {b(16,24)}', "2", "3", [("3","4"),("4","6"),("1","2")]),
    ("skriv", "Forkort brøken:", f'Forkort brøken: {b(20,30)}', "2", "3", None),
    ("tekst", "En dag har 24 timer. Du sover 8 timer. Hvilken forkortet brøk av dagen sover du?", "", "1", "3", None),
    ("flervalg", "", f'Forkort brøken: {b(25,100)}', "1", "4", [("2","5"),("1","2"),("5","20")]),
    ("skriv", "Forkort brøken:", f'Forkort brøken: {b(75,100)}', "3", "4", None),
    ("flervalg", "", f'Forkort brøken: {b(50,100)}', "1", "2", [("5","10"),("2","4"),("1","4")]),
    ("tekst", "En butikk har 100 varer. 25 er på salg. Hvilken forkortet brøk er på salg?", "", "1", "4", None),
    ("skriv", "Forkort brøken:", f'Forkort brøken: {b(21,28)}', "3", "4", None),
]


@app.route('/oppgaver/Brøker/nivaa1', methods=['GET', 'POST'])
@login_required
def brok_nivaa1_route():
    oppgaver = brok_nivaa1_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 16000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Brøker – Nivå 1", melding="Du fullførte nivå 1! Bra jobba 🎉")

    o = oppgaver[nummer - 1]
    type_, oppgave_tekst, oppgave_html, tf, nf, gale = o

    alternativer = _fv(tf, nf, gale) if type_ == "flervalg" else []
    if not oppgave_html:
        oppgave_html = f'<p class="task-question-text">{oppgave_tekst}</p>'

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        if type_ == "flervalg":
            svar = request.form.get("svar_flervalg", "")
            ok = sjekk_flervalg(svar, tf, nf)
        else:
            ts = request.form.get("teller", "").strip()
            ns = request.form.get("nevner", "").strip()
            ok = sjekk_brok(ts, ns, tf, nf)
            if ts == "67" or ns == "67":
                resultat = "🤡🤮 Du er ikke morsom 🖕"
                ok = False

        if ok:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif not resultat:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 16000 + i, "link": f"/oppgaver/Brøker/nivaa1?n={i}"} for i in range(1, total + 1)]
    return render_template("brok_nivaa1.html",
        oppgave=oppgave_tekst, oppgave_html=oppgave_html,
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        fasit_teller=tf, fasit_nevner=nf,
        oppgave_nummer=nummer, oppgaver=venstre_meny,
        riktige_oppgaver=riktige_oppgaver
    )


# ── NIVÅ 2: Addisjon og subtraksjon av brøker ──
brok_nivaa2_oppgaver = [
    ("skriv", "", f'Regn ut: {b(1,4)} + {b(1,4)} =', "2", "4", None),
    ("skriv", "", f'Regn ut: {b(2,5)} + {b(1,5)} =', "3", "5", None),
    ("flervalg", "", f'Regn ut: {b(3,8)} + {b(2,8)} =', "5", "8", [("1","2"),("6","8"),("4","8")]),
    ("skriv", "", f'Regn ut: {b(3,4)} - {b(1,4)} =', "2", "4", None),
    ("flervalg", "", f'Regn ut: {b(4,5)} - {b(2,5)} =', "2", "5", [("1","5"),("3","5"),("6","10")]),
    ("skriv", "", f'Regn ut: {b(1,2)} + {b(1,4)} =', "3", "4", None),
    ("flervalg", "", f'Regn ut: {b(1,3)} + {b(1,6)} =', "3", "6", [("2","9"),("1","2"),("4","6")]),
    ("skriv", "", f'Regn ut: {b(2,3)} + {b(1,6)} =', "5", "6", None),
    ("flervalg", "", f'Regn ut: {b(3,4)} + {b(1,8)} =', "7", "8", [("4","12"),("1","2"),("5","8")]),
    ("skriv", "", f'Regn ut: {b(1,2)} - {b(1,4)} =', "1", "4", None),
    ("tekst", "Emma spiser 2/8 av en kake, og Lena spiser 3/8. Hvor stor del av kaken er spist til sammen?", "", "5", "8", None),
    ("flervalg", "", f'Regn ut: {b(2,3)} - {b(1,6)} =', "3", "6", [("1","3"),("1","6"),("4","6")]),
    ("skriv", "", f'Regn ut: {b(3,4)} - {b(1,8)} =', "5", "8", None),
    ("flervalg", "", f'Regn ut: {b(5,6)} - {b(1,3)} =', "3", "6", [("4","6"),("2","3"),("1","2")]),
    ("tekst", "En beholder er 3/4 full. Du tar ut 1/8 av beholderen. Hvor mye er igjen?", "", "5", "8", None),
    ("skriv", "", f'Regn ut: {b(1,2)} + {b(1,6)} =', "4", "6", None),
    ("flervalg", "", f'Regn ut: {b(1,4)} + {b(3,8)} =', "5", "8", [("4","12"),("2","8"),("1","2")]),
    ("skriv", "", f'Regn ut: {b(5,8)} - {b(1,4)} =', "3", "8", None),
    ("flervalg", "", f'Regn ut: {b(7,10)} - {b(2,5)} =', "3", "10", [("5","5"),("1","2"),("4","10")]),
    ("tekst", "Ole løper 1/3 av en runde, så løper han 2/9 til. Hvor stor del av runden har han løpt?", "", "5", "9", None),
    ("skriv", "", f'Regn ut: {b(1,3)} + {b(2,9)} =', "5", "9", None),
    ("flervalg", "", f'Regn ut: {b(5,9)} - {b(1,3)} =', "2", "9", [("4","9"),("1","3"),("6","9")]),
    ("skriv", "", f'Regn ut: {b(3,4)} + {b(1,12)} =', "10", "12", None),
    ("flervalg", "", f'Regn ut: {b(2,5)} + {b(3,10)} =', "7", "10", [("5","15"),("1","2"),("6","10")]),
    ("tekst", "En strikk er 9/10 meter. Du klipper av 2/5 meter. Hvor mye er igjen?", "", "5", "10", None),
    ("skriv", "", f'Regn ut: {b(9,10)} - {b(2,5)} =', "5", "10", None),
    ("flervalg", "", f'Regn ut: {b(1,6)} + {b(5,12)} =', "7", "12", [("6","18"),("1","2"),("3","12")]),
    ("skriv", "", f'Regn ut: {b(11,12)} - {b(1,4)} =', "8", "12", None),
    ("flervalg", "", f'Regn ut: {b(3,8)} + {b(1,4)} =', "5", "8", [("4","12"),("2","8"),("6","8")]),
    ("tekst", "En tank er 7/12 full. Det lekker ut 1/6. Hvor mye er igjen i tanken?", "", "5", "12", None),
]


@app.route('/oppgaver/Brøker/nivaa2', methods=['GET', 'POST'])
@login_required
def brok_nivaa2_route():
    oppgaver = brok_nivaa2_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 17000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Brøker – Nivå 2", melding="Du fullførte nivå 2! Sterkt jobba 🔥")

    o = oppgaver[nummer - 1]
    type_, oppgave_tekst, oppgave_html, tf, nf, gale = o

    alternativer = _fv(tf, nf, gale) if type_ == "flervalg" else []
    if not oppgave_html:
        oppgave_html = f'<p class="task-question-text">{oppgave_tekst}</p>'

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        if type_ == "flervalg":
            svar = request.form.get("svar_flervalg", "")
            ok = sjekk_flervalg(svar, tf, nf)
        else:
            ts = request.form.get("teller", "").strip()
            ns = request.form.get("nevner", "").strip()
            ok = sjekk_brok(ts, ns, tf, nf)
            if ts == "67" or ns == "67":
                resultat = "🤡🤮 Du er ikke morsom 🖕"
                ok = False

        if ok:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif not resultat:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 17000 + i, "link": f"/oppgaver/Brøker/nivaa2?n={i}"} for i in range(1, total + 1)]
    return render_template("brok_nivaa2.html",
        oppgave=oppgave_tekst, oppgave_html=oppgave_html,
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        fasit_teller=tf, fasit_nevner=nf,
        oppgave_nummer=nummer, oppgaver=venstre_meny,
        riktige_oppgaver=riktige_oppgaver
    )


# ── NIVÅ 3: Multiplikasjon og divisjon av brøker ──
brok_nivaa3_oppgaver = [
    ("skriv", "", f'Regn ut: {b(1,2)} · {b(1,3)} =', "1", "6", None),
    ("flervalg", "", f'Regn ut: {b(2,3)} · {b(3,4)} =', "6", "12", [("5","7"),("2","4"),("3","8")]),
    ("skriv", "", f'Regn ut: {b(3,4)} · {b(2,5)} =', "6", "20", None),
    ("flervalg", "", f'Regn ut: {b(4,5)} · {b(5,8)} =', "20", "40", [("9","13"),("1","3"),("8","25")]),
    ("tekst", "En oppskrift bruker 2/3 av en pakke mel. Du lager halvparten av oppskriften. Hvor mye mel bruker du?", "", "1", "3", None),
    ("skriv", "", f'Regn ut: {b(1,2)} ÷ {b(1,4)} =', "4", "2", None),
    ("flervalg", "", f'Regn ut: {b(2,3)} ÷ {b(1,3)} =', "6", "3", [("2","9"),("3","2"),("1","2")]),
    ("skriv", "", f'Regn ut: {b(3,4)} ÷ {b(3,8)} =', "24", "12", None),
    ("flervalg", "", f'Regn ut: {b(5,6)} · {b(3,10)} =', "15", "60", [("8","16"),("2","5"),("1","4")]),
    ("tekst", "En snekker har 3/4 meter bord. Han kapper det i biter på 3/8 meter. Hvor mange biter får han?", "", "2", "1", None),
    ("skriv", "", f'Regn ut: {b(2,5)} · {b(5,6)} =', "10", "30", None),
    ("flervalg", "", f'Regn ut: {b(4,5)} ÷ {b(2,5)} =', "20", "10", [("2","25"),("6","5"),("8","10")]),
    ("skriv", "", f'Regn ut: {b(5,6)} ÷ {b(5,12)} =', "60", "30", None),
    ("flervalg", "", f'Regn ut: {b(7,8)} · {b(4,7)} =', "28", "56", [("11","15"),("3","7"),("4","8")]),
    ("tekst", "En beholder rommer 5/6 liter. Du fyller 2/3 av beholderen. Hvor mange liter er i beholderen?", "", "10", "18", None),
    ("skriv", "", f'Regn ut: {b(1,3)} ÷ {b(1,6)} =', "6", "3", None),
    ("flervalg", "", f'Regn ut: {b(3,7)} · {b(7,9)} =', "21", "63", [("10","16"),("1","3"),("6","7")]),
    ("skriv", "", f'Regn ut: {b(2,9)} · {b(3,4)} =', "6", "36", None),
    ("flervalg", "", f'Regn ut: {b(3,8)} ÷ {b(3,4)} =', "12", "24", [("9","32"),("1","2"),("6","12")]),
    ("tekst", "Du har 4/5 kg sukker. Du bruker 1/2 av det til en kake. Hvor mye sukker bruker du?", "", "4", "10", None),
    ("skriv", "", f'Regn ut: {b(5,7)} · {b(7,10)} =', "35", "70", None),
    ("flervalg", "", f'Regn ut: {b(6,7)} ÷ {b(3,14)} =', "84", "21", [("18","98"),("2","1"),("9","14")]),
    ("skriv", "", f'Regn ut: {b(5,9)} · {b(3,10)} =', "15", "90", None),
    ("flervalg", "", f'Regn ut: {b(9,10)} · {b(5,3)} =', "45", "30", [("14","13"),("3","2"),("4","5")]),
    ("tekst", "En løper fullfører 3/4 av et løp på 5/6 time. Hvor lang tid bruker han på hele løpet? (5/6 ÷ 3/4)", "", "20", "18", None),
    ("skriv", "", f'Regn ut: {b(4,11)} · {b(11,8)} =', "44", "88", None),
    ("flervalg", "", f'Regn ut: {b(5,8)} ÷ {b(15,16)} =', "80", "120", [("75","128"),("1","2"),("16","24")]),
    ("skriv", "", f'Regn ut: {b(7,12)} ÷ {b(7,6)} =', "42", "84", None),
    ("flervalg", "", f'Regn ut: {b(2,3)} ÷ {b(8,9)} =', "18", "24", [("16","27"),("3","4"),("6","9")]),
    ("tekst", "En fabrikk produserer 5/6 tonn om dagen. Hvor mye produserer den på 3/4 dag?", "", "15", "24", None),
]


@app.route('/oppgaver/Brøker/nivaa3', methods=['GET', 'POST'])
@login_required
def brok_nivaa3_route():
    oppgaver = brok_nivaa3_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 18000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Brøker – Nivå 3", melding="Du fullførte nivå 3! Monstersterkt 💪🔥")

    o = oppgaver[nummer - 1]
    type_, oppgave_tekst, oppgave_html, tf, nf, gale = o

    alternativer = _fv(tf, nf, gale) if type_ == "flervalg" else []
    if not oppgave_html:
        oppgave_html = f'<p class="task-question-text">{oppgave_tekst}</p>'

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        if type_ == "flervalg":
            svar = request.form.get("svar_flervalg", "")
            ok = sjekk_flervalg(svar, tf, nf)
        else:
            ts = request.form.get("teller", "").strip()
            ns = request.form.get("nevner", "").strip()
            ok = sjekk_brok(ts, ns, tf, nf)
            if ts == "67" or ns == "67":
                resultat = "🤡🤮 Du er ikke morsom 🖕"
                ok = False

        if ok:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif not resultat:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 18000 + i, "link": f"/oppgaver/Brøker/nivaa3?n={i}"} for i in range(1, total + 1)]
    return render_template("brok_nivaa3.html",
        oppgave=oppgave_tekst, oppgave_html=oppgave_html,
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total,
        resultat=resultat, riktig=riktig,
        fasit_teller=tf, fasit_nevner=nf,
        oppgave_nummer=nummer, oppgaver=venstre_meny,
        riktige_oppgaver=riktige_oppgaver
    )



# ─────────────────────────────────────────────
# POTENSER (ENKLE)
# ─────────────────────────────────────────────

@app.route('/oppgaver/potenser')
@login_required
def potenser():
    return render_template('oppgaver_potenser.html')


def p(base, exp):
    """Lag HTML for potens med superscript."""
    return f'<span class="pot-uttrykk">{base}<sup>{exp}</sup></span>'


def _fv_tall(riktig, gale):
    """Flervalg med enkle tall."""
    import random
    alts = [riktig] + gale
    random.shuffle(alts)
    return alts


# Format: (type, oppgave_html, fasit, alternativer_eller_None)
# type: "skriv" | "flervalg" | "tekst"

# POTENSER NIVÅ 1 – enkle potenser, kvadrattall (ID 19001–19030)
potenser_nivaa1_oppgaver = [
    ("skriv",   f'Regn ut: {p(2,2)} =', "4", None),
    ("skriv",   f'Regn ut: {p(3,2)} =', "9", None),
    ("flervalg",f'Regn ut: {p(4,2)} =', "16", ["8", "12", "20"]),
    ("skriv",   f'Regn ut: {p(5,2)} =', "25", None),
    ("flervalg",f'Regn ut: {p(6,2)} =', "36", ["12", "30", "42"]),
    ("skriv",   f'Regn ut: {p(7,2)} =', "49", None),
    ("flervalg",f'Regn ut: {p(8,2)} =', "64", ["16", "48", "72"]),
    ("skriv",   f'Regn ut: {p(9,2)} =', "81", None),
    ("flervalg",f'Regn ut: {p(10,2)} =', "100", ["20", "50", "110"]),
    ("skriv",   f'Regn ut: {p(2,3)} =', "8", None),
    ("flervalg",f'Regn ut: {p(3,3)} =', "27", ["9", "18", "33"]),
    ("skriv",   f'Regn ut: {p(2,4)} =', "16", None),
    ("flervalg",f'Regn ut: {p(2,5)} =', "32", ["10", "25", "16"]),
    ("skriv",   f'Regn ut: {p(10,3)} =', "1000", None),
    ("flervalg",f'Regn ut: {p(1,10)} =', "1", ["10", "100", "0"]),
    ("tekst",   'Et kvadrat har sidelengde 7 cm. Hva er arealet? (Areal = side²)', "49", None),
    ("flervalg",f'Regn ut: {p(4,3)} =', "64", ["12", "16", "48"]),
    ("skriv",   f'Regn ut: {p(5,3)} =', "125", None),
    ("flervalg",f'Regn ut: {p(11,2)} =', "121", ["22", "111", "132"]),
    ("tekst",   'Et kvadrat har sidelengde 9 cm. Hva er arealet?', "81", None),
    ("skriv",   f'Regn ut: {p(12,2)} =', "144", None),
    ("flervalg",f'Regn ut: {p(3,4)} =', "81", ["12", "64", "27"]),
    ("tekst",   f'Hva er {p(2,6)} ?', "64", None),
    ("flervalg",f'Hva er {p(10,4)} ?', "10000", ["1000", "40", "100000"]),
    ("skriv",   f'Regn ut: {p(6,3)} =', "216", None),
    ("flervalg",f'Regn ut: {p(0,5)} =', "0", ["1", "5", "0,5"]),
    ("tekst",   'Et rom er 5 m langt og 5 m bredt. Hva er gulvarealet?', "25", None),
    ("flervalg",f'Regn ut: {p(13,2)} =', "169", ["26", "130", "196"]),
    ("skriv",   f'Regn ut: {p(2,8)} =', "256", None),
    ("flervalg",f'Regn ut: {p(15,2)} =', "225", ["30", "150", "250"]),
]


@app.route('/oppgaver/Potenser (enkle)/nivaa1', methods=['GET', 'POST'])
@login_required
def potenser_nivaa1_route():
    oppgaver = potenser_nivaa1_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 19000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Potenser – Nivå 1", melding="Du fullførte nivå 1! Bra jobba 🎉")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        if type_ == "flervalg":
            svar = request.form.get("svar_flervalg", "").strip()
        else:
            svar = request.form.get("svar", "").strip()

        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 19000 + i, "link": f"/oppgaver/Potenser (enkle)/nivaa1?n={i}"} for i in range(1, total + 1)]
    return render_template("potenser_nivaa1.html",
        oppgave_html=oppgave_html, type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )


# POTENSER NIVÅ 2 – kubikktall, større eksponenter, sammenligning (ID 20001–20030)
potenser_nivaa2_oppgaver = [
    ("skriv",   f'Regn ut: {p(2,7)} =', "128", None),
    ("flervalg",f'Regn ut: {p(3,5)} =', "243", ["125", "15", "81"]),
    ("skriv",   f'Regn ut: {p(4,4)} =', "256", None),
    ("flervalg",f'Regn ut: {p(5,4)} =', "625", ["100", "500", "125"]),
    ("tekst",   f'En kube har sidelengde 4 cm. Hva er volumet? (Volum = side³)', "64", None),
    ("skriv",   f'Regn ut: {p(6,4)} =', "1296", None),
    ("flervalg",f'Regn ut: {p(2,10)} =', "1024", ["512", "20", "2048"]),
    ("tekst",   f'En kube har sidelengde 5 cm. Hva er volumet?', "125", None),
    ("flervalg",f'Hva er større: {p(3,4)} eller {p(4,3)}?', "81", ["64", "De er like", "Vet ikke"]),
    ("skriv",   f'Regn ut: {p(7,3)} =', "343", None),
    ("flervalg",f'Regn ut: {p(8,3)} =', "512", ["24", "256", "384"]),
    ("tekst",   f'En kube har sidelengde 3 cm. Hva er volumet?', "27", None),
    ("skriv",   f'Regn ut: {p(9,3)} =', "729", None),
    ("flervalg",f'Regn ut: {p(10,5)} =', "100000", ["50000", "10000", "1000000"]),
    ("skriv",   f'Regn ut: {p(2,9)} =', "512", None),
    ("flervalg",f'Hva er {p(4,5)} ?', "1024", ["20", "512", "2048"]),
    ("tekst",   f'Et skakbrett har 8 rader med 8 felt. Hvor mange felt er det totalt? (Skriv som potens og regn ut)', "64", None),
    ("flervalg",f'Regn ut: {p(5,5)} =', "3125", ["625", "25", "1000"]),
    ("skriv",   f'Regn ut: {p(3,6)} =', "729", None),
    ("flervalg",f'Hva er {p(6,3)} ?', "216", ["18", "63", "108"]),
    ("tekst",   f'En datamaskin lagrer 2¹⁰ filer. Hvor mange filer er det?', "1024", None),
    ("flervalg",f'Regn ut: {p(2,6)} + {p(2,5)} =', "96", ["32", "64", "128"]),
    ("skriv",   f'Regn ut: {p(11,3)} =', "1331", None),
    ("flervalg",f'Hva er {p(12,3)} ?', "1728", ["36", "864", "144"]),
    ("tekst",   f'Et rektangel har sider {p(3,2)} cm og {p(2,3)} cm. Hva er arealet?', "72", None),
    ("skriv",   f'Regn ut: {p(4,4)} + {p(3,3)} =', "283", None),
    ("flervalg",f'Regn ut: {p(5,3)} - {p(4,3)} =', "61", ["0", "1", "125"]),
    ("tekst",   f'En by dobler befolkningen sin hvert tiår. Hvis den nå har 1000 innbyggere, hvor mange har den etter 3 tiår? (1000 · {p(2,3)})', "8000", None),
    ("flervalg",f'Hva er {p(2,3)} · {p(2,3)} ?', "64", ["12", "32", "16"]),
    ("skriv",   f'Regn ut: {p(10,6)} =', "1000000", None),
]


@app.route('/oppgaver/Potenser (enkle)/nivaa2', methods=['GET', 'POST'])
@login_required
def potenser_nivaa2_route():
    oppgaver = potenser_nivaa2_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 20000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Potenser – Nivå 2", melding="Du fullførte nivå 2! Sterkt jobba 🔥")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        if type_ == "flervalg":
            svar = request.form.get("svar_flervalg", "").strip()
        else:
            svar = request.form.get("svar", "").strip()

        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 20000 + i, "link": f"/oppgaver/Potenser (enkle)/nivaa2?n={i}"} for i in range(1, total + 1)]
    return render_template("potenser_nivaa2.html",
        oppgave_html=oppgave_html, type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )


# POTENSER NIVÅ 3 – potensregler, blandede uttrykk, sammensatte tekstoppgaver (ID 21001–21030)
potenser_nivaa3_oppgaver = [
    ("flervalg",f'Regn ut: {p(2,3)} · {p(2,2)} =', "32", ["10", "64", "16"]),
    ("skriv",   f'Regn ut: {p(3,2)} + {p(4,2)} + {p(5,2)} =', "50", None),
    ("flervalg",f'{p(2,5)} : {p(2,3)} =', "4", ["2", "8", "16"]),
    ("tekst",   f'En kvadratisk hage har areal 144 m². Hva er sidelengden? (Hint: hva i andre potens gir 144?)', "12", None),
    ("flervalg",f'Regn ut: ({p(2,3)})² =', "64", ["32", "16", "512"]),
    ("skriv",   f'Regn ut: {p(2,4)} · {p(3,2)} =', "144", None),
    ("flervalg",f'Hva er {p(10,3)} + {p(10,2)} + 10 ?', "1110", ["111", "10000", "1100"]),
    ("tekst",   f'En kube har volum 216 cm³. Hva er sidelengden? (Hint: hva i tredje potens gir 216?)', "6", None),
    ("flervalg",f'Regn ut: {p(5,2)} · {p(2,3)} =', "200", ["80", "400", "100"]),
    ("skriv",   f'Regn ut: {p(2,6)} - {p(2,5)} =', "32", None),
    ("flervalg",f'Regn ut: {p(4,3)} : {p(2,3)} =', "8", ["4", "2", "16"]),
    ("tekst",   f'Befolkningen i en by tredobles hvert år. Etter 4 år er den 1 · {p(3,4)}. Regn ut.', "81", None),
    ("skriv",   f'Regn ut: {p(3,3)} + {p(4,2)} =', "43", None),
    ("flervalg",f'Hva er ({p(3,2)})² ?', "81", ["18", "36", "729"]),
    ("tekst",   f'Et kvadrat har sidelengde {p(2,3)} cm. Hva er arealet?', "64", None),
    ("flervalg",f'{p(10,5)} : {p(10,3)} =', "100", ["10", "1000", "2"]),
    ("skriv",   f'Regn ut: {p(2,3)} · {p(5,2)} =', "200", None),
    ("flervalg",f'Regn ut: {p(3,4)} - {p(4,3)} =', "17", ["0", "81", "64"]),
    ("tekst",   f'Et papir brettes dobbelt 6 ganger. Antall lag = {p(2,6)}. Hvor mange lag?', "64", None),
    ("flervalg",f'Regn ut: {p(6,2)} + {p(6,3)} =', "252", ["108", "72", "216"]),
    ("skriv",   f'Regn ut: ({p(2,4)})² =', "256", None),
    ("flervalg",f'{p(2,8)} : {p(2,4)} =', "16", ["8", "4", "32"]),
    ("tekst",   f'En kube har sidelengde {p(2,2)} cm. Hva er volumet? (side³)', "64", None),
    ("flervalg",f'Regn ut: {p(5,3)} + {p(5,2)} =', "150", ["25", "250", "100"]),
    ("skriv",   f'Regn ut: {p(7,2)} + {p(7,3)} =', "392", None),
    ("flervalg",f'Hva er {p(2,10)} : {p(2,5)} ?', "32", ["64", "5", "16"]),
    ("tekst",   f'Et sjakkbrett: antall ruter = {p(8,2)}. Hvor mange ruter?', "64", None),
    ("flervalg",f'Regn ut: {p(4,2)} · {p(3,3)} =', "432", ["48", "216", "144"]),
    ("skriv",   f'Regn ut: {p(2,5)} + {p(3,4)} + {p(4,2)} =', "129", None),
    ("tekst",   f'En bakterie deler seg og dobler seg hvert minutt. Etter 8 minutter er det {p(2,8)} bakterier. Hvor mange?', "256", None),
]


@app.route('/oppgaver/Potenser (enkle)/nivaa3', methods=['GET', 'POST'])
@login_required
def potenser_nivaa3_route():
    oppgaver = potenser_nivaa3_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 21000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Potenser – Nivå 3", melding="Du fullførte nivå 3! Monstersterkt 💪🔥")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        if type_ == "flervalg":
            svar = request.form.get("svar_flervalg", "").strip()
        else:
            svar = request.form.get("svar", "").strip()

        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 21000 + i, "link": f"/oppgaver/Potenser (enkle)/nivaa3?n={i}"} for i in range(1, total + 1)]
    return render_template("potenser_nivaa3.html",
        oppgave_html=oppgave_html, type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )



# ─────────────────────────────────────────────
# OVERSLAG OG HODEREGNING
# ─────────────────────────────────────────────

@app.route('/oppgaver/overslag')
@login_required
def overslag():
    return render_template('oppgaver_overslag.html')


# OVERSLAG NIVÅ 1 – avrunding og enkle overslag (ID 22001–22030)
overslag_nivaa1_oppgaver = [
    ("skriv",   "Rund av 47 til nærmeste tier.", "50", None),
    ("flervalg","Rund av 83 til nærmeste tier.", "80", ["70", "90", "100"]),
    ("skriv",   "Rund av 125 til nærmeste hundre.", "100", None),
    ("flervalg","Rund av 350 til nærmeste hundre.", "400", ["300", "350", "500"]),
    ("skriv",   "Rund av 7,4 til nærmeste hele tall.", "7", None),
    ("flervalg","Rund av 6,8 til nærmeste hele tall.", "7", ["6", "8", "10"]),
    ("skriv",   "Rund av 2,45 til én desimal.", "2,5", None),
    ("flervalg","Rund av 3,74 til én desimal.", "3,7", ["3,8", "4,0", "3,5"]),
    ("tekst",   "En butikk selger en vare for 49 kr. Rund av til nærmeste tier for å gjøre et overslag.", "50", None),
    ("flervalg","Rund av 999 til nærmeste hundre.", "1000", ["900", "990", "100"]),
    ("skriv",   "Rund av 4 567 til nærmeste tusen.", "5000", None),
    ("flervalg","Rund av 1 234 til nærmeste hundre.", "1200", ["1000", "1300", "1250"]),
    ("tekst",   "En skole har 487 elever. Lag et overslag ved å runde til nærmeste hundre.", "500", None),
    ("skriv",   "Rund av 0,36 til én desimal.", "0,4", None),
    ("flervalg","Rund av 14,45 til nærmeste hele tall.", "14", ["15", "14,5", "13"]),
    ("tekst",   "En buss kjører 38 km. Rund av til nærmeste tier.", "40", None),
    ("flervalg","Rund av 8 500 til nærmeste tusen.", "9000", ["8000", "8500", "10000"]),
    ("skriv",   "Rund av 55 til nærmeste hundre.", "100", None),
    ("flervalg","Rund av 3,15 til én desimal.", "3,2", ["3,1", "3,0", "3,5"]),
    ("tekst",   "Et tog bruker 2 timer og 47 minutter. Lag et overslag i hele timer.", "3", None),
    ("skriv",   "Rund av 74 til nærmeste tier.", "70", None),
    ("flervalg","Rund av 6 499 til nærmeste tusen.", "6000", ["7000", "6500", "5000"]),
    ("tekst",   "En vare koster 295 kr. Lag et overslag til nærmeste hundre.", "300", None),
    ("skriv",   "Rund av 1,75 til én desimal.", "1,8", None),
    ("flervalg","Rund av 45 til nærmeste tier.", "50", ["40", "40", "60"]),
    ("tekst",   "En svømmebasseng rommer 3 847 liter. Lag et overslag til nærmeste tusen.", "4000", None),
    ("skriv",   "Rund av 9,95 til nærmeste hele tall.", "10", None),
    ("flervalg","Rund av 2 750 til nærmeste tusen.", "3000", ["2000", "2800", "2500"]),
    ("tekst",   "En eske veier 4,38 kg. Lag et overslag til nærmeste hele kg.", "4", None),
    ("skriv",   "Rund av 365 til nærmeste hundre.", "400", None),
]


@app.route('/oppgaver/Overslag og hoderegning/nivaa1', methods=['GET', 'POST'])
@login_required
def overslag_nivaa1_route():
    oppgaver = overslag_nivaa1_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 22000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Overslag og hoderegning – Nivå 1", melding="Du fullførte nivå 1! Bra jobba 🎉")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip().replace(".", ",")
        fasit_norm = fasit.replace(".", ",")
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar == fasit_norm:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = f"❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 22000 + i, "link": f"/oppgaver/Overslag og hoderegning/nivaa1?n={i}"} for i in range(1, total + 1)]
    return render_template("overslag_nivaa1.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )


# OVERSLAG NIVÅ 2 – hoderegning og praktiske overslag (ID 23001–23030)
overslag_nivaa2_oppgaver = [
    ("tekst",   "Regn ut i hodet: 48 + 37", "85", None),
    ("flervalg","Regn ut i hodet: 99 + 56", "155", ["145", "165", "150"]),
    ("tekst",   "Regn ut i hodet: 125 - 48", "77", None),
    ("flervalg","Regn ut i hodet: 203 - 97", "106", ["96", "116", "100"]),
    ("tekst",   "En butikk selger 3 varer til 49 kr hver. Lag et overslag og regn ut nøyaktig.", "147", None),
    ("flervalg","Regn ut i hodet: 25 · 4", "100", ["80", "120", "90"]),
    ("tekst",   "Regn ut i hodet: 15 · 8", "120", None),
    ("flervalg","Regn ut i hodet: 360 : 9", "40", ["36", "45", "30"]),
    ("tekst",   "Du har 500 kr. Du kjøper noe for 187 kr. Hvor mye har du igjen? Regn i hodet.", "313", None),
    ("flervalg","Lag overslag: 298 + 403", "700", ["600", "800", "650"]),
    ("tekst",   "Regn ut i hodet: 450 + 380", "830", None),
    ("flervalg","Regn ut i hodet: 12 · 12", "144", ["124", "132", "148"]),
    ("tekst",   "En pakke med 6 flasker koster 54 kr. Hva koster én flaske?", "9", None),
    ("flervalg","Lag overslag: 4 · 97", "400", ["300", "380", "450"]),
    ("tekst",   "Regn ut i hodet: 750 - 290", "460", None),
    ("flervalg","Regn ut i hodet: 48 · 5", "240", ["200", "250", "220"]),
    ("tekst",   "Du kjøper 8 epler til 3,50 kr per eple. Hva blir totalen?", "28", None),
    ("flervalg","Lag overslag: 19 · 21", "400", ["300", "380", "420"]),
    ("tekst",   "Regn ut i hodet: 1000 - 347", "653", None),
    ("flervalg","Regn ut i hodet: 64 : 4", "16", ["14", "18", "12"]),
    ("tekst",   "En bil kjører 60 km/t. Hvor langt kjører den på 2,5 timer?", "150", None),
    ("flervalg","Regn ut i hodet: 35 · 6", "210", ["180", "200", "240"]),
    ("tekst",   "Regn ut i hodet: 99 · 3", "297", None),
    ("flervalg","Lag overslag: 5 · 196", "1000", ["800", "900", "1100"]),
    ("tekst",   "En klasse på 30 elever samler inn 45 kr hver. Hvor mye har de til sammen?", "1350", None),
    ("flervalg","Regn ut i hodet: 144 : 12", "12", ["11", "13", "14"]),
    ("tekst",   "Regn ut i hodet: 250 + 375 + 125", "750", None),
    ("flervalg","Lag overslag: 38 · 52", "2000", ["1500", "1800", "2500"]),
    ("tekst",   "Du har 200 kr. Du kjøper tre ting til 39 kr, 59 kr og 79 kr. Har du nok penger?", "ja", None),
    ("flervalg","Regn ut i hodet: 72 : 8", "9", ["8", "7", "10"]),
]


@app.route('/oppgaver/Overslag og hoderegning/nivaa2', methods=['GET', 'POST'])
@login_required
def overslag_nivaa2_route():
    oppgaver = overslag_nivaa2_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 23000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Overslag og hoderegning – Nivå 2", melding="Du fullførte nivå 2! Sterkt jobba 🔥")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip().lower().replace(".", ",")
        fasit_norm = fasit.lower().replace(".", ",")
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar == fasit_norm:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = f"❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 23000 + i, "link": f"/oppgaver/Overslag og hoderegning/nivaa2?n={i}"} for i in range(1, total + 1)]
    return render_template("overslag_nivaa2.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )


# OVERSLAG NIVÅ 3 – sammensatte overslag og rimelighet (ID 24001–24030)
overslag_nivaa3_oppgaver = [
    ("tekst",   "En butikk selger 4 varer til 199 kr, 299 kr, 149 kr og 249 kr. Lag et overslag og finn totalen.", "896", None),
    ("flervalg","Hva er det beste overslaget for 49 · 51?", "2500", ["2000", "3000", "2400"]),
    ("tekst",   "Regn ut i hodet: 999 + 1 + 999 + 1", "2000", None),
    ("flervalg","En bil kjører 110 km/t i ca. 3 timer. Hva er et godt overslag på distansen?", "330", ["200", "400", "300"]),
    ("tekst",   "Regn ut i hodet: 125 · 8", "1000", None),
    ("flervalg","Hva er det beste overslaget for 198 · 5?", "1000", ["900", "1100", "800"]),
    ("tekst",   "Du skal kjøpe 12 bøker til 89 kr stykket. Lag et overslag.", "1080", None),
    ("flervalg","Regn ut i hodet: 50 · 36", "1800", ["1600", "2000", "1500"]),
    ("tekst",   "En restaurant serverer 47 gjester. Regningen per person er ca. 205 kr. Lag et overslag på totalen.", "9350", None),
    ("flervalg","Regn ut i hodet: 375 + 625", "1000", ["900", "1100", "950"]),
    ("tekst",   "Regn ut i hodet: 64 · 25", "1600", None),
    ("flervalg","En fotballkamp varer 90 minutter. Hvor mange timer er det?", "1,5", ["2", "1", "0,5"]),
    ("tekst",   "Regn ut i hodet: 5 000 - 1 875", "3125", None),
    ("flervalg","Hva er det beste overslaget for 7 · 698?", "4900", ["4200", "5600", "4000"]),
    ("tekst",   "En klasse med 28 elever skal reise. Bussen koster 3 500 kr totalt. Hva betaler hver elev? Lag overslag.", "125", None),
    ("flervalg","Regn ut i hodet: 88 + 77 + 55", "220", ["200", "230", "210"]),
    ("tekst",   "Regn ut i hodet: 999 · 8", "7992", None),
    ("flervalg","En matbutikk har 365 dager i året. Overslag: hvor mange uker er det?", "52", ["50", "55", "48"]),
    ("tekst",   "Regn ut i hodet: 450 : 9 + 350 : 7", "100", None),
    ("flervalg","Hva er det beste overslaget for 313 · 3?", "900", ["600", "1200", "1000"]),
    ("tekst",   "Du kjøper 5 ting til 39 kr, 41 kr, 62 kr, 58 kr og 100 kr. Lag overslag og nøyaktig sum.", "300", None),
    ("flervalg","Regn ut i hodet: 2 500 : 25", "100", ["50", "75", "125"]),
    ("tekst",   "En svømmehall har 48 baner med 12 svømmere per bane. Regn ut totalt antall svømmere i hodet.", "576", None),
    ("flervalg","Hva er et godt overslag for 4,9 · 20?", "100", ["80", "90", "120"]),
    ("tekst",   "Regn ut i hodet: 75 · 4 + 25 · 4", "400", None),
    ("flervalg","En tog kjører 320 km på 2 timer. Hva er gjennomsnittsfarten i km/t?", "160", ["140", "180", "200"]),
    ("tekst",   "Regn ut i hodet: 11 · 11 · 11", "1331", None),
    ("flervalg","Hva er det beste overslaget for 19 · 19?", "400", ["300", "361", "500"]),
    ("tekst",   "En butikk selger 1 200 varer per dag. Hvor mange varer selger de på en uke?", "8400", None),
    ("flervalg","Regn ut i hodet: 3 600 : 12 + 2 400 : 8", "600", ["400", "700", "500"]),
]


@app.route('/oppgaver/Overslag og hoderegning/nivaa3', methods=['GET', 'POST'])
@login_required
def overslag_nivaa3_route():
    oppgaver = overslag_nivaa3_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 24000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Overslag og hoderegning – Nivå 3", melding="Du fullførte nivå 3! Monstersterkt 💪🔥")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip().lower().replace(".", ",")
        fasit_norm = fasit.lower().replace(".", ",")
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar == fasit_norm:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = f"❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 24000 + i, "link": f"/oppgaver/Overslag og hoderegning/nivaa3?n={i}"} for i in range(1, total + 1)]
    return render_template("overslag_nivaa3.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )



# ─────────────────────────────────────────────
# FORHOLD OG BRØK–DESIMAL–PROSENT
# ─────────────────────────────────────────────

@app.route('/oppgaver/forhold')
@login_required
def forhold():
    return render_template('oppgaver_forhold.html')


def _fv_tall(riktig, gale):
    import random
    alts = [riktig] + gale
    random.shuffle(alts)
    return alts


# NIVÅ 1 – omgjøring brøk ↔ desimal ↔ prosent (ID 25001–25030)
forhold_nivaa1_oppgaver = [
    ("flervalg", "Hva er 1/2 som prosent?",                                         "50%",   ["25%", "75%", "40%"]),
    ("skriv",    "Hva er 1/4 som prosent?",                                          "25%",   None),
    ("flervalg", "Hva er 3/4 som prosent?",                                          "75%",   ["50%", "25%", "80%"]),
    ("skriv",    "Hva er 1/5 som prosent?",                                          "20%",   None),
    ("flervalg", "Hva er 2/5 som prosent?",                                          "40%",   ["20%", "50%", "35%"]),
    ("skriv",    "Hva er 1/10 som prosent?",                                         "10%",   None),
    ("flervalg", "Hva er 3/10 som prosent?",                                         "30%",   ["25%", "33%", "20%"]),
    ("skriv",    "Hva er 1/2 som desimaltall?",                                      "0,5",   None),
    ("flervalg", "Hva er 1/4 som desimaltall?",                                      "0,25",  ["0,4", "0,5", "0,2"]),
    ("skriv",    "Hva er 3/4 som desimaltall?",                                      "0,75",  None),
    ("flervalg", "Hva er 1/5 som desimaltall?",                                      "0,2",   ["0,5", "0,15", "0,25"]),
    ("skriv",    "Hva er 1/10 som desimaltall?",                                     "0,1",   None),
    ("flervalg", "Hva er 0,5 som prosent?",                                          "50%",   ["5%", "0,5%", "55%"]),
    ("skriv",    "Hva er 0,25 som prosent?",                                         "25%",   None),
    ("flervalg", "Hva er 0,1 som prosent?",                                          "10%",   ["1%", "100%", "15%"]),
    ("skriv",    "Hva er 0,75 som prosent?",                                         "75%",   None),
    ("flervalg", "Hva er 0,2 som prosent?",                                          "20%",   ["2%", "12%", "25%"]),
    ("skriv",    "Hva er 50% som desimaltall?",                                      "0,5",   None),
    ("flervalg", "Hva er 25% som desimaltall?",                                      "0,25",  ["2,5", "0,025", "0,3"]),
    ("skriv",    "Hva er 10% som desimaltall?",                                      "0,1",   None),
    ("flervalg", "Hva er 75% som desimaltall?",                                      "0,75",  ["7,5", "0,075", "0,8"]),
    ("skriv",    "Hva er 50% som brøk? Skriv teller/nevner, f.eks. 1/2",            "1/2",   None),
    ("flervalg", "Hva er 25% som brøk?",                                             "1/4",   ["1/2", "2/5", "1/5"]),
    ("skriv",    "Hva er 20% som brøk (forenklet)?",                                "1/5",   None),
    ("flervalg", "Hva er 10% som brøk?",                                             "1/10",  ["1/5", "1/100", "1/9"]),
    ("tekst",    "I en klasse på 30 elever er 15 jenter. Hva er andelen jenter som prosent?", "50%", None),
    ("tekst",    "En butikk selger 4 av 10 varer. Skriv dette som desimaltall.",     "0,4",   None),
    ("flervalg", "Hva er 0,4 som prosent?",                                          "40%",   ["4%", "44%", "14%"]),
    ("tekst",    "En pizza er delt i 4 biter. Du spiser 1 bit. Hva er det som prosent?", "25%", None),
    ("skriv",    "Hva er 3/5 som prosent?",                                          "60%",   None),
]


@app.route('/oppgaver/Forhold og brøk–desimal–prosent/nivaa1', methods=['GET', 'POST'])
@login_required
def forhold_nivaa1_route():
    oppgaver = forhold_nivaa1_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 25000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Forhold og brøk–desimal–prosent – Nivå 1", melding="Du fullførte nivå 1! Bra jobba 🎉")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip().replace(".", ",")
        fasit_norm = fasit.replace(".", ",")
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar.lower() == fasit_norm.lower():
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 25000 + i, "link": f"/oppgaver/Forhold og brøk–desimal–prosent/nivaa1?n={i}"} for i in range(1, total + 1)]
    return render_template("forhold_nivaa1.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )


# NIVÅ 2 – forhold og forenkling (ID 26001–26030)
forhold_nivaa2_oppgaver = [
    ("skriv",    "Forenkle forholdet 4:8",                                           "1:2",   None),
    ("flervalg", "Forenkle forholdet 6:9",                                           "2:3",   ["3:4", "1:2", "6:9"]),
    ("skriv",    "Forenkle forholdet 10:15",                                         "2:3",   None),
    ("flervalg", "Forenkle forholdet 8:12",                                          "2:3",   ["4:6", "1:2", "3:4"]),
    ("skriv",    "Forenkle forholdet 15:20",                                         "3:4",   None),
    ("flervalg", "Forenkle forholdet 12:16",                                         "3:4",   ["2:3", "6:8", "1:2"]),
    ("tekst",    "I en klasse er det 12 jenter og 18 gutter. Hva er forholdet jenter:gutter (forenklet)?", "2:3", None),
    ("flervalg", "Forenkle forholdet 20:30",                                         "2:3",   ["4:6", "1:2", "3:5"]),
    ("skriv",    "Forenkle forholdet 9:27",                                          "1:3",   None),
    ("flervalg", "Forenkle forholdet 14:21",                                         "2:3",   ["7:10", "1:2", "4:7"]),
    ("tekst",    "En oppskrift bruker 2 dl mel og 4 dl vann. Hva er forholdet mel:vann?", "1:2", None),
    ("skriv",    "Forenkle forholdet 25:100",                                        "1:4",   None),
    ("flervalg", "Forenkle forholdet 16:24",                                         "2:3",   ["4:6", "8:12", "1:2"]),
    ("tekst",    "Et kart har målestokk 1:50000. Hva tilsvarer 1 cm på kartet i virkeligheten? Skriv antall cm.", "50000", None),
    ("flervalg", "Forenkle forholdet 30:45",                                         "2:3",   ["3:4", "6:9", "1:2"]),
    ("skriv",    "Forenkle forholdet 18:24",                                         "3:4",   None),
    ("tekst",    "En blanding er 3 deler juice og 1 del vann. Hva er prosenten juice?", "75%", None),
    ("flervalg", "Hva er forholdet 1:4 som prosent (den første delen)?",             "25%",   ["20%", "40%", "10%"]),
    ("skriv",    "Forenkle forholdet 100:250",                                       "2:5",   None),
    ("flervalg", "Hva er forholdet 2:5 som prosent (den første delen)?",             "40%",   ["20%", "25%", "50%"]),
    ("tekst",    "En bil kjører 300 km på 4 timer. Hva er gjennomsnittsfarten i km/t?", "75", None),
    ("flervalg", "Forenkle forholdet 36:48",                                         "3:4",   ["2:3", "6:8", "9:12"]),
    ("skriv",    "Forenkle forholdet 21:35",                                         "3:5",   None),
    ("tekst",    "En butikk selger juice: 1,5 liter for 30 kr og 1 liter for 22 kr. Hva koster 1 dl av den billigste? Skriv i kr.", "2", None),
    ("flervalg", "Hva er forholdet 3:4 som desimaltall (første del av totalen)?",   "0,75",  ["0,3", "0,25", "0,8"]),
    ("skriv",    "Forenkle forholdet 45:60",                                         "3:4",   None),
    ("tekst",    "I en fruktblanding er det 3 epler og 5 appelsiner. Hva er andelen epler som prosent? Rund av.", "38%", None),
    ("flervalg", "Forenkle forholdet 50:75",                                         "2:3",   ["5:7", "1:2", "25:38"]),
    ("skriv",    "Forenkle forholdet 28:42",                                         "2:3",   None),
    ("tekst",    "En skole har 200 elever. 80 er i 8. trinn. Hva er andelen som brøk (forenklet)?", "2/5", None),
]


@app.route('/oppgaver/Forhold og brøk–desimal–prosent/nivaa2', methods=['GET', 'POST'])
@login_required
def forhold_nivaa2_route():
    oppgaver = forhold_nivaa2_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 26000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Forhold og brøk–desimal–prosent – Nivå 2", melding="Du fullførte nivå 2! Sterkt jobba 🔥")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip().replace(".", ",")
        fasit_norm = fasit.replace(".", ",")
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar.lower() == fasit_norm.lower():
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 26000 + i, "link": f"/oppgaver/Forhold og brøk–desimal–prosent/nivaa2?n={i}"} for i in range(1, total + 1)]
    return render_template("forhold_nivaa2.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )


# NIVÅ 3 – sammensatte tekstoppgaver (ID 27001–27030)
forhold_nivaa3_oppgaver = [
    ("tekst",    "En jakke koster 600 kr. Den er satt ned 25%. Hva er den nye prisen?",                         "450",   None),
    ("flervalg", "0,375 som prosent er:",                                                                        "37,5%", ["3,75%", "375%", "38%"]),
    ("tekst",    "I en klasse er 60% jenter. Det er 30 elever totalt. Hvor mange er jenter?",                   "18",    None),
    ("flervalg", "Hva er 5/8 som desimaltall?",                                                                  "0,625", ["0,58", "0,68", "0,5"]),
    ("tekst",    "En butikk øker prisen med 20%. Varen kostet 250 kr. Hva er ny pris?",                         "300",   None),
    ("flervalg", "Hva er forholdet 3:5 som prosent av totalen (første del)?",                                   "37,5%", ["60%", "30%", "40%"]),
    ("tekst",    "Et tall er 0,6. Skriv det som brøk (forenklet).",                                             "3/5",   None),
    ("flervalg", "En by hadde 10 000 innbyggere og vokste med 15%. Hvor mange er det nå?",                      "11500", ["10150", "11000", "12000"]),
    ("tekst",    "Hva er 7/8 som prosent? (Rund av til én desimal)",                                            "87,5%", None),
    ("flervalg", "En elev fikk 18 av 24 oppgaver riktig. Hva er prosentandelen riktige?",                       "75%",   ["70%", "80%", "72%"]),
    ("tekst",    "Et produkt er satt ned fra 400 kr til 300 kr. Hvor mange prosent er det satt ned?",           "25%",   None),
    ("flervalg", "Hva er 0,125 som brøk (forenklet)?",                                                          "1/8",   ["1/4", "1/6", "1/12"]),
    ("tekst",    "En fotballkamp: laget vant 9 og tapte 6 av 15 kamper. Hva er vinnerprosenten?",               "60%",   None),
    ("flervalg", "Hva er 2:3 som desimaltall (første del av totalen)?",                                         "0,4",   ["0,6", "0,5", "0,25"]),
    ("tekst",    "Et tall er 0,875. Skriv det som brøk (forenklet).",                                           "7/8",   None),
    ("flervalg", "En vare koster 1 200 kr. Du får 30% rabatt. Hva betaler du?",                                 "840",   ["900", "960", "780"]),
    ("tekst",    "En klasse har forholdet 3:2 mellom jenter og gutter. Det er 25 elever totalt. Hvor mange jenter?", "15", None),
    ("flervalg", "Hva er 66,6% tilnærmet som brøk?",                                                            "2/3",   ["3/4", "1/2", "5/6"]),
    ("tekst",    "Et tall øker fra 80 til 100. Hvor mange prosent økte det?",                                   "25%",   None),
    ("flervalg", "0,04 som prosent er:",                                                                         "4%",    ["0,4%", "40%", "0,04%"]),
    ("tekst",    "En skole har 450 elever. 54 er syke én dag. Hva er fraværsprosenten?",                        "12%",   None),
    ("flervalg", "Hva er 12,5% som brøk?",                                                                      "1/8",   ["1/4", "1/6", "1/10"]),
    ("tekst",    "En butikk selger epler til 25 kr/kg og appelsiner til 40 kr/kg. Du kjøper 2 kg epler og 0,5 kg appelsiner. Hva betaler du?", "70", None),
    ("flervalg", "Hva er 37,5% som brøk?",                                                                      "3/8",   ["3/5", "4/10", "1/3"]),
    ("tekst",    "En person tjener 35 000 kr i måneden og betaler 28% i skatt. Hvor mye betaler de i skatt?",   "9800",  None),
    ("flervalg", "Et tall synker fra 200 til 150. Hvor mange prosent er nedgangen?",                            "25%",   ["20%", "30%", "33%"]),
    ("tekst",    "Forholdet mellom bredde og høyde på en skjerm er 16:9. Bredden er 48 cm. Hva er høyden?",     "27",    None),
    ("flervalg", "Hva er 0,0625 som brøk?",                                                                     "1/16",  ["1/8", "1/12", "1/4"]),
    ("tekst",    "Et tall er 1,25. Skriv det som blandet tall (brøk), f.eks. 1 1/4",                            "1 1/4", None),
    ("tekst",    "En elev fikk 45 av 60 poeng. Hva er prosentandelen?",                                         "75%",   None),
]


@app.route('/oppgaver/Forhold og brøk–desimal–prosent/nivaa3', methods=['GET', 'POST'])
@login_required
def forhold_nivaa3_route():
    oppgaver = forhold_nivaa3_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 27000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Forhold og brøk–desimal–prosent – Nivå 3", melding="Du fullførte nivå 3! Monstersterkt 💪🔥")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip().replace(".", ",")
        fasit_norm = fasit.replace(".", ",")
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar.lower() == fasit_norm.lower():
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 27000 + i, "link": f"/oppgaver/Forhold og brøk–desimal–prosent/nivaa3?n={i}"} for i in range(1, total + 1)]
    return render_template("forhold_nivaa3.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )



# ─────────────────────────────────────────────
# VARIABLER
# ─────────────────────────────────────────────

@app.route('/oppgaver/variabler')
@login_required
def variabler():
    return render_template('oppgaver_variabler.html')


def _fv_tall(riktig, gale):
    import random
    alts = [riktig] + gale
    random.shuffle(alts)
    return alts


# VARIABLER NIVÅ 1 – hva er en variabel, sette inn enkle verdier (ID 28001–28030)
variabler_nivaa1_oppgaver = [
    ("flervalg", "Hva er en variabel?",
     "Et symbol som representerer et ukjent tall",
     ["Et fast tall", "Et regnestykke", "Et svar"]),
    ("skriv",    "Hva er x + 3 når x = 2?",                            "5",    None),
    ("flervalg", "Hva er y + 5 når y = 4?",                            "9",    ["8", "10", "7"]),
    ("skriv",    "Hva er a - 2 når a = 7?",                            "5",    None),
    ("flervalg", "Hva er b + 10 når b = 6?",                           "16",   ["15", "17", "60"]),
    ("skriv",    "Hva er x + x når x = 3?",                            "6",    None),
    ("flervalg", "Hva er n - 4 når n = 9?",                            "5",    ["4", "6", "13"]),
    ("tekst",    "En pose inneholder x epler. Hvis x = 8, hvor mange epler er det?", "8", None),
    ("skriv",    "Hva er z + 7 når z = 0?",                            "7",    None),
    ("flervalg", "Hva er m + m + m når m = 2?",                        "6",    ["3", "4", "8"]),
    ("skriv",    "Hva er x - 1 når x = 10?",                           "9",    None),
    ("flervalg", "Hva er p + 6 når p = 3?",                            "9",    ["8", "10", "18"]),
    ("tekst",    "En boks har y blyanter. Hvis y = 12, hvor mange blyanter er det?", "12", None),
    ("skriv",    "Hva er a + b når a = 3 og b = 4?",                   "7",    None),
    ("flervalg", "Hva er x + y når x = 5 og y = 2?",                  "7",    ["10", "6", "8"]),
    ("skriv",    "Hva er n + 0 når n = 15?",                           "15",   None),
    ("flervalg", "Hva er a - b når a = 10 og b = 3?",                  "7",    ["6", "8", "13"]),
    ("tekst",    "En bil kjører x km per time. Etter 1 time er x = 60. Hvor langt har den kjørt?", "60", None),
    ("skriv",    "Hva er x + 4 når x = 11?",                           "15",   None),
    ("flervalg", "Hva er k - k når k = 99?",                           "0",    ["1", "99", "2"]),
    ("skriv",    "Hva er a + b + c når a = 1, b = 2 og c = 3?",        "6",    None),
    ("flervalg", "Hva er t + 8 når t = 7?",                            "15",   ["14", "16", "56"]),
    ("tekst",    "Ole har x kr. Han får 5 kr til. Uttrykket er x + 5. Hva er svaret når x = 20?", "25", None),
    ("skriv",    "Hva er x - y når x = 9 og y = 4?",                   "5",    None),
    ("flervalg", "Hva er p + q når p = 8 og q = 8?",                   "16",   ["8", "64", "0"]),
    ("tekst",    "En klasse har x elever. x = 28. Hvor mange elever er det?", "28", None),
    ("skriv",    "Hva er a + 3 når a = 17?",                           "20",   None),
    ("flervalg", "Hva er n - 0 når n = 42?",                           "42",   ["0", "41", "43"]),
    ("tekst",    "En eske har x kaker. Kari spiser 2. Uttrykket er x - 2. Hva er svaret når x = 10?", "8", None),
    ("skriv",    "Hva er x + y + z når x = 2, y = 3 og z = 5?",       "10",   None),
]


@app.route('/oppgaver/Variabler/nivaa1', methods=['GET', 'POST'])
@login_required
def variabler_nivaa1_route():
    oppgaver = variabler_nivaa1_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 28000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Variabler – Nivå 1", melding="Du fullførte nivå 1! Bra jobba 🎉")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip()
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar.lower() == fasit.lower():
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 28000 + i, "link": f"/oppgaver/Variabler/nivaa1?n={i}"} for i in range(1, total + 1)]
    return render_template("variabler_nivaa1.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )


# VARIABLER NIVÅ 2 – koeffisienter og uttrykk (ID 29001–29030)
variabler_nivaa2_oppgaver = [
    ("skriv",    "Hva er 2x når x = 4?",                               "8",    None),
    ("flervalg", "Hva er 3x når x = 5?",                               "15",   ["8", "53", "20"]),
    ("skriv",    "Hva er 4y når y = 3?",                               "12",   None),
    ("flervalg", "Hva er 5n når n = 6?",                               "30",   ["11", "25", "56"]),
    ("skriv",    "Hva er 2x + 3 når x = 4?",                           "11",   None),
    ("flervalg", "Hva er 3a - 2 når a = 4?",                           "10",   ["9", "11", "14"]),
    ("skriv",    "Hva er x² når x = 3?",                               "9",    None),
    ("flervalg", "Hva er 2x + y når x = 3 og y = 4?",                  "10",   ["9", "11", "14"]),
    ("tekst",    "En taxi koster 2x kr per km. Hva koster en tur på 5 km? (x = 1, så det er 2·5)", "10", None),
    ("skriv",    "Hva er 6n - 4 når n = 2?",                           "8",    None),
    ("flervalg", "Hva er 4x + 2x når x = 3?",                          "18",   ["12", "14", "24"]),
    ("skriv",    "Hva er 3a + 2b når a = 2 og b = 3?",                 "12",   None),
    ("flervalg", "Hva er 5y - 3y når y = 4?",                          "8",    ["2", "20", "12"]),
    ("tekst",    "En pakke koster 3x kr. Du kjøper 4 pakker. Hva er totalkostnaden når x = 5?", "60", None),
    ("skriv",    "Hva er 2x² når x = 3?",                              "18",   None),
    ("flervalg", "Hva er 10 - 2x når x = 3?",                          "4",    ["6", "7", "8"]),
    ("skriv",    "Hva er 4x - 2y når x = 5 og y = 4?",                 "12",   None),
    ("flervalg", "Hva er 3(x + 2) når x = 4?",                         "18",   ["14", "12", "9"]),
    ("tekst",    "En person tjener 50x kr per time og jobber 8 timer. Hva tjener personen når x = 1?", "400", None),
    ("skriv",    "Hva er 2(x + y) når x = 3 og y = 2?",               "10",   None),
    ("flervalg", "Hva er 7n + 3 når n = 3?",                           "24",   ["21", "33", "22"]),
    ("skriv",    "Hva er 5x - 3x + 2 når x = 4?",                     "10",   None),
    ("flervalg", "Hva er 4(2x - 1) når x = 2?",                        "12",   ["14", "16", "8"]),
    ("tekst",    "En rektangel har lengde 3x og bredde 2. Hva er arealet når x = 4?", "24", None),
    ("skriv",    "Hva er 9 - 3x når x = 2?",                           "3",    None),
    ("flervalg", "Hva er 2x + 3y når x = 5 og y = 2?",                 "16",   ["17", "20", "12"]),
    ("tekst",    "En bil kjører med fart v. Etter t timer har den kjørt v·t km. Hva er distansen når v = 80 og t = 3?", "240", None),
    ("skriv",    "Hva er 3x + 4x - 2 når x = 2?",                     "12",   None),
    ("flervalg", "Hva er 6(x - 2) når x = 5?",                         "18",   ["24", "12", "6"]),
    ("tekst",    "Prisen per eple er x kr. Du kjøper 6 epler og betaler med 50 kr. Restpengene er 50 - 6x. Hva er svaret når x = 7?", "8", None),
]


@app.route('/oppgaver/Variabler/nivaa2', methods=['GET', 'POST'])
@login_required
def variabler_nivaa2_route():
    oppgaver = variabler_nivaa2_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 29000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Variabler – Nivå 2", melding="Du fullførte nivå 2! Sterkt jobba 🔥")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip()
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar.lower() == fasit.lower():
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 29000 + i, "link": f"/oppgaver/Variabler/nivaa2?n={i}"} for i in range(1, total + 1)]
    return render_template("variabler_nivaa2.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )


# VARIABLER NIVÅ 3 – sammensatte uttrykk og tekstoppgaver (ID 30001–30030)
variabler_nivaa3_oppgaver = [
    ("skriv",    "Hva er 3x² + 2x når x = 2?",                        "16",   None),
    ("flervalg", "Hva er 2x² - 3x + 1 når x = 3?",                    "10",   ["16", "12", "8"]),
    ("tekst",    "Arealet av et kvadrat er x². Hva er arealet når x = 7?", "49", None),
    ("skriv",    "Hva er (x + y)² når x = 2 og y = 3?",               "25",   None),
    ("flervalg", "Hva er 4x² - x når x = 3?",                         "33",   ["39", "27", "30"]),
    ("tekst",    "En ball kastes opp med fart v. Høyden etter t sekunder er v·t - 5t². Hva er høyden når v = 20 og t = 2?", "20", None),
    ("skriv",    "Hva er 5(x + 3) - 2x når x = 4?",                   "23",   None),
    ("flervalg", "Hva er x(x + 1) når x = 5?",                        "30",   ["25", "35", "20"]),
    ("tekst",    "En rektangel har lengde (2x + 3) og bredde x. Hva er arealet når x = 4?", "44", None),
    ("skriv",    "Hva er 2(3x - 1) + x når x = 3?",                   "19",   None),
    ("flervalg", "Hva er (x + 2)(x - 2) når x = 5?",                  "21",   ["9", "25", "16"]),
    ("tekst",    "Prisen er 3x² + 2x kr. Hva er prisen når x = 4?",   "56",   None),
    ("skriv",    "Hva er 4x - 3y + 2z når x = 5, y = 2 og z = 3?",   "22",   None),
    ("flervalg", "Hva er x³ + x² når x = 2?",                         "12",   ["10", "8", "16"]),
    ("tekst",    "Vann i en tank: V = 100 - 3t liter. Hvor mye vann er det etter t = 15 minutter?", "55", None),
    ("skriv",    "Hva er 3x² - 2x - 1 når x = 4?",                    "39",   None),
    ("flervalg", "Hva er 2(x + y)(x - y) når x = 5 og y = 3?",        "32",   ["16", "64", "48"]),
    ("tekst",    "En bedrift tjener 200x - 500 kr per dag. Hva tjener de når x = 8?", "1100", None),
    ("skriv",    "Hva er x² + 2xy + y² når x = 3 og y = 2?",         "25",   None),
    ("flervalg", "Hva er 5x² - 4x + 3 når x = 2?",                    "15",   ["19", "11", "23"]),
    ("tekst",    "Temperaturen ute er t grader. Inne er det (2t + 5) grader. Hva er innetemperaturen når t = 8?", "21", None),
    ("skriv",    "Hva er (2x)² - x når x = 3?",                       "33",   None),
    ("flervalg", "Hva er 3x(x - 2) når x = 4?",                       "24",   ["12", "36", "48"]),
    ("tekst",    "Et svømmebasseng fylles med 5x liter per minutt. Etter t minutter er det 5xt liter. Hva er mengden når x = 3 og t = 10?", "150", None),
    ("skriv",    "Hva er 6x² - 2(x + 1) når x = 3?",                  "46",   None),
    ("flervalg", "Hva er x² + y² når x = 3 og y = 4?",                "25",   ["49", "14", "12"]),
    ("tekst",    "En bil starter med 60 liter drivstoff og bruker 0,1x liter per km. Hvor mye er igjen etter 200 km når x = 1?", "40", None),
    ("skriv",    "Hva er 2x³ - x² når x = 2?",                        "12",   None),
    ("flervalg", "Hva er (x + 1)² - (x - 1)² når x = 5?",             "20",   ["10", "24", "16"]),
    ("tekst",    "Fortjeneste = pris · antall - kostnad = 3x · 10 - 50. Hva er fortjenesten når x = 8?", "190", None),
]


@app.route('/oppgaver/Variabler/nivaa3', methods=['GET', 'POST'])
@login_required
def variabler_nivaa3_route():
    oppgaver = variabler_nivaa3_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 30000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Variabler – Nivå 3", melding="Du fullførte nivå 3! Monstersterkt 💪🔥")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip()
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar.lower() == fasit.lower():
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 30000 + i, "link": f"/oppgaver/Variabler/nivaa3?n={i}"} for i in range(1, total + 1)]
    return render_template("variabler_nivaa3.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )



# ─────────────────────────────────────────────
# ENKLE ALGEBRAISKE UTTRYKK
# ─────────────────────────────────────────────

@app.route('/oppgaver/enkle_uttrykk')
@login_required
def enkle_uttrykk():
    return render_template('oppgaver_enkle_uttrykk.html')


# NIVÅ 1 – lese og tolke enkle uttrykk (ID 31001–31030)
enkle_uttrykk_nivaa1_oppgaver = [
    ("flervalg", "Hva er koeffisienten i uttrykket 5x?",                               "5",          ["x", "1", "0"]),
    ("flervalg", "Hva er konstantleddet i uttrykket 3x + 7?",                          "7",          ["3", "x", "10"]),
    ("skriv",    "Hvor mange ledd har uttrykket 4x + 2y - 3?",                         "3",          None),
    ("flervalg", "Hva er koeffisienten til x i uttrykket 8x + 4?",                     "8",          ["4", "2", "12"]),
    ("skriv",    "Hva er verdien av 3x + 1 når x = 0?",                                "1",          None),
    ("flervalg", "Hva kalles tallene foran variablene i et uttrykk?",                  "Koeffisienter", ["Konstanter", "Eksponenter", "Ledd"]),
    ("skriv",    "Hva er verdien av 2x + 4 når x = 3?",                                "10",         None),
    ("flervalg", "Hva er verdien av 5x - 3 når x = 2?",                                "7",          ["10", "13", "3"]),
    ("tekst",    "Et uttrykk er 4 + n. Hva er verdien når n = 6?",                     "10",         None),
    ("flervalg", "Hva er verdien av 3y + 6 når y = 4?",                                "18",         ["12", "24", "10"]),
    ("skriv",    "Hva er verdien av 7 - x når x = 3?",                                 "4",          None),
    ("flervalg", "Hva er verdien av 2a + 2b når a = 3 og b = 2?",                      "10",         ["12", "7", "14"]),
    ("tekst",    "En butikk selger x antall varer til 10 kr stykket. Uttrykket er 10x. Hva er verdien når x = 5?", "50", None),
    ("skriv",    "Hva er verdien av 6 + 2t når t = 4?",                                "14",         None),
    ("flervalg", "Hvilket uttrykk beskriver 'et tall x pluss fire'?",                   "x + 4",      ["4x", "x - 4", "4 - x"]),
    ("skriv",    "Hva er verdien av 10 - 3k når k = 2?",                               "4",          None),
    ("flervalg", "Hva er verdien av 4n - 1 når n = 3?",                                "11",         ["12", "13", "7"]),
    ("tekst",    "Ole er x år gammel. Neste år er han x + 1 år. Hva er uttrykket for alderen om 5 år?", "x + 5", None),
    ("skriv",    "Hva er verdien av a + b + c når a = 2, b = 3, c = 4?",               "9",          None),
    ("flervalg", "Hvilket uttrykk betyr 'tre ganger et tall x'?",                      "3x",         ["x + 3", "x³", "x : 3"]),
    ("tekst",    "En eske har x kjeks. Du spiser 4. Skriv uttrykket for antall kjeks igjen.", "x - 4", None),
    ("flervalg", "Hva er verdien av 5 + 3m når m = 0?",                                "5",          ["3", "8", "15"]),
    ("skriv",    "Hva er verdien av 2x + 3y når x = 4 og y = 2?",                      "14",         None),
    ("flervalg", "Hva kalles x i uttrykket 4x + 3?",                                   "Variabel",   ["Koeffisient", "Konstant", "Ledd"]),
    ("tekst",    "En rektangel har sidelengder x og 5. Skriv uttrykket for omkretsen.", "2x + 10",    None),
    ("flervalg", "Hva er verdien av 8 - 2y når y = 3?",                                "2",          ["4", "6", "14"]),
    ("skriv",    "Hva er verdien av 3x - 2x + 5 når x = 4?",                           "9",          None),
    ("flervalg", "Hva er verdien av 4(x + 1) når x = 2?",                              "12",         ["8", "9", "16"]),
    ("tekst",    "Du har 20 kr og bruker x kr. Skriv uttrykket for pengene du har igjen.", "20 - x", None),
    ("skriv",    "Hva er verdien av 9 - x + 2 når x = 5?",                             "6",          None),
]


@app.route('/oppgaver/Enkle algebraiske uttrykk/nivaa1', methods=['GET', 'POST'])
@login_required
def enkle_uttrykk_nivaa1_route():
    oppgaver = enkle_uttrykk_nivaa1_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 31000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Enkle algebraiske uttrykk – Nivå 1", melding="Du fullførte nivå 1! Bra jobba 🎉")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip()
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar.lower() == fasit.lower():
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 31000 + i, "link": f"/oppgaver/Enkle algebraiske uttrykk/nivaa1?n={i}"} for i in range(1, total + 1)]
    return render_template("enkle_uttrykk_nivaa1.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )


# NIVÅ 2 – forenkle uttrykk ved å samle like ledd (ID 32001–32030)
enkle_uttrykk_nivaa2_oppgaver = [
    ("skriv",    "Forenkle: 3x + 2x",                                                  "5x",         None),
    ("flervalg", "Forenkle: 5y + 3y",                                                  "8y",         ["2y", "15y", "53y"]),
    ("skriv",    "Forenkle: 7a - 3a",                                                  "4a",         None),
    ("flervalg", "Forenkle: 4x + x",                                                   "5x",         ["4x", "3x", "44x"]),
    ("skriv",    "Forenkle: 6n - 2n + n",                                              "5n",         None),
    ("flervalg", "Forenkle: 3x + 2y + x",                                              "4x + 2y",    ["5x + 2y", "3x + 3y", "5xy"]),
    ("tekst",    "En klasse kjøper x blyanter og 3x bøker. Skriv det totale antallet som ett uttrykk.", "4x", None),
    ("flervalg", "Forenkle: 5a + 3b - 2a",                                             "3a + 3b",    ["3a - 3b", "6ab", "8a + 3b"]),
    ("skriv",    "Forenkle: 2x + 3 + 4x + 1",                                          "6x + 4",     None),
    ("flervalg", "Forenkle: 8m - 3m + 2",                                              "5m + 2",     ["5m - 2", "3m + 2", "11m"]),
    ("skriv",    "Forenkle: 4y + 2 - y - 1",                                           "3y + 1",     None),
    ("flervalg", "Forenkle: 3x + 4x - 2x",                                             "5x",         ["9x", "x", "7x"]),
    ("tekst",    "Ole har 2x kr og Kari har 5x kr. Skriv totalen som ett uttrykk.",    "7x",         None),
    ("skriv",    "Forenkle: 6a + 3b - 4a + b",                                         "2a + 4b",    None),
    ("flervalg", "Forenkle: 2(x + 3) + x",                                             "3x + 6",     ["2x + 3", "3x + 3", "2x + 6"]),
    ("skriv",    "Forenkle: 5x + 2y - 3x - y",                                        "2x + y",     None),
    ("flervalg", "Forenkle: 4n + 2 + 3n - 5",                                         "7n - 3",     ["7n + 3", "n - 3", "7n + 7"]),
    ("tekst",    "En rektangel har lengde 3x + 2 og bredde 2. Hva er arealet som uttrykk?", "6x + 4", None),
    ("skriv",    "Forenkle: 3(2x + 1)",                                                "6x + 3",     None),
    ("flervalg", "Forenkle: 2(3a - 2) + a",                                            "7a - 4",     ["6a - 4", "7a + 4", "5a - 2"]),
    ("skriv",    "Forenkle: 4x + 3 - 2x - 3",                                         "2x",         None),
    ("flervalg", "Forenkle: 5(x + 2) - 3x",                                            "2x + 10",    ["5x + 2", "2x - 10", "8x + 10"]),
    ("tekst",    "En butikk har x epler og dobbelt så mange appelsiner. Skriv totalen.", "3x",        None),
    ("skriv",    "Forenkle: 2x + 4y + 3x - 2y",                                        "5x + 2y",    None),
    ("flervalg", "Forenkle: 6a - (2a + 1)",                                             "4a - 1",     ["4a + 1", "8a - 1", "4a"]),
    ("skriv",    "Forenkle: 3(x + y) + 2(x - y)",                                      "5x + y",     None),
    ("flervalg", "Forenkle: 4m + 5 - m - 2",                                           "3m + 3",     ["5m + 3", "3m - 3", "4m + 3"]),
    ("tekst",    "En hage har lengde 2x + 3 og bredde x + 1. Skriv uttrykket for omkretsen.", "6x + 8", None),
    ("skriv",    "Forenkle: 5(2x - 3) - 4x",                                           "6x - 15",    None),
    ("flervalg", "Forenkle: 8y - 3(y - 2)",                                             "5y + 6",     ["5y - 6", "11y + 6", "5y - 2"]),
]


@app.route('/oppgaver/Enkle algebraiske uttrykk/nivaa2', methods=['GET', 'POST'])
@login_required
def enkle_uttrykk_nivaa2_route():
    oppgaver = enkle_uttrykk_nivaa2_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 32000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Enkle algebraiske uttrykk – Nivå 2", melding="Du fullførte nivå 2! Sterkt jobba 🔥")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip()
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar.lower().replace(" ", "") == fasit.lower().replace(" ", ""):
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 32000 + i, "link": f"/oppgaver/Enkle algebraiske uttrykk/nivaa2?n={i}"} for i in range(1, total + 1)]
    return render_template("enkle_uttrykk_nivaa2.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )


# NIVÅ 3 – sette opp uttrykk fra tekstoppgaver (ID 33001–33030)
enkle_uttrykk_nivaa3_oppgaver = [
    ("tekst",    "En bil kjører x km/t. Skriv uttrykket for distansen etter 3 timer.",                 "3x",         None),
    ("flervalg", "Hva er uttrykket for 'fem mer enn det dobbelte av x'?",                              "2x + 5",     ["5x + 2", "2 + 5x", "x + 5"]),
    ("tekst",    "En eske har n kjeks. Du spiser halvparten. Skriv uttrykket.",                         "n/2",        None),
    ("flervalg", "Forenkle: 3x + 2(x - 4) + 5",                                                       "5x - 3",     ["5x + 3", "3x - 3", "5x + 13"]),
    ("tekst",    "Prisen per kg epler er p kr. Du kjøper 2,5 kg. Skriv uttrykket for totalkostnaden.", "2,5p",       None),
    ("flervalg", "Forenkle: 4(2x + 3) - 3(x + 2)",                                                    "5x + 6",     ["5x - 6", "8x + 6", "5x + 8"]),
    ("tekst",    "En rektangel har lengde 2x + 1 og bredde x + 3. Skriv uttrykket for arealet.",       "(2x+1)(x+3)", None),
    ("flervalg", "Forenkle: 2x + 3y - (x - y)",                                                        "x + 4y",     ["x + 2y", "3x + 4y", "x - 2y"]),
    ("tekst",    "Kari er x år. Søsteren er 3 år eldre. Skriv uttrykket for søsterens alder om 5 år.", "x + 8",      None),
    ("flervalg", "Forenkle: 5(x + 2) - 2(2x - 1)",                                                    "x + 12",     ["x - 12", "9x + 8", "x + 8"]),
    ("tekst",    "En bedrift tjener 50x - 200 kr per dag. Skriv uttrykket for ukentlig fortjeneste (5 dager).", "250x - 1000", None),
    ("flervalg", "Forenkle: 3(a + b) - 2(a - b)",                                                      "a + 5b",     ["a - 5b", "5a + b", "a + b"]),
    ("tekst",    "Et kvadrat har sidelengde (x + 2). Skriv uttrykket for omkretsen.",                  "4x + 8",     None),
    ("flervalg", "Forenkle: 6x - 2(3x - 4)",                                                           "8",          ["8x", "0", "-8"]),
    ("tekst",    "En person sykler x km/t i 2 timer og går 4 km/t i 1 time. Skriv totaldistansen.",    "2x + 4",     None),
    ("flervalg", "Forenkle: 4(x - 1) + 3(2x + 1)",                                                    "10x - 1",    ["10x + 1", "7x - 1", "10x - 7"]),
    ("tekst",    "En butikk selger x varer til 45 kr og y varer til 30 kr. Skriv totalinntekten.",     "45x + 30y",  None),
    ("flervalg", "Forenkle: 2(x + 3y) - (x + y)",                                                     "x + 5y",     ["x - 5y", "3x + 5y", "x + 7y"]),
    ("tekst",    "Ole tar opp lån på 10 000 kr. Hvert år øker gjelden med 500x kr. Skriv gjelden etter n år.", "10000 + 500xn", None),
    ("flervalg", "Forenkle: 3x + 4 - (x - 2) + 2x",                                                   "4x + 6",     ["4x - 6", "6x + 6", "4x + 2"]),
    ("tekst",    "En tank inneholder 200 liter. Det renner ut 5x liter per time. Skriv uttrykket for mengden etter t timer.", "200 - 5xt", None),
    ("flervalg", "Forenkle: 5(2a - b) - 3(a + 2b)",                                                   "7a - 11b",   ["7a + 11b", "10a - 11b", "7a - 5b"]),
    ("tekst",    "En trekant har sider x, 2x og x + 5. Skriv uttrykket for omkretsen.",               "4x + 5",     None),
    ("flervalg", "Forenkle: 4(x + 2y) - 2(2x - y)",                                                   "10y",        ["4x + 10y", "10y + 4x", "0"]),
    ("tekst",    "En restaurant har faste kostnader på 3000 kr og 40x kr per gjest. Skriv uttrykket for totalkostnaden.", "3000 + 40x", None),
    ("flervalg", "Forenkle: 6(x - 3) - 2(x - 9)",                                                     "4x",         ["4x - 36", "4x + 36", "8x"]),
    ("tekst",    "Prisen på en jakke er p kr. Det er 20% rabatt. Skriv den nye prisen som uttrykk.",   "0,8p",       None),
    ("flervalg", "Forenkle: 3(2x + 1) - (4x - 5)",                                                    "2x + 8",     ["2x - 8", "10x + 8", "2x + 2"]),
    ("tekst",    "En elev får x poeng på hver oppgave. Det er 12 oppgaver, men hun mister 3 poeng for feil svar. Hun svarer feil på 2. Skriv poengsummen.", "12x - 6", None),
    ("flervalg", "Forenkle: 4(3x - 2y) - 2(5x - 4y)",                                                 "2x",         ["2x - 8y", "2x + 8y", "2x + 16y"]),
]


@app.route('/oppgaver/Enkle algebraiske uttrykk/nivaa3', methods=['GET', 'POST'])
@login_required
def enkle_uttrykk_nivaa3_route():
    oppgaver = enkle_uttrykk_nivaa3_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 33000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Enkle algebraiske uttrykk – Nivå 3", melding="Du fullførte nivå 3! Monstersterkt 💪🔥")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip()
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar.lower().replace(" ", "") == fasit.lower().replace(" ", ""):
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 33000 + i, "link": f"/oppgaver/Enkle algebraiske uttrykk/nivaa3?n={i}"} for i in range(1, total + 1)]
    return render_template("enkle_uttrykk_nivaa3.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )



# ─────────────────────────────────────────────
# REGNING MED UTTRYKK
# ─────────────────────────────────────────────

@app.route('/oppgaver/regning_uttrykk')
@login_required
def regning_uttrykk():
    return render_template('oppgaver_regning_uttrykk.html')


# NIVÅ 1 – addisjon og subtraksjon av uttrykk (ID 34001–34030)
regning_uttrykk_nivaa1_oppgaver = [
    ("skriv",    "Legg sammen: (2x + 3) + (4x + 1)",                           "6x + 4",    None),
    ("flervalg", "Legg sammen: (3x + 5) + (2x + 2)",                           "5x + 7",    ["5x + 3", "6x + 7", "5x + 10"]),
    ("skriv",    "Trekk fra: (5x + 4) - (2x + 1)",                             "3x + 3",    None),
    ("flervalg", "Trekk fra: (6x + 3) - (3x + 3)",                             "3x",        ["3x + 6", "9x", "3x - 6"]),
    ("skriv",    "Legg sammen: (x + 4) + (3x - 2)",                            "4x + 2",    None),
    ("flervalg", "Trekk fra: (8x + 5) - (3x - 2)",                             "5x + 7",    ["5x + 3", "5x - 7", "11x + 7"]),
    ("tekst",    "En rektangel har lengder (3x + 2) og (x + 4). Hva er summen av de to lengdene?", "4x + 6", None),
    ("flervalg", "Legg sammen: (2a + 3b) + (4a - b)",                          "6a + 2b",   ["6a - 2b", "2a + 2b", "6ab"]),
    ("skriv",    "Trekk fra: (7x - 3) - (2x - 5)",                             "5x + 2",    None),
    ("flervalg", "Legg sammen: (5x - 2) + (3x + 8)",                           "8x + 6",    ["8x - 6", "2x + 6", "8x + 10"]),
    ("tekst",    "Ole har (4x + 3) kr og Kari har (2x - 1) kr. Hvor mye har de til sammen?", "6x + 2", None),
    ("skriv",    "Legg sammen: (3x + y) + (x - 3y)",                           "4x - 2y",   None),
    ("flervalg", "Trekk fra: (9x + 4) - (4x + 4)",                             "5x",        ["5x + 8", "13x", "5x - 8"]),
    ("skriv",    "Legg sammen: (2x + 5) + (2x + 5)",                           "4x + 10",   None),
    ("flervalg", "Trekk fra: (6a - 2b) - (3a - 5b)",                           "3a + 3b",   ["3a - 3b", "9a - 7b", "3a - 7b"]),
    ("tekst",    "En boks inneholder (5n + 2) kuler. En annen inneholder (3n - 2) kuler. Hvor mange er det totalt?", "8n", None),
    ("skriv",    "Trekk fra: (10x + 3) - (4x - 1)",                            "6x + 4",    None),
    ("flervalg", "Legg sammen: (4x - 3) + (x + 7)",                            "5x + 4",    ["5x - 4", "4x + 4", "5x + 10"]),
    ("skriv",    "Legg sammen: (3a + 2b + 1) + (a - b + 3)",                   "4a + b + 4", None),
    ("flervalg", "Trekk fra: (5x + 2y) - (2x + y)",                            "3x + y",    ["3x - y", "7x + 3y", "3xy"]),
    ("tekst",    "Temperaturen stiger (2t + 1) grader og synker (t - 3) grader. Hva er netto endring?", "t + 4", None),
    ("skriv",    "Legg sammen: (7x - 4) + (-3x + 6)",                          "4x + 2",    None),
    ("flervalg", "Trekk fra: (8m + 3n) - (5m - 2n)",                           "3m + 5n",   ["3m - 5n", "3m + n", "13m + 5n"]),
    ("skriv",    "Trekk fra: (4x + 3y - 2) - (x + y - 5)",                    "3x + 2y + 3", None),
    ("flervalg", "Legg sammen: (6x - 1) + (2x + 1)",                           "8x",        ["8x - 2", "8x + 2", "4x"]),
    ("tekst",    "En trekant har sider (2x + 3), (x + 1) og (3x - 2). Hva er omkretsen?", "6x + 2", None),
    ("skriv",    "Trekk fra: (5x + 2y + 3) - (3x - y + 1)",                   "2x + 3y + 2", None),
    ("flervalg", "Legg sammen: (4a - 3) + (2a + 3) + (a - 1)",                "7a - 1",    ["7a + 1", "6a - 1", "7a"]),
    ("tekst",    "En butikk hadde (8x + 5) varer og solgte (3x + 2). Hvor mange er igjen?", "5x + 3", None),
    ("skriv",    "Legg sammen: (x + 2y - 3) + (3x - y + 5)",                  "4x + y + 2", None),
]


@app.route('/oppgaver/Regning med uttrykk/nivaa1', methods=['GET', 'POST'])
@login_required
def regning_uttrykk_nivaa1_route():
    oppgaver = regning_uttrykk_nivaa1_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 34000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Regning med uttrykk – Nivå 1", melding="Du fullførte nivå 1! Bra jobba 🎉")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip()
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar.lower().replace(" ", "") == fasit.lower().replace(" ", ""):
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 34000 + i, "link": f"/oppgaver/Regning med uttrykk/nivaa1?n={i}"} for i in range(1, total + 1)]
    return render_template("regning_uttrykk_nivaa1.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )


# NIVÅ 2 – multiplikasjon og distribusjon (ID 35001–35030)
regning_uttrykk_nivaa2_oppgaver = [
    ("skriv",    "Gang ut: 3(x + 4)",                                           "3x + 12",   None),
    ("flervalg", "Gang ut: 5(2x - 3)",                                          "10x - 15",  ["10x + 15", "7x - 3", "5x - 15"]),
    ("skriv",    "Gang ut: 2(3x + y)",                                          "6x + 2y",   None),
    ("flervalg", "Gang ut: 4(x - 2y + 1)",                                      "4x - 8y + 4", ["4x - 2y + 1", "4x + 8y + 4", "4x - 8y - 4"]),
    ("skriv",    "Gang ut og forenkle: 2(x + 3) + 3(x + 1)",                   "5x + 9",    None),
    ("flervalg", "Gang ut og forenkle: 4(x + 2) - 2(x - 1)",                   "2x + 10",   ["2x - 10", "6x + 6", "2x + 6"]),
    ("tekst",    "En rektangel har lengde (x + 3) og bredde 4. Skriv arealet som et forenklet uttrykk.", "4x + 12", None),
    ("flervalg", "Gang ut: -2(3x - 4)",                                         "-6x + 8",   ["-6x - 8", "6x - 8", "-6x + 4"]),
    ("skriv",    "Gang ut og forenkle: 3(2x + 1) - (x + 3)",                   "5x",        None),
    ("flervalg", "Gang ut og forenkle: 5(x - 2) + 2(x + 5)",                   "7x",        ["7x - 10", "3x", "7x + 10"]),
    ("tekst",    "Et kvadrat har sidelengde (2x + 1). Skriv arealet som uttrykk. (Hint: side · side)", "(2x+1)²", None),
    ("skriv",    "Gang ut og forenkle: 2(x + y) + 3(x - y)",                   "5x - y",    None),
    ("flervalg", "Gang ut og forenkle: 6(x + 1) - 3(x + 2)",                   "3x",        ["3x + 6", "9x - 6", "3x - 6"]),
    ("skriv",    "Gang ut: x(x + 3)",                                           "x² + 3x",   None),
    ("flervalg", "Gang ut: x(2x - 5)",                                          "2x² - 5x",  ["2x² + 5x", "x² - 5x", "2x - 5"]),
    ("tekst",    "En boks koster (3x + 2) kr. Du kjøper 4 bokser. Skriv totalkostnaden.", "12x + 8", None),
    ("skriv",    "Gang ut og forenkle: 4(3x - 1) - 2(5x - 3)",                 "2x + 2",    None),
    ("flervalg", "Gang ut: 2x(x + 4)",                                          "2x² + 8x",  ["2x + 8x", "2x² + 4", "2x² - 8x"]),
    ("tekst",    "En person jobber (x + 2) timer per dag i 5 dager. Skriv totale arbeidstimer.", "5x + 10", None),
    ("skriv",    "Gang ut og forenkle: 3(x + 2y) - 2(2x - y)",                 "-x + 8y",   None),
    ("flervalg", "Gang ut: -3(2x + 5)",                                         "-6x - 15",  ["-6x + 15", "6x + 15", "-6x - 5"]),
    ("skriv",    "Gang ut og forenkle: x(x + 2) + x(x - 2)",                   "2x²",       None),
    ("flervalg", "Gang ut og forenkle: 2(x + 3) + 4(x - 1) - x",              "5x + 2",    ["5x - 2", "7x + 2", "5x + 10"]),
    ("tekst",    "En bil kjører (v + 10) km/t i 3 timer. Skriv distansen som uttrykk.", "3v + 30", None),
    ("skriv",    "Gang ut og forenkle: 5(2x + 3) - 3(3x + 5)",                 "x",         None),
    ("flervalg", "Gang ut: 3x(2x - 1) + x",                                    "6x² - 2x",  ["6x² + 2x", "6x² - x", "6x - 2x"]),
    ("tekst",    "En rektangel har lengde (3x - 1) og bredde (x + 2). Skriv omkretsen.", "8x + 2", None),
    ("skriv",    "Gang ut og forenkle: 4(x - 2) - 3(x - 4) + 2x",             "3x + 4",    None),
    ("flervalg", "Gang ut og forenkle: 2(3x + 1) + 3(x - 2) - x",             "8x - 4",    ["8x + 4", "6x - 4", "8x"]),
    ("tekst",    "En butikk selger x varer til 25 kr og (x + 3) varer til 15 kr. Skriv totalinntekten.", "40x + 45", None),
]


@app.route('/oppgaver/Regning med uttrykk/nivaa2', methods=['GET', 'POST'])
@login_required
def regning_uttrykk_nivaa2_route():
    oppgaver = regning_uttrykk_nivaa2_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 35000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Regning med uttrykk – Nivå 2", melding="Du fullførte nivå 2! Sterkt jobba 🔥")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip()
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar.lower().replace(" ", "") == fasit.lower().replace(" ", ""):
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 35000 + i, "link": f"/oppgaver/Regning med uttrykk/nivaa2?n={i}"} for i in range(1, total + 1)]
    return render_template("regning_uttrykk_nivaa2.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )


# NIVÅ 3 – sammensatte uttrykk og tekstoppgaver (ID 36001–36030)
regning_uttrykk_nivaa3_oppgaver = [
    ("skriv",    "Gang ut og forenkle: (x + 2)(x + 3)",                         "x² + 5x + 6",   None),
    ("flervalg", "Gang ut og forenkle: (x + 4)(x + 1)",                         "x² + 5x + 4",   ["x² + 4x + 4", "x² + 5x + 5", "x² + 4"]),
    ("skriv",    "Gang ut og forenkle: (x + 3)(x - 3)",                         "x² - 9",         None),
    ("flervalg", "Gang ut og forenkle: (x + 5)(x - 2)",                         "x² + 3x - 10",  ["x² - 3x - 10", "x² + 5x - 10", "x² + 3x + 10"]),
    ("tekst",    "Et rom har lengde (x + 4) og bredde (x + 2). Skriv arealet som et forenklet uttrykk.", "x² + 6x + 8", None),
    ("skriv",    "Gang ut og forenkle: (2x + 1)(x + 3)",                        "2x² + 7x + 3",   None),
    ("flervalg", "Gang ut og forenkle: (x - 2)²",                               "x² - 4x + 4",   ["x² + 4x + 4", "x² - 4", "x² + 4"]),
    ("skriv",    "Gang ut og forenkle: (3x + 2)(x - 1)",                        "3x² - x - 2",    None),
    ("flervalg", "Gang ut og forenkle: (x + 1)²",                               "x² + 2x + 1",   ["x² + 1", "x² - 2x + 1", "2x + 1"]),
    ("tekst",    "En hage er (x + 5) meter lang og (x - 1) meter bred. Skriv arealet.", "x² + 4x - 5", None),
    ("skriv",    "Forenkle: 3(x + 2)² - 2x",                                    "3x² + 10x + 12", None),
    ("flervalg", "Gang ut og forenkle: (2x - 3)(2x + 3)",                       "4x² - 9",        ["4x² + 9", "4x² - 6x - 9", "4x² + 6x - 9"]),
    ("tekst",    "En bedrift selger (x + 10) enheter til (x - 5) kr per enhet. Skriv inntekten.", "x² + 5x - 50", None),
    ("skriv",    "Gang ut og forenkle: (x + 4)(x + 4)",                         "x² + 8x + 16",   None),
    ("flervalg", "Gang ut og forenkle: (3x + 1)(x - 4)",                        "3x² - 11x - 4",  ["3x² + 11x - 4", "3x² - 4x - 4", "3x² - 11x + 4"]),
    ("tekst",    "En rektangel har sider (2x + 3) og (x + 1). Skriv arealet og omkretsen.", "Areal: 2x²+5x+3, Omk: 6x+8", None),
    ("skriv",    "Forenkle: (x + 3)(x - 1) - x(x + 2)",                        "2x - 3",          None),
    ("flervalg", "Gang ut og forenkle: 2(x + 1)² - (x + 2)²",                  "x²",              ["x² + 2", "x² - 2", "2x²"]),
    ("tekst",    "En kvadrat har sidelengde (x + 3). Finn arealet og omkretsen.", "Areal: x²+6x+9, Omk: 4x+12", None),
    ("skriv",    "Gang ut og forenkle: (x - 5)(x + 5) + 10x",                   "x² + 10x - 25",  None),
    ("flervalg", "Gang ut og forenkle: (4x - 1)(x + 2)",                        "4x² + 7x - 2",   ["4x² - 7x - 2", "4x² + 7x + 2", "4x² - x - 2"]),
    ("tekst",    "Fortjeneste = (antall · pris) - kostnad = (x + 5)(2x - 3) - 10. Forenkle uttrykket.", "2x² + 7x - 25", None),
    ("skriv",    "Forenkle: (x + 2)² - (x - 2)²",                              "8x",              None),
    ("flervalg", "Gang ut og forenkle: 3(x + 1)(x - 1)",                        "3x² - 3",         ["3x² + 3", "3x² - 1", "3x²"]),
    ("tekst",    "Et rektangulært basseng er (3x - 2) meter langt og (x + 4) meter bredt. Finn arealet.", "3x² + 10x - 8", None),
    ("skriv",    "Gang ut og forenkle: (2x + 3)² - 4x²",                        "12x + 9",         None),
    ("flervalg", "Forenkle: (x + 4)(x - 2) + (x - 1)(x + 3)",                  "2x² + 4x - 11",   ["2x² + 4x + 11", "x² + 4x - 11", "2x² - 11"]),
    ("tekst",    "En trekant har grunnlinje (2x + 1) og høyde (x + 3). Skriv arealet (½ · g · h).", "x² + 3,5x + 1,5", None),
    ("skriv",    "Forenkle: (x + 1)(x + 2)(x + 3) — gang ut de to første først",  "x³ + 6x² + 11x + 6", None),
    ("flervalg", "Gang ut og forenkle: (5x - 2)(2x + 3)",                       "10x² + 11x - 6",  ["10x² - 11x - 6", "10x² + 11x + 6", "10x² - x - 6"]),
]


@app.route('/oppgaver/Regning med uttrykk/nivaa3', methods=['GET', 'POST'])
@login_required
def regning_uttrykk_nivaa3_route():
    oppgaver = regning_uttrykk_nivaa3_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 36000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Regning med uttrykk – Nivå 3", melding="Du fullførte nivå 3! Monstersterkt 💪🔥")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip()
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar.lower().replace(" ", "") == fasit.lower().replace(" ", ""):
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 36000 + i, "link": f"/oppgaver/Regning med uttrykk/nivaa3?n={i}"} for i in range(1, total + 1)]
    return render_template("regning_uttrykk_nivaa3.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )



# ─────────────────────────────────────────────
# LIKNINGER
# ─────────────────────────────────────────────

@app.route('/oppgaver/likninger2')
@login_required
def likninger2():
    return render_template('oppgaver_likninger2.html')


# NIVÅ 1 – enkle likninger, én operasjon (ID 37001–37030)
likninger_nivaa1_oppgaver = [
    ("skriv",    "Løs likningen: x + 5 = 12",                                          "7",    None),
    ("flervalg", "Løs likningen: x + 8 = 15",                                          "7",    ["8", "23", "6"]),
    ("skriv",    "Løs likningen: x - 3 = 9",                                           "12",   None),
    ("flervalg", "Løs likningen: x - 7 = 4",                                           "11",   ["3", "13", "-3"]),
    ("skriv",    "Løs likningen: 2x = 10",                                              "5",    None),
    ("flervalg", "Løs likningen: 3x = 21",                                              "7",    ["6", "63", "18"]),
    ("skriv",    "Løs likningen: x : 4 = 3",                                           "12",   None),
    ("flervalg", "Løs likningen: x : 5 = 6",                                           "30",   ["1", "11", "25"]),
    ("tekst",    "🎮 Du har x liv i et spill. Etter å ha tapt 4 liv har du 3 igjen. Hvor mange liv hadde du?", "7", None),
    ("flervalg", "Løs likningen: 4x = 36",                                              "9",    ["8", "32", "40"]),
    ("skriv",    "Løs likningen: x + 14 = 20",                                         "6",    None),
    ("flervalg", "Løs likningen: x - 9 = 6",                                           "15",   ["3", "-3", "54"]),
    ("tekst",    "🍕 En pizza er delt i x skiver. Du spiser 3 og det er 5 igjen. Hvor mange skiver var det?", "8", None),
    ("skriv",    "Løs likningen: 5x = 45",                                              "9",    None),
    ("flervalg", "Løs likningen: x + 25 = 40",                                         "15",   ["65", "16", "14"]),
    ("tekst",    "🐶 Du mater hunden x ganger om dagen. På en uke mater du den 21 ganger. Løs: 7x = 21", "3", None),
    ("skriv",    "Løs likningen: x - 15 = 7",                                          "22",   None),
    ("flervalg", "Løs likningen: 6x = 54",                                              "9",    ["48", "10", "8"]),
    ("skriv",    "Løs likningen: x : 3 = 8",                                           "24",   None),
    ("flervalg", "Løs likningen: x + 33 = 50",                                         "17",   ["83", "16", "18"]),
    ("tekst",    "🚀 En rakett har x drivstofftanker. Hver tank veier 200 kg. Total vekt er 1000 kg. Løs: 200x = 1000", "5", None),
    ("skriv",    "Løs likningen: 8x = 64",                                              "8",    None),
    ("flervalg", "Løs likningen: x - 18 = 12",                                         "30",   ["6", "-6", "216"]),
    ("tekst",    "🎵 Du har x sanger på spillelisten. Du sletter 7 og har 13 igjen. Løs likningen.", "20", None),
    ("skriv",    "Løs likningen: x : 6 = 5",                                           "30",   None),
    ("flervalg", "Løs likningen: 9x = 72",                                              "8",    ["63", "9", "7"]),
    ("tekst",    "⚽ Et lag scorer x mål per kamp. Etter 5 kamper har de 20 mål totalt. Løs: 5x = 20", "4", None),
    ("skriv",    "Løs likningen: x + 47 = 60",                                         "13",   None),
    ("flervalg", "Løs likningen: x - 23 = 8",                                          "31",   ["15", "-15", "184"]),
    ("tekst",    "🍦 En iskrem koster x kr. Du kjøper 3 og betaler 45 kr. Løs: 3x = 45", "15", None),
]


@app.route('/oppgaver/Likninger/nivaa1', methods=['GET', 'POST'])
@login_required
def likninger_nivaa1_route():
    oppgaver = likninger_nivaa1_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 37000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Likninger – Nivå 1", melding="Du fullførte nivå 1! Bra jobba 🎉")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip()
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 37000 + i, "link": f"/oppgaver/Likninger/nivaa1?n={i}"} for i in range(1, total + 1)]
    return render_template("likninger_nivaa1.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )


# NIVÅ 2 – likninger med parenteser og x på begge sider (ID 38001–38030)
likninger_nivaa2_oppgaver = [
    ("skriv",    "Løs likningen: 2x + 3 = 11",                                         "4",    None),
    ("flervalg", "Løs likningen: 3x - 5 = 16",                                         "7",    ["11", "3", "4"]),
    ("skriv",    "Løs likningen: 4x + 2 = 18",                                         "4",    None),
    ("flervalg", "Løs likningen: 5x - 3 = 22",                                         "5",    ["4", "6", "19"]),
    ("skriv",    "Løs likningen: 2x + 7 = 3x + 1",                                    "6",    None),
    ("flervalg", "Løs likningen: 4x + 3 = 2x + 11",                                   "4",    ["2", "7", "8"]),
    ("tekst",    "🎮 Du og kompisen din har begge x poeng. Du får 5 poeng til og han får 3 poeng til. Nå har dere like mange? Nei det er feil! Løs: x + 5 = x + 3. Hva skjer?", "ingen løsning", None),
    ("flervalg", "Løs likningen: 3(x + 2) = 15",                                       "3",    ["5", "7", "4"]),
    ("skriv",    "Løs likningen: 2(x - 3) = 8",                                       "7",    None),
    ("flervalg", "Løs likningen: 5(x + 1) = 30",                                       "5",    ["6", "25", "4"]),
    ("tekst",    "🐱 En katt veier x kg. En hund veier 3 ganger så mye pluss 2 kg = 14 kg. Løs: 3x + 2 = 14", "4", None),
    ("skriv",    "Løs likningen: 3x + 4 = x + 10",                                    "3",    None),
    ("flervalg", "Løs likningen: 6x - 2 = 4x + 8",                                    "5",    ["3", "10", "2"]),
    ("tekst",    "🏃 Lena løper x km/t og Ole løper (x + 2) km/t. Etter 3 timer er Ole 6 km foran. Løs: 3(x+2) - 3x = 6. Hva er x?", "Alle x fungerer — differansen er alltid 6", None),
    ("skriv",    "Løs likningen: 4(x + 3) = 2(x + 9)",                                "3",    None),
    ("flervalg", "Løs likningen: 7x - 5 = 5x + 9",                                    "7",    ["2", "14", "4"]),
    ("tekst",    "🍔 En burger koster (2x + 5) kr og brus koster (x + 3) kr. Totalt 26 kr. Løs: (2x+5) + (x+3) = 26", "6", None),
    ("skriv",    "Løs likningen: 3(2x - 1) = 15",                                     "3",    None),
    ("flervalg", "Løs likningen: 2(3x + 4) = 32",                                     "4",    ["8", "20", "6"]),
    ("tekst",    "💰 Du og søsteren din sparer penger. Du har (3x + 10) kr og hun har (5x - 6) kr. Dere har like mye. Løs likningen.", "8", None),
    ("skriv",    "Løs likningen: 5x - 8 = 2x + 7",                                    "5",    None),
    ("flervalg", "Løs likningen: 4(x - 2) = 2(x + 3)",                                "7",    ["5", "1", "9"]),
    ("tekst",    "🚗 En bil kjører x km/t. En sykkel kjører (x - 50) km/t. Bilen er dobbelt så rask. Løs: x = 2(x - 50)", "100", None),
    ("skriv",    "Løs likningen: 6(x + 1) = 4(x + 4)",                                "5",    None),
    ("flervalg", "Løs likningen: 3x + 12 = 5x - 4",                                   "8",    ["4", "2", "16"]),
    ("tekst",    "🎂 En kake deles mellom x venner. Hver får 3 biter. Det er 24 biter totalt. Løs: 3x = 24", "8", None),
    ("skriv",    "Løs likningen: 2(x + 5) = 3(x - 1)",                                "13",   None),
    ("flervalg", "Løs likningen: 8x - 3 = 6x + 7",                                    "5",    ["10", "2", "4"]),
    ("tekst",    "🏀 Et basketlag scorer 2x poeng i første omgang og (x + 15) i andre. Totalt 60 poeng. Løs likningen.", "15", None),
    ("skriv",    "Løs likningen: 4(2x - 3) = 3(x + 2)",                               "18",    None),
]


@app.route('/oppgaver/Likninger/nivaa2', methods=['GET', 'POST'])
@login_required
def likninger_nivaa2_route():
    oppgaver = likninger_nivaa2_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 38000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Likninger – Nivå 2", melding="Du fullførte nivå 2! Sterkt jobba 🔥")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip().lower()
        fasit_norm = fasit.lower()
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar == fasit_norm:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 38000 + i, "link": f"/oppgaver/Likninger/nivaa2?n={i}"} for i in range(1, total + 1)]
    return render_template("likninger_nivaa2.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )


# NIVÅ 3 – morsomme og krevende likninger (ID 39001–39030)
likninger_nivaa3_oppgaver = [
    ("tekst",    "🧟 I en zombiefilm er det x mennesker og (2x + 10) zombier. Totalt 100 skapninger. Finn x.", "30", None),
    ("flervalg", "Løs: x² = 25",                                                        "5",    ["-5", "±5", "12,5"]),
    ("tekst",    "🎯 En pil treffer blinken x ganger av 20 forsøk. Treffsikkerheten er 60%. Løs: x/20 = 0,6", "12", None),
    ("skriv",    "Løs likningen: x/3 + x/6 = 5",                                       "10",   None),
    ("flervalg", "Løs likningen: (x + 3)/2 = 7",                                        "11",   ["4", "17", "10"]),
    ("tekst",    "🦸 En superhelt løper x km/t og en superskurk løper (x - 20) km/t. Helten innhenter skurken på 2 timer hvis skurken er 40 km foran. Løs: 2x - 2(x-20) = 40", "Alle x fungerer — helten innhenter alltid", None),
    ("skriv",    "Løs likningen: 2x/3 = 8",                                            "12",   None),
    ("flervalg", "Løs likningen: (2x - 1)/3 = 5",                                      "8",    ["14", "7", "16"]),
    ("tekst",    "🍩 En baker lager x smultringer. Han spiser 5% av dem (= 3 stk). Løs: 0,05x = 3", "60", None),
    ("skriv",    "Løs likningen: 3x/4 - 2 = 7",                                        "12",   None),
    ("flervalg", "Løs likningen: (x + 5)/3 = (x - 1)/2",                               "13",   ["3", "7", "19"]),
    ("tekst",    "🌍 Verden har x milliarder mennesker. Asia har 4,7 milliarder, som er 60% av verdens befolkning. Løs: 0,6x = 4,7. Rund av til én desimal.", "7,8", None),
    ("skriv",    "Løs likningen: 5x/2 + 3 = 18",                                       "6",    None),
    ("flervalg", "Løs likningen: x² - 3x = 0",                                         "x = 0 eller x = 3", ["x = 3", "x = 0", "x = -3"]),
    ("tekst",    "🏦 Du setter inn x kr i banken med 5% rente. Etter ett år har du 1050 kr. Løs: x + 0,05x = 1050", "1000", None),
    ("skriv",    "Løs likningen: (3x + 1)/4 = (x + 5)/2",                              "9",    None),
    ("flervalg", "Løs likningen: 2x² = 50",                                             "5",    ["25", "10", "±5"]),
    ("tekst",    "🎪 Et sirkus selger x voksenbilletter à 150 kr og (x + 20) barnebilletter à 80 kr. Totalt 9 200 kr. Finn x.", "32", None),
    ("skriv",    "Løs likningen: x/4 + x/2 = 9",                                       "12",   None),
    ("flervalg", "Løs likningen: 4(x - 1)/3 = 8",                                      "7",    ["5", "9", "6"]),
    ("tekst",    "🚀 En rakett stiger x meter per sekund. Etter 30 sekunder er den 1500 meter oppe. Men vinden presser den 10 m/s ned. Løs: 30(x - 10) = 1500", "60", None),
    ("skriv",    "Løs likningen: 3(x + 2) = x² - 2  (prøv x = 4)",                   "4",    None),
    ("flervalg", "Løs likningen: (x - 3)(x + 3) = 0",                                  "x = 3 eller x = -3", ["x = 3", "x = -3", "x = 9"]),
    ("tekst",    "🎲 Du kaster en terning. Sannsynligheten for å få 6 er 1/6. Hvis du kaster x ganger og forventer 5 seksere. Løs: x/6 = 5", "30", None),
    ("skriv",    "Løs likningen: 2(x + 3)/5 = x - 1",                                 "11",   None),
    ("flervalg", "Løs likningen: 3x/5 + x/3 = 28/15",                                  "2",    ["1", "3", "4"]),
    ("tekst",    "🏠 En leilighet koster x kr. Etter 10% prisstigning er den verdt 550 000 kr. Løs: 1,1x = 550000", "500000", None),
    ("skriv",    "Løs likningen: (4x - 5)/3 = (2x + 1)/2",                            "13",   None),
    ("flervalg", "Løs likningen: x² + 2x - 8 = 0",                                     "x = 2 eller x = -4", ["x = 4 eller x = -2", "x = 2", "x = -4"]),
    ("tekst",    "🧮 Tenk på et tall x. Gang det med 3, trekk fra 7, del på 2 og legg til 5. Svaret er 10. Finn x! (Løs: (3x-7)/2 + 5 = 10)", "7", None),
]


@app.route('/oppgaver/Likninger/nivaa3', methods=['GET', 'POST'])
@login_required
def likninger_nivaa3_route():
    oppgaver = likninger_nivaa3_oppgaver
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = 39000 + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Likninger – Nivå 3", melding="Du fullførte nivå 3! Monstersterkt 💪🔥")

    type_, oppgave_html, fasit, gale = oppgaver[nummer - 1]
    alternativer = _fv_tall(fasit, gale) if type_ == "flervalg" else []

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form.get("svar_flervalg" if type_ == "flervalg" else "svar", "").strip().lower()
        fasit_norm = fasit.lower()
        if svar == "67":
            resultat = "🤡🤮 Du er ikke morsom 🖕"
            riktig = False
        elif svar == fasit_norm:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))", (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        else:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": 39000 + i, "link": f"/oppgaver/Likninger/nivaa3?n={i}"} for i in range(1, total + 1)]
    return render_template("likninger_nivaa3.html",
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )



# ─────────────────────────────────────────────
# SETTE INN VERDIER
# ─────────────────────────────────────────────

@app.route('/oppgaver/sette_inn')
@login_required
def sette_inn():
    return render_template('oppgaver_sette_inn.html')


def sjekk_matching(svar_json, riktige_par):
    """Sjekker om alle matching-koblinger er riktige. riktige_par = {str(i): str(i)}"""
    import json
    try:
        svar = json.loads(svar_json)
        for k, v in riktige_par.items():
            if str(svar.get(k)) != str(v):
                return False
        return len(svar) == len(riktige_par)
    except:
        return False


def lag_blandet_matching(par_liste):
    """Blander høyre-siden av par og legger til original index."""
    import random
    indeksert = [(p[0], p[1], str(i+1)) for i, p in enumerate(par_liste)]
    blandet = indeksert[:]
    random.shuffle(blandet)
    return blandet


# NIVÅ 1 – enkle uttrykk, finn feilen, matching (ID 40001–40030)
# Format: (type, oppgave_html, fasit, gale_eller_ekstra_data)
# ekstra_data for finn_feilen = liste av steg-strenger, fasit = str(feil_steg_nr)
# ekstra_data for matching = liste av (venstre, høyre) par, fasit = "riktig"
# ekstra_data for steg = liste av (steg_label, fasit_svar), fasit = "alle"

sette_inn_nivaa1_oppgaver = [
    ("skriv",       "Hva er verdien av 3x + 2 når x = 4?",                                 "14",       None),
    ("flervalg",    "Hva er verdien av 5y - 3 når y = 2?",                                  "7",        ["3", "13", "10"]),
    ("skriv",       "Hva er verdien av 2a + 2b når a = 3 og b = 5?",                       "16",       None),
    ("flervalg",    "Hva er verdien av 4n + 1 når n = 3?",                                  "13",       ["7", "16", "12"]),
    ("tekst",       "🌡️ Temperaturen i Celsius er C. Formelen for Fahrenheit er F = 1,8C + 32. Hva er F når C = 0?", "32", None),
    ("finn_feilen",
     "🔍 Noen regnet ut 2x + 3 når x = 5. Finn det gale steget!",
     "2",
     ["Setter inn x = 5: 2·5 + 3",
      "Regner: 2·5 = 15  ← HER ER FEILEN (skal være 10)",
      "Legger til 3: 15 + 3 = 18"]),
    ("skriv",       "Hva er verdien av 6 - x når x = 4?",                                  "2",        None),
    ("flervalg",    "Hva er verdien av 2x + 3y når x = 1 og y = 2?",                       "8",        ["5", "12", "7"]),
    ("matching",
     "Match hvert uttrykk med riktig verdi når x = 3",
     "riktig",
     [("2x + 1", "7"), ("x²", "9"), ("3x - 2", "7 — nei! 7"), ("x + 10", "13")]),
    ("skriv",       "Hva er verdien av a² + b når a = 2 og b = 5?",                        "9",        None),
    ("flervalg",    "Hva er verdien av 10 - 2x når x = 3?",                                "4",        ["7", "8", "16"]),
    ("tekst",       "🚗 Farten er v km/t. Distansen etter t timer er d = v·t. Hva er d når v = 60 og t = 2?", "120", None),
    ("skriv",       "Hva er verdien av 3(x + 2) når x = 4?",                               "18",       None),
    ("flervalg",    "Hva er verdien av x² - x når x = 5?",                                  "20",       ["25", "30", "4"]),
    ("tekst",       "📦 En eske har x blyanter. Du har 4 esker og 3 ekstra. Uttrykket er 4x + 3. Hva er verdien når x = 6?", "27", None),
    ("skriv",       "Hva er verdien av 2x² når x = 3?",                                    "18",       None),
    ("flervalg",    "Hva er verdien av (x + 3)² når x = 2?",                               "25",       ["10", "13", "7"]),
    ("finn_feilen",
     "🔍 Noen regnet ut 3(x - 2) når x = 6. Finn feilen!",
     "2",
     ["Setter inn x = 6: 3(6 - 2)",
      "Regner parentesen: 6 - 2 = 2  ← FEIL (skal være 4)",
      "Ganger: 3 · 2 = 6"]),
    ("tekst",       "🎯 Poengsummen er P = 10x - 5 der x er antall treff. Hva er P når x = 7?", "65", None),
    ("skriv",       "Hva er verdien av 4x + 3y - 2 når x = 2 og y = 3?",                  "15",       None),
    ("flervalg",    "Hva er verdien av 5(x + 1) - 3 når x = 4?",                           "22",       ["20", "27", "17"]),
    ("skriv",       "Hva er verdien av x³ når x = 2?",                                     "8",        None),
    ("tekst",       "💰 Lønn = 200x + 500 der x er antall timer. Hva er lønnen etter 8 timer?", "2100", None),
    ("matching",
     "Match hvert uttrykk med riktig verdi når x = 2 og y = 3",
     "riktig",
     [("x + y", "5"), ("2x + y", "7"), ("xy", "6"), ("x² + y", "7 — nei! 7")]),
    ("flervalg",    "Hva er verdien av 2(3x - 1) når x = 3?",                              "16",       ["17", "15", "11"]),
    ("skriv",       "Hva er verdien av x² + 2x + 1 når x = 3?",                            "16",       None),
    ("tekst",       "📐 Arealet av en trekant er A = ½·g·h. Hva er A når g = 8 og h = 5?", "20", None),
    ("flervalg",    "Hva er verdien av 3x² - 2x + 1 når x = 2?",                           "9",        ["11", "13", "7"]),
    ("steg",
     "📝 Regn ut 4x² - 3x + 2 steg for steg når x = 3",
     "alle",
     [("Steg 1: Regn ut x² (= 3²)", "9"),
      ("Steg 2: Gang med 4 (= 4·9)", "36"),
      ("Steg 3: Regn ut 3x (= 3·3)", "9"),
      ("Steg 4: Sett inn: 36 - 9 + 2", "29")]),
    ("skriv",       "Hva er verdien av (2x + 1)(x - 3) når x = 5?",                       "33",       None),
]


def kjor_sette_inn(oppgaver, id_base, template_navn, link_prefix):
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = id_base + nummer

    if nummer > total:
        return render_template("ferdig.html",
            tittel="Sette inn verdier",
            melding="Du fullførte dette nivået! 🎉")

    o = oppgaver[nummer - 1]
    type_ = o[0]
    oppgave_html = o[1]
    fasit = o[2]
    ekstra = o[3]

    alternativer = []
    steg_liste = []
    par_liste = []
    par_liste_blandet = []

    if type_ == "flervalg":
        alternativer = _fv_tall(fasit, ekstra)
    elif type_ == "finn_feilen":
        steg_liste = ekstra
        alternativer = []
    elif type_ == "matching":
        par_liste = ekstra
        par_liste_blandet = lag_blandet_matching(ekstra)
    elif type_ == "steg":
        steg_liste = [s[0] for s in ekstra]

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        ok = False

        if type_ in ["skriv", "tekst"]:
            svar = request.form.get("svar", "").strip().replace(".", ",")
            fasit_n = fasit.replace(".", ",")
            if svar == "67":
                resultat = "🤡🤮 Du er ikke morsom 🖕"
            else:
                ok = svar.lower() == fasit_n.lower()

        elif type_ == "flervalg":
            svar = request.form.get("svar_flervalg", "").strip()
            if svar == "67":
                resultat = "🤡🤮 Du er ikke morsom 🖕"
            else:
                ok = svar.lower() == fasit.lower()

        elif type_ == "finn_feilen":
            svar = request.form.get("svar_flervalg", "").strip()
            ok = svar == fasit

        elif type_ == "matching":
            svar_json = request.form.get("matching_svar", "{}")
            riktige = {str(i+1): str(i+1) for i in range(len(ekstra))}
            ok = sjekk_matching(svar_json, riktige)

        elif type_ == "steg":
            alle_riktige = all(
                request.form.get(f"steg_{i+1}", "").strip().replace(".", ",") == s[1].replace(".", ",")
                for i, s in enumerate(ekstra)
            )
            if alle_riktige:
                ok = True
            else:
                feil = [s[0] for i, s in enumerate(ekstra)
                        if request.form.get(f"steg_{i+1}", "").strip().replace(".", ",") != s[1].replace(".", ",")]
                resultat = "❌ Feil i: " + ", ".join(feil)

        if ok:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))",
                (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif not resultat:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": id_base + i, "link": f"{link_prefix}?n={i}"} for i in range(1, total + 1)]
    return render_template(template_navn,
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        steg_liste=steg_liste,
        par_liste=par_liste, par_liste_blandet=par_liste_blandet,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )


@app.route('/oppgaver/Sette inn verdier/nivaa1', methods=['GET', 'POST'])
@login_required
def sette_inn_nivaa1_route():
    return kjor_sette_inn(
        sette_inn_nivaa1_oppgaver, 40000,
        "sette_inn_nivaa1.html",
        "/oppgaver/Sette inn verdier/nivaa1"
    )


# NIVÅ 2 – sammensatte uttrykk og formler (ID 41001–41030)
sette_inn_nivaa2_oppgaver = [
    ("skriv",       "Hva er verdien av 3x² + 2x - 1 når x = 3?",                           "32",       None),
    ("flervalg",    "Hva er verdien av 2x³ - x² når x = 2?",                               "12",       ["8", "10", "16"]),
    ("tekst",       "⚡ Effekt P = U²/R. Hva er P når U = 10 og R = 5?",                   "20",       None),
    ("finn_feilen",
     "🔍 Noen regnet ut x² + 3x når x = 4. Finn det gale steget!",
     "3",
     ["Setter inn x = 4: 4² + 3·4",
      "Regner potensen: 4² = 16",
      "Regner 3x: 3·4 = 7  ← FEIL (skal være 12)",
      "Legger sammen: 16 + 7 = 23"]),
    ("skriv",       "Hva er verdien av (x + y)(x - y) når x = 5 og y = 3?",               "16",       None),
    ("flervalg",    "Hva er verdien av x² + y² når x = 3 og y = 4?",                       "25",       ["49", "14", "7"]),
    ("matching",
     "Match formelen med riktig verdi (x = 4)",
     "riktig",
     [("x² + 2x", "24"), ("3x - 4", "8"), ("2(x + 1)", "10"), ("x³ - x", "60")]),
    ("tekst",       "🏃 Distansen er s = v₀t + ½at². Hva er s når v₀ = 10, a = 2 og t = 3?", "39", None),
    ("skriv",       "Hva er verdien av 4x² - 3x + 2 når x = 2?",                           "12",       None),
    ("flervalg",    "Hva er verdien av (2x - 1)² når x = 3?",                              "25",       ["36", "11", "9"]),
    ("tekst",       "💡 Energi E = mc². Hva er E når m = 2 og c = 3?",                     "18",       None),
    ("skriv",       "Hva er verdien av 2x² + xy - y² når x = 3 og y = 2?",                "18",       None),
    ("flervalg",    "Hva er verdien av x(x + 1)(x + 2) når x = 3?",                        "60",       ["24", "36", "120"]),
    ("finn_feilen",
     "🔍 Noen regnet ut 2(x + 3)² når x = 1. Finn feilen!",
     "2",
     ["Setter inn x = 1: 2(1 + 3)²",
      "Regner parentesen: 1 + 3 = 8  ← FEIL (skal være 4)",
      "Tar kvadratet: 8² = 64",
      "Ganger med 2: 2·64 = 128"]),
    ("tekst",       "📐 Volumet av en kule er V = (4/3)πr³. Bruk π ≈ 3 og r = 2. Hva er V (omtrent)?", "32", None),
    ("skriv",       "Hva er verdien av x² - 4x + 4 når x = 5?",                            "9",        None),
    ("flervalg",    "Hva er verdien av 3x² - 2xy + y² når x = 2 og y = 1?",               "11",       ["9", "13", "15"]),
    ("steg",
     "📝 Regn ut (x + 2)(x - 1) steg for steg når x = 4",
     "alle",
     [("Steg 1: Regn ut (x + 2) = 4 + 2", "6"),
      ("Steg 2: Regn ut (x - 1) = 4 - 1", "3"),
      ("Steg 3: Gang sammen: 6 · 3", "18")]),
    ("tekst",       "🚀 Høyde h = -5t² + 20t. Hva er høyden etter t = 3 sekunder?",       "15",       None),
    ("skriv",       "Hva er verdien av (x + y)² - 2xy når x = 3 og y = 4?",               "25",       None),
    ("flervalg",    "Hva er verdien av x⁴ - x² når x = 2?",                               "12",       ["8", "16", "6"]),
    ("matching",
     "Match formelen med riktig verdi (x = 3, y = 2)",
     "riktig",
     [("x² + y²", "13"), ("(x+y)²", "25"), ("x² - y²", "5"), ("2xy", "12")]),
    ("tekst",       "🌡️ Formelen K = C + 273 gir Kelvin fra Celsius. Hva er K når C = 25?", "298", None),
    ("skriv",       "Hva er verdien av 5x² - 4xy + 3y² når x = 2 og y = 1?",             "15",       None),
    ("flervalg",    "Hva er verdien av (x - 2)³ når x = 4?",                               "8",        ["4", "16", "6"]),
    ("tekst",       "💰 Kapital K = P(1 + r)^n. Hva er K når P = 1000, r = 0,1 og n = 2?", "1210", None),
    ("skriv",       "Hva er verdien av x² + 2xy + y² når x = 4 og y = 3?",               "49",       None),
    ("flervalg",    "Hva er verdien av 2x³ + 3x² - x + 1 når x = 2?",                     "27",       ["23", "31", "19"]),
    ("tekst",       "📊 Fortjeneste F = px - kx - fk der p = pris, k = kostnad per enhet, fk = faste kostnader. Hva er F når p = 50, k = 30, x = 100, fk = 500?", "1500", None),
    ("skriv",       "Hva er verdien av (2x + y)(x - 2y) når x = 3 og y = 1?",            "21",       None),
]


@app.route('/oppgaver/Sette inn verdier/nivaa2', methods=['GET', 'POST'])
@login_required
def sette_inn_nivaa2_route():
    return kjor_sette_inn(
        sette_inn_nivaa2_oppgaver, 41000,
        "sette_inn_nivaa2.html",
        "/oppgaver/Sette inn verdier/nivaa2"
    )


# NIVÅ 3 – formler fra virkeligheten og krevende uttrykk (ID 42001–42030)
sette_inn_nivaa3_oppgaver = [
    ("tekst",       "🌍 Gravitasjonskraft F = G·m₁·m₂/r². Bruk G=6, m₁=5, m₂=4, r=2. Hva er F?", "30", None),
    ("flervalg",    "Hva er verdien av x³ + 3x² + 3x + 1 når x = 2?",                     "27",       ["19", "35", "9"]),
    ("finn_feilen",
     "🔍 Noen regnet ut (2x + 3)(x - 1) når x = 3. Finn feilen!",
     "3",
     ["Setter inn: (2·3 + 3)(3 - 1)",
      "Regner første parentes: 2·3 + 3 = 9",
      "Regner andre parentes: 3 - 1 = 1  ← FEIL (skal være 2)",
      "Ganger: 9 · 1 = 9"]),
    ("skriv",       "Hva er verdien av x⁴ - 2x³ + x² når x = 3?",                         "36",       None),
    ("tekst",       "🏦 Sluttverdien er S = P·(1 + r)^n. Hva er S når P = 2000, r = 0,05 og n = 3? (Rund av til nærmeste heltall)", "2315", None),
    ("matching",
     "Match formelen med riktig verdi (x = 2)",
     "riktig",
     [("x⁴ - x²", "12"), ("(x+1)³", "27"), ("3x² - 2x³", "-4"), ("x⁵", "32")]),
    ("tekst",       "⚡ Ohms lov: I = U/R. Effekt P = U·I = U²/R. Hva er P når U = 12 og R = 4?", "36", None),
    ("skriv",       "Hva er verdien av (x + 1)⁴ når x = 1?",                              "16",       None),
    ("flervalg",    "Hva er verdien av x² + 4x + 4 - (x - 2)² når x = 5?",               "16",       ["0", "25", "36"]),
    ("tekst",       "🎢 Farten på en berg-og-dal-bane er v = √(2gh). Bruk g = 10 og h = 20. Hva er v²? (v² = 2gh)", "400", None),
    ("steg",
     "📝 Regn ut 2x³ - 3x² + x - 5 steg for steg når x = 3",
     "alle",
     [("Steg 1: x³ = 3³", "27"),
      ("Steg 2: 2x³ = 2·27", "54"),
      ("Steg 3: x² = 3²", "9"),
      ("Steg 4: 3x² = 3·9", "27"),
      ("Steg 5: Sett inn: 54 - 27 + 3 - 5", "25")]),
    ("skriv",       "Hva er verdien av (x² - 1)/(x + 1) når x = 4?",                      "3",        None),
    ("flervalg",    "Hva er verdien av 2x³ - x² + 3x - 7 når x = 2?",                     "11",       ["9", "13", "7"]),
    ("tekst",       "📡 Signalstyrken S = P/d². Hva er S når P = 100 og d = 5?",           "4",        None),
    ("matching",
     "Match med riktig verdi (x = 2, y = 3)",
     "riktig",
     [("x³ + y²", "17"), ("(xy)²", "36"), ("x² · y³", "108"), ("(x+y)³", "125")]),
    ("skriv",       "Hva er verdien av x³ - 3x² + 3x - 1 når x = 4?",                     "27",       None),
    ("tekst",       "🌊 Bølgelengde λ = v/f. Hva er λ når v = 340 og f = 170?",           "2",        None),
    ("flervalg",    "Hva er verdien av (x + y + z)² når x = 1, y = 2, z = 3?",            "36",       ["14", "6", "100"]),
    ("tekst",       "🎯 Sannsynligheten for x treff av n forsøk: P = (x/n)·100%. Hva er P når x = 7 og n = 20?", "35%", None),
    ("skriv",       "Hva er verdien av 4x² - (2x - 1)² når x = 3?",                       "11",       None),
    ("finn_feilen",
     "🔍 Noen regnet ut x³ - 2x² + x når x = 4. Finn feilen!",
     "2",
     ["Setter inn: 4³ - 2·4² + 4",
      "Regner 4³: 4³ = 32  ← FEIL (skal være 64)",
      "Regner 2·4²: 2·16 = 32",
      "Setter inn: 32 - 32 + 4 = 4"]),
    ("tekst",       "💻 En algoritme bruker T = 2n² + 3n operasjoner. Hva er T når n = 10?", "230", None),
    ("flervalg",    "Hva er verdien av (x - y)³ når x = 5 og y = 2?",                     "27",       ["9", "125", "6"]),
    ("skriv",       "Hva er verdien av (x² + 2)(x - 1) når x = 3?",                       "22",       None),
    ("tekst",       "📐 Overflaten av en sylinder: S = 2πr² + 2πrh. Bruk π ≈ 3, r = 2, h = 5. Hva er S?", "84", None),
    ("flervalg",    "Hva er verdien av x⁴ + 4x³ + 6x² + 4x + 1 når x = 1?",              "16",       ["8", "32", "4"]),
    ("tekst",       "🏎️ Stoppedistansen er d = v²/2a. Hva er d når v = 20 og a = 5?",    "40",       None),
    ("skriv",       "Hva er verdien av (x + y)³ - (x³ + y³) når x = 2 og y = 1?",        "9",        None),
    ("flervalg",    "Hva er verdien av 5x⁴ - 3x³ + 2x² - x + 1 når x = 1?",              "4",        ["6", "8", "10"]),
    ("tekst",       "🌡️ Idealgassloven: P = nRT/V. Hva er P når n = 2, R = 8, T = 300 og V = 4?", "1200", None),
]


@app.route('/oppgaver/Sette inn verdier/nivaa3', methods=['GET', 'POST'])
@login_required
def sette_inn_nivaa3_route():
    return kjor_sette_inn(
        sette_inn_nivaa3_oppgaver, 42000,
        "sette_inn_nivaa3.html",
        "/oppgaver/Sette inn verdier/nivaa3"
    )



# ─────────────────────────────────────────────
# TALL OG SYMBOLER
# ─────────────────────────────────────────────

@app.route('/oppgaver/tall_symboler')
@login_required
def tall_symboler():
    return render_template('oppgaver_tall_symboler.html')


# NIVÅ 1 – grunnleggende symboler: =, ≠, <, >, ≤, ≥ (ID 43001–43030)

# NIVÅ 1 – lese og tolke symboler, enkle sammenligninger (ID 43001–43030)
# REGLER: Ingen svar krever spesialtegn. Alle symbol-svar er FLERVALG.
tall_symboler_nivaa1_oppgaver = [
    ("flervalg", "Hva betyr symbolet < ?",
     "Mindre enn", ["Større enn", "Er lik", "Er ikke lik"]),
    ("flervalg", "Hva betyr symbolet > ?",
     "Større enn", ["Mindre enn", "Er lik", "Pluss"]),
    ("flervalg", "Hva betyr symbolet = ?",
     "Er lik", ["Er ikke lik", "Større enn", "Mindre enn"]),
    ("flervalg", "Hva betyr symbolet ≠ ?",
     "Er ikke lik", ["Er lik", "Større enn", "Mindre enn"]),
    ("flervalg", "Er 5 > 3 sant eller usant?",
     "Sant", ["Usant", "Vet ikke", "Verken sant eller usant"]),
    ("flervalg", "Er 7 < 4 sant eller usant?",
     "Usant", ["Sant", "Kan ikke si", "Begge deler"]),
    ("flervalg", "Hvilket symbol passer? 8 ___ 10",
     "<", [">", "=", "≠"]),
    ("flervalg", "Hvilket symbol passer? 15 ___ 9",
     ">", ["<", "=", "≠"]),
    ("flervalg", "Hvilket symbol passer? 3 + 4 ___ 7",
     "=", ["<", ">", "≠"]),
    ("flervalg", "Hvilket symbol passer? 2 · 5 ___ 9",
     ">", ["<", "=", "≠"]),
    ("tekst", "🌡️ Temperaturen ute er -5°C og inne er 20°C. Hvilket er størst?",
     "20", None),
    ("flervalg", "Er 0 > -1 sant eller usant?",
     "Sant", ["Usant", "Vet ikke", "Begge"]),
    ("flervalg", "Hva betyr ≤ ?",
     "Mindre enn eller lik", ["Større enn eller lik", "Er lik", "Ikke lik"]),
    ("flervalg", "Hva betyr ≥ ?",
     "Større enn eller lik", ["Mindre enn eller lik", "Er lik", "Større enn"]),
    ("flervalg", "Er 4 ≤ 4 sant eller usant?",
     "Sant", ["Usant", "Vet ikke", "Begge"]),
    ("tekst", "🏆 Lag A har 45 poeng og Lag B har 38 poeng. Hvem har flest poeng?",
     "Lag A", None),
    ("flervalg", "Er 6 ≥ 7 sant eller usant?",
     "Usant", ["Sant", "Begge", "Vet ikke"]),
    ("flervalg", "Hva betyr ≈ ?",
     "Tilnærmet lik", ["Er lik", "Ikke lik", "Større enn"]),
    ("flervalg", "Er π ≈ 3,14 sant eller usant?",
     "Sant", ["Usant", "Begge", "Vet ikke"]),
    ("tekst", "🎮 Du trenger minst 10 liv for å spille. Du har 12. Har du nok?",
     "ja", None),
    ("flervalg", "Hvilket symbol passer? 3² ___ 8",
     ">", ["<", "=", "≠"]),
    ("flervalg", "Hvilket symbol passer? 2³ ___ 9",
     "<", [">", "=", "≠"]),
    ("tekst", "🍕 En pizza har 8 biter. Du spiser 3. Er antall spiste biter større enn antall igjen?",
     "nei", None),
    ("matching",
     "Match symbolet med riktig betydning",
     "riktig",
     [("<", "Mindre enn"), (">", "Større enn"), ("=", "Er lik"), ("≠", "Er ikke lik")]),
    ("flervalg", "Hvilket symbol passer? 0,5 ___ ½",
     "=", ["<", ">", "≠"]),
    ("flervalg", "Er -10 < -5 sant eller usant?",
     "Sant", ["Usant", "Vet ikke", "Begge"]),
    ("tekst", "❄️ Hvilken temperatur er lavest: -8°C eller -2°C?",
     "-8", None),
    ("steg",
     "📝 Sammenlign 2³ og 3²",
     "alle",
     [("Steg 1: Regn ut 2³ (= 2·2·2)", "8"),
      ("Steg 2: Regn ut 3² (= 3·3)", "9"),
      ("Steg 3: Hvem er størst? Skriv 2³ eller 3²", "3²")]),
    ("flervalg", "Hvilket symbol passer? 4! ___ 20   (4! = 24)",
     ">", ["<", "=", "≠"]),
    ("finn_feilen",
     "🔍 Noen sammenlignet 2³ og 4². Finn det gale steget!",
     "2",
     ["Regner 2³: 2·2·2 = 8",
      "Regner 4²: 4·4 = 8  ← FEIL (4·4 = 16, ikke 8!)",
      "Sammenligner: 8 < 16, altså 2³ < 4²"]),
]


@app.route('/oppgaver/Tall og symboler/nivaa1', methods=['GET', 'POST'])
@login_required
def tall_symboler_nivaa1_route():
    return kjor_sette_inn(
        tall_symboler_nivaa1_oppgaver, 43000,
        "tall_symboler_nivaa1.html",
        "/oppgaver/Tall og symboler/nivaa1"
    )


# NIVÅ 2 – bruke symboler i sammenheng med tall og ulikheter (ID 44001–44030)
tall_symboler_nivaa2_oppgaver = [
    ("flervalg", "Hva betyr |−7|?",
     "7", ["−7", "0", "49"]),
    ("flervalg", "Hva er |−12|?",
     "12", ["−12", "144", "0"]),
    ("skriv",    "Hva er |−9| + |3|?",                                "12", None),
    ("flervalg", "Hva er |5 − 8|?",
     "3", ["−3", "13", "40"]),
    ("tekst", "❄️ Oslo hadde −8°C og Bergen hadde −3°C. Absoluttverdien viser avstand fra 0. Hvilken by er kaldest?",
     "Oslo", None),
    ("flervalg", "Hva betyr x < 5 i ord?",
     "x er mindre enn 5", ["x er 5", "x er større enn 5", "x er lik 5"]),
    ("flervalg", "Hvilke tall oppfyller x > 3? (Velg riktig gruppe)",
     "4, 5, 6, 7", ["1, 2, 3", "0, 1, 2", "3, 3, 3"]),
    ("tekst", "🎯 Løs ulikheten x + 3 > 7. Hva er det minste hele tall x kan være?",
     "5", None),
    ("flervalg", "Hva betyr 3 ∈ {1, 2, 3, 4}?",
     "3 er med i mengden", ["3 er ikke i mengden", "3 ganger mengden", "3 er lik mengden"]),
    ("flervalg", "Er 7 ∈ {2, 4, 6, 8}?",
     "Nei", ["Ja", "Kanskje", "Vet ikke"]),
    ("tekst", "🔢 Mengden A = {1, 3, 5, 7, 9}. Er 5 med i A? Skriv ja eller nei.",
     "ja", None),
    ("finn_feilen",
     "🔍 Noen løste 2x < 10. Finn feilen!",
     "2",
     ["Starter med: 2x < 10",
      "Deler på 2: x > 5  ← FEIL (skal være x < 5 når man deler, ikke snur tegnet!)",
      "Konklusjon: x > 5"]),
    ("flervalg", "Hva er ∑ av {2, 4, 6}?",
     "12", ["6", "24", "8"]),
    ("skriv",    "Hva er summen (∑) av {10, 20, 30, 40}?",            "100", None),
    ("tekst", "📊 ∑ betyr sum. Hva er ∑ av tallene 5, 10, 15 og 20?",
     "50", None),
    ("flervalg", "Hva er |−3 + 10|?",
     "7", ["−7", "13", "30"]),
    ("matching",
     "Match symbolet med riktig forklaring",
     "riktig",
     [("|x|", "Absoluttverdien av x"), ("∈", "Er et element i"), ("∑", "Summen av"), ("≈", "Tilnærmet lik")]),
    ("tekst", "🎮 Løs: 3x ≤ 12. Hva er det største hele tallet x kan være?",
     "4", None),
    ("flervalg", "Hva er |−20|?",
     "20", ["−20", "2", "200"]),
    ("skriv",    "Hva er |7 − 15|?",                                  "8", None),
    ("steg",
     "📝 Løs ulikheten 4x − 2 > 10 steg for steg",
     "alle",
     [("Steg 1: Legg til 2 på begge sider: 4x > ?", "12"),
      ("Steg 2: Del på 4: x > ?", "3"),
      ("Steg 3: Minste hele tall som oppfyller ulikheten", "4")]),
    ("tekst", "🌡️ Termometeret viser −15°C. Hva er absoluttverdien?",
     "15", None),
    ("flervalg", "Hvilke tall er med i mengden {partall mellom 1 og 10}?",
     "2, 4, 6, 8", ["1, 3, 5, 7", "2, 4, 6, 8, 10", "0, 2, 4, 6"]),
    ("tekst", "⚽ Et lag trenger minst 11 spillere. Laget har 13. Er dette nok? Skriv ja eller nei.",
     "ja", None),
    ("flervalg", "Hva er |−5| · |−4|?",
     "20", ["−20", "9", "1"]),
    ("tekst", "🔢 A = {1,2,3,4,5,6}. Er 7 ∈ A? Skriv ja eller nei.",
     "nei", None),
    ("flervalg", "Hva betyr x ≠ 0?",
     "x er ikke null", ["x er null", "x er negativ", "x er positiv"]),
    ("skriv",    "Hva er |−6| − |−2|?",                               "4", None),
    ("finn_feilen",
     "🔍 Noen regnet |−4 + 9|. Finn feilen!",
     "2",
     ["Regner inni absoluttverdien: −4 + 9",
      "Svaret er: −4 + 9 = −5  ← FEIL (skal være +5)",
      "Absoluttverdien: |5| = 5"]),
    ("tekst", "💰 Du har 200 kr. Bruker 80 kr. Har du mer enn 100 kr igjen? Skriv ja eller nei.",
     "ja", None),
]


@app.route('/oppgaver/Tall og symboler/nivaa2', methods=['GET', 'POST'])
@login_required
def tall_symboler_nivaa2_route():
    return kjor_sette_inn(
        tall_symboler_nivaa2_oppgaver, 44000,
        "tall_symboler_nivaa2.html",
        "/oppgaver/Tall og symboler/nivaa2"
    )


# NIVÅ 3 – symboler i sammensatte oppgaver og hverdagssituasjoner (ID 45001–45030)
tall_symboler_nivaa3_oppgaver = [
    ("tekst", "🏦 Du setter inn 1000 kr i banken. Etter ett år har du 1050 kr. Hva er økningen i kr?",
     "50", None),
    ("flervalg", "Hva er |−8| + |−8|?",
     "16", ["0", "−16", "64"]),
    ("tekst", "🌡️ Temperaturforskjell: Oslo −5°C, Madrid 25°C. Hva er absolutt differanse?",
     "30", None),
    ("flervalg", "A = {2, 4, 6, 8} og B = {4, 8, 12}. Hvilke tall er i BEGGE mengdene?",
     "4 og 8", ["2 og 4", "6 og 8", "8 og 12"]),
    ("tekst", "🎯 Løs: 2x + 4 > 10. Hva er minste hele tall x kan være?",
     "4", None),
    ("finn_feilen",
     "🔍 Noen fant felles elementer i A={2,4,6} og B={1,2,3,4}. Finn feilen!",
     "2",
     ["Ser på A: {2, 4, 6}",
      "Felles elementer er {2, 4, 6}  ← FEIL (6 er ikke i B!)",
      "Riktig svar er {2, 4}"]),
    ("flervalg", "Hva er |3² − 4²|?",
     "7", ["1", "25", "−7"]),
    ("tekst", "📐 Arealet av et kvadrat er A = s². Er A > 0 alltid sant når s > 0? Skriv ja eller nei.",
     "ja", None),
    ("matching",
     "Match hvert uttrykk med riktig verdi",
     "riktig",
     [("|−10|", "10"), ("|3 − 7|", "4"), ("|−5| + |−5|", "10"), ("|2² − 5|", "1")]),
    ("flervalg", "Mengden A = {oddetall under 10}. Hva er A?",
     "{1, 3, 5, 7, 9}", ["{1, 3, 5, 7}", "{3, 5, 7, 9}", "{0, 2, 4, 6, 8}"]),
    ("tekst", "🚗 En bil bruker mer enn 5 liter per mil. Kjøreturen er 3 mil. Bruker bilen mer enn 15 liter? Skriv ja eller nei.",
     "ja", None),
    ("flervalg", "Hva er ∑ av de 5 første naturlige tallene {1,2,3,4,5}?",
     "15", ["10", "20", "25"]),
    ("steg",
     "📝 Finn absoluttverdien av −3 + (−7) + 4 steg for steg",
     "alle",
     [("Steg 1: Regn ut inni: −3 + (−7) + 4", "-6"),
      ("Steg 2: Ta absoluttverdien av svaret", "6"),
      ("Steg 3: Er svaret positivt eller negativt? Skriv positivt eller negativt", "positivt")]),
    ("tekst", "💡 En lampe tåler maks 60 watt. Du setter inn en 75 watt pære. Er dette for mye? Skriv ja eller nei.",
     "ja", None),
    ("flervalg", "Hva er |−100| : |−4|?",
     "25", ["−25", "400", "96"]),
    ("tekst", "🎲 Du kaster en terning 60 ganger. Du forventer ≈ 10 seksere. Stemmer dette med P(6) = 1/6 · 60?",
     "ja", None),
    ("finn_feilen",
     "🔍 Noen løste 5x − 10 > 20. Finn feilen!",
     "2",
     ["Legger til 10: 5x > 30",
      "Deler på 5: x > 3  ← FEIL (skal være x > 6)",
      "Konklusjon: x > 3"]),
    ("flervalg", "A = {1,2,3,4,5} og B = {4,5,6,7}. Hva er alle elementer som er i A eller B?",
     "{1,2,3,4,5,6,7}", ["{4,5}", "{1,2,3}", "{6,7}"]),
    ("tekst", "🏃 Lena løper mer enn 5 km per dag. På 7 dager løper hun mer enn ____ km?",
     "35", None),
    ("flervalg", "Hva er |−2³|?",
     "8", ["−8", "6", "3"]),
    ("tekst", "📊 En klasse tar prøve. Gjennomsnittet er ≈ 4,2 av 6. Hva er det nærmeste hele tallet?",
     "4", None),
    ("flervalg", "Hva er ∑ av {5, 10, 15, 20, 25}?",
     "75", ["55", "100", "65"]),
    ("tekst", "🌍 Havet stiger ≈ 3 mm per år. Hvor mye stiger det på 10 år (omtrent)?",
     "30", None),
    ("flervalg", "Er −5 ∈ {negative heltall}?",
     "Ja", ["Nei", "Kanskje", "Vet ikke"]),
    ("tekst", "💰 En vare koster 299 kr. Du har 300 kr. Har du nok? Skriv ja eller nei.",
     "ja", None),
    ("matching",
     "Match talltypen med eksempel",
     "riktig",
     [("Negativt tall", "−7"), ("Desimaltall", "3,14"), ("Naturlig tall", "5"), ("Null", "0")]),
    ("finn_feilen",
     "🔍 Noen regnet ∑ av {3, 5, 7, 9}. Finn feilen!",
     "2",
     ["Legger sammen: 3 + 5 = 8",
      "Legger til 7: 8 + 7 = 16  (men sa 14)  ← FEIL (8+7=15, ikke 14!)",
      "Legger til 9: 15 + 9 = 24"]),
    ("skriv",    "Hva er |−4| · 3 − |−2|?",                           "10", None),
    ("tekst", "🎯 x er et heltall og x² < 10. Hva er det største positive x kan være?",
     "3", None),
    ("flervalg", "Er påstanden '|x| er alltid positiv eller null' sann?",
     "Ja, alltid", ["Nei, kan være negativ", "Bare for positive x", "Bare for x = 0"]),
]


@app.route('/oppgaver/Tall og symboler/nivaa3', methods=['GET', 'POST'])
@login_required
def tall_symboler_nivaa3_route():
    return kjor_sette_inn(
        tall_symboler_nivaa3_oppgaver, 45000,
        "tall_symboler_nivaa3.html",
        "/oppgaver/Tall og symboler/nivaa3"
    )



# ─────────────────────────────────────────────
# SAMMENHENG MELLOM TO STØRRELSER
# ─────────────────────────────────────────────

@app.route('/oppgaver/sammenheng')
@login_required
def sammenheng():
    return render_template('oppgaver_sammenheng.html')


# NIVÅ 1 – lese tabeller og enkle formler (ID 46001–46030)
sammenheng_nivaa1_oppgaver = [
    ("tekst",
     "🚗 En bil kjører 60 km per time. Etter 3 timer, hvor langt har den kjørt?",
     "180", None),
    ("flervalg",
     "Tabellen viser sammenhengen mellom antall timer (x) og km kjørt (y):\n"
     "x: 1 → y: 60\nx: 2 → y: 120\nx: 3 → y: ?\nHva er y når x = 3?",
     "180", ["160", "200", "90"]),
    ("skriv",
     "Formelen er y = 5x. Hva er y når x = 4?",
     "20", None),
    ("flervalg",
     "y = 3x. Hva er y når x = 7?",
     "21", ["10", "73", "37"]),
    ("tekst",
     "🍕 En pizza koster 100 kr. Hva koster 4 pizzaer?",
     "400", None),
    ("flervalg",
     "Tabellen:\nx: 1 → y: 5\nx: 2 → y: 10\nx: 3 → y: 15\nx: 4 → y: ?\nHva er y når x = 4?",
     "20", ["16", "25", "14"]),
    ("skriv",
     "y = x + 8. Hva er y når x = 5?",
     "13", None),
    ("flervalg",
     "y = 2x + 1. Hva er y når x = 3?",
     "7", ["5", "9", "8"]),
    ("tekst",
     "🚶 Du går 4 km per time. Hvor langt går du på 2,5 timer?",
     "10", None),
    ("matching",
     "Match x-verdien med riktig y-verdi når y = 4x",
     "riktig",
     [("x = 1", "4"), ("x = 2", "8"), ("x = 3", "12"), ("x = 5", "20")]),
    ("flervalg",
     "y = 10x. Hva er y når x = 6?",
     "60", ["16", "106", "600"]),
    ("tekst",
     "💧 En kran fyller 8 liter per minutt. Hvor mye vann er det etter 5 minutter?",
     "40", None),
    ("skriv",
     "Tabellen:\nx: 0 → y: 2\nx: 1 → y: 4\nx: 2 → y: 6\nHva er formelen? Skriv y = ...",
     "y = 2x + 2", None),
    ("flervalg",
     "y = x - 3. Hva er y når x = 10?",
     "7", ["13", "30", "6"]),
    ("tekst",
     "🎮 Du tjener 50 poeng per level. Etter 6 levels, hvor mange poeng har du?",
     "300", None),
    ("finn_feilen",
     "🔍 Noen regnet y = 3x + 2 når x = 4. Finn feilen!",
     "2",
     ["Setter inn x = 4: 3·4 + 2",
      "Regner: 3·4 = 8  ← FEIL (3·4 = 12, ikke 8!)",
      "Legger til 2: 8 + 2 = 10"]),
    ("skriv",
     "y = 7x. Hva er y når x = 0?",
     "0", None),
    ("flervalg",
     "Tabellen:\nx: 2 → y: 6\nx: 4 → y: 12\nx: 6 → y: ?\nHva er y når x = 6?",
     "18", ["14", "16", "20"]),
    ("tekst",
     "🏊 Et svømmebasseng fylles med 200 liter per time. Etter 3 timer er det 600 liter. Er formelen y = 200x?",
     "ja", None),
    ("flervalg",
     "y = 2x + 3. Hva er y når x = 0?",
     "3", ["2", "5", "0"]),
    ("steg",
     "📝 En sykkel kjører 15 km per time. Sett opp og bruk formelen for x = 4 timer.",
     "alle",
     [("Steg 1: Skriv formelen (y = ? · x)", "y = 15x"),
      ("Steg 2: Sett inn x = 4: y = 15 · 4", "60"),
      ("Steg 3: Svaret i km", "60")]),
    ("tekst",
     "📦 En eske veier 2 kg. 5 esker veier ... kg?",
     "10", None),
    ("flervalg",
     "y = x². Hva er y når x = 4?",
     "16", ["8", "44", "12"]),
    ("skriv",
     "Tabellen:\nx: 1 → y: 3\nx: 2 → y: 6\nx: 3 → y: 9\nHva er y når x = 10?",
     "30", None),
    ("flervalg",
     "y = 5x − 1. Hva er y når x = 2?",
     "9", ["8", "10", "7"]),
    ("tekst",
     "🌡️ Temperaturen stiger 2°C per time. Start: 5°C. Hva er temperaturen etter 4 timer?",
     "13", None),
    ("flervalg",
     "Formelen y = 3x beskriver sammenhengen. Hva skjer med y når x dobles?",
     "y dobles også", ["y halveres", "y tredobles", "y forblir lik"]),
    ("skriv",
     "y = 4x + 5. Hva er y når x = 3?",
     "17", None),
    ("finn_feilen",
     "🔍 Noen leste tabellen og sa at formelen var y = 2x:\nx: 1 → y: 4\nx: 2 → y: 8\nx: 3 → y: 12\nFinne feilen!",
     "1",
     ["Formelen er y = 2x  ← FEIL (y = 4x passer, siden 4·1=4, 4·2=8, 4·3=12)",
      "Sjekk: 2·1 = 2, men tabellen sier 4",
      "Riktig formel er y = 4x"]),
    ("tekst",
     "💰 Du sparer 50 kr per uke. Etter 8 uker, hvor mye har du spart?",
     "400", None),
]


@app.route('/oppgaver/Sammenheng mellom to størrelser/nivaa1', methods=['GET', 'POST'])
@login_required
def sammenheng_nivaa1_route():
    return kjor_sette_inn(
        sammenheng_nivaa1_oppgaver, 46000,
        "sammenheng_nivaa1.html",
        "/oppgaver/Sammenheng mellom to størrelser/nivaa1"
    )


# NIVÅ 2 – finn formelen fra tabell og løs problemer (ID 47001–47030)
sammenheng_nivaa2_oppgaver = [
    ("flervalg",
     "Tabellen:\nx: 0 → y: 1\nx: 1 → y: 4\nx: 2 → y: 7\nx: 3 → y: 10\nHvilken formel passer?",
     "y = 3x + 1", ["y = x + 3", "y = 4x", "y = 3x"]),
    ("skriv",
     "Tabellen:\nx: 0 → y: 5\nx: 1 → y: 8\nx: 2 → y: 11\nHva er y når x = 5?",
     "20", None),
    ("tekst",
     "🚕 En taxi koster 30 kr i startpris pluss 12 kr per km. Hva koster en tur på 5 km?",
     "90", None),
    ("flervalg",
     "y = 2x + 4. Hva er x når y = 14?",
     "5", ["7", "9", "3"]),
    ("tekst",
     "🏃 Ole løper 8 km per time. Lena løper 6 km per time. Hvem har løpt lengst etter 3 timer?",
     "Ole", None),
    ("finn_feilen",
     "🔍 Noen fant formelen fra tabellen:\nx: 1 → y: 7, x: 2 → y: 12, x: 3 → y: 17\nSa at formelen er y = 5x + 1. Finn feilen!",
     "1",
     ["Ser på økningen: 12−7 = 5, 17−12 = 5 — stigning er 5  ✓",
      "Konstantleddet: y = 5·1 + b → 7 = 5 + b → b = 1  ← FEIL (b = 2, ikke 1!)",
      "Sjekk: 5·1 + 2 = 7  ✓, 5·2 + 2 = 12  ✓"]),
    ("skriv",
     "y = 2x + 3. For hvilken x-verdi er y = 11?",
     "4", None),
    ("flervalg",
     "Tabellen:\nx: 2 → y: 9\nx: 4 → y: 17\nx: 6 → y: 25\nHvilken formel passer?",
     "y = 4x + 1", ["y = 3x + 3", "y = 4x", "y = 5x − 1"]),
    ("tekst",
     "💡 En pærebutikk selger pærer for 3 kr stykket og tar 10 kr i levering. Hva koster 8 pærer totalt?",
     "34", None),
    ("matching",
     "Match formelen med riktig y-verdi når x = 3",
     "riktig",
     [("y = 2x + 1", "7"), ("y = 3x − 2", "7 — nei, det er 7"), ("y = 5x", "15"), ("y = x² + 1", "10")]),
    ("skriv",
     "Tabellen:\nx: 1 → y: 6\nx: 2 → y: 11\nx: 3 → y: 16\nHva er formelen?",
     "y = 5x + 1", None),
    ("flervalg",
     "En bil bruker 0,8 liter per km. Hvor mange liter trenger den for 50 km?",
     "40", ["45", "30", "35"]),
    ("tekst",
     "🎯 En formel er y = 4x − 2. Hva er y når x = 6?",
     "22", None),
    ("finn_feilen",
     "🔍 Noen løste y = 3x + 5 for x når y = 20. Finn feilen!",
     "2",
     ["Setter y = 20: 3x + 5 = 20",
      "Trekker fra 5: 3x = 20  ← FEIL (skal være 3x = 15)",
      "Deler på 3: x = 5"]),
    ("steg",
     "📝 En mobilplan koster 99 kr per måned + 0,50 kr per SMS. Sett opp formelen og finn kostnaden for 40 SMS.",
     "alle",
     [("Steg 1: Skriv formelen (la x = antall SMS)", "y = 0,5x + 99"),
      ("Steg 2: Sett inn x = 40: y = 0,5 · 40 + 99", "119"),
      ("Steg 3: Hva koster planen den måneden?", "119")]),
    ("skriv",
     "y = 6x − 3. Hva er x når y = 9?",
     "2", None),
    ("flervalg",
     "Tabellen:\nx: 0 → y: 10\nx: 5 → y: 20\nx: 10 → y: 30\nHva er formelen?",
     "y = 2x + 10", ["y = x + 10", "y = 3x + 10", "y = 2x"]),
    ("tekst",
     "🏊 Bassenget har 500 liter. Det tapper ut 25 liter per minutt. Hvor mye er igjen etter 8 minutter?",
     "300", None),
    ("flervalg",
     "y = −2x + 10. Hva er y når x = 3?",
     "4", ["16", "7", "−4"]),
    ("tekst",
     "📱 Du har 100 kr internett igjen. Du bruker 4 kr per dag. Etter hvor mange dager er det tomt?",
     "25", None),
    ("skriv",
     "Tabellen:\nx: 1 → y: 2\nx: 2 → y: 5\nx: 3 → y: 10\nx: 4 → y: 17\nHva er formelen?",
     "y = x² + 1", None),
    ("flervalg",
     "En formel er y = 3x + 6. Hva skjer med y når x øker med 1?",
     "y øker med 3", ["y øker med 6", "y øker med 1", "y øker med 9"]),
    ("tekst",
     "🚲 Sykkel A: 15 km/t. Sykkel B: y = 10x + 5. Hvem er raskest etter 2 timer?",
     "Sykkel A", None),
    ("matching",
     "Match situasjonen med riktig formel",
     "riktig",
     [("Taxi: 30 kr start + 10 kr/km", "y = 10x + 30"),
      ("Spare 50 kr/uke", "y = 50x"),
      ("Basseng tapper 20 liter/min fra 400 liter", "y = 400 − 20x"),
      ("Temperatur stiger 3°C/time fra 5°C", "y = 3x + 5")]),
    ("skriv",
     "y = −5x + 50. For hvilken x er y = 0?",
     "10", None),
    ("flervalg",
     "To størrelser er proporsjonale. Når x = 3 er y = 12. Hva er y når x = 7?",
     "28", ["21", "16", "35"]),
    ("tekst",
     "💰 Du leier en sykkel for 20 kr per time. Har du råd til 4 timer for 100 kr?",
     "ja", None),
    ("skriv",
     "Tabellen:\nx: 0 → y: 0\nx: 2 → y: 6\nx: 4 → y: 12\nHva er formelen?",
     "y = 3x", None),
    ("finn_feilen",
     "🔍 Noen sa at y = 2x og y = x + 5 aldri kan ha samme verdi. Finn feilen!",
     "1",
     ["Påstanden er at de aldri er like  ← FEIL",
      "Setter lik: 2x = x + 5 → x = 5",
      "Når x = 5: y = 10 i begge — de er like!"]),
    ("tekst",
     "🌡️ Formelen C = (F − 32) : 1,8 gir Celsius fra Fahrenheit. Hva er Celsius når F = 32?",
     "0", None),
]


@app.route('/oppgaver/Sammenheng mellom to størrelser/nivaa2', methods=['GET', 'POST'])
@login_required
def sammenheng_nivaa2_route():
    return kjor_sette_inn(
        sammenheng_nivaa2_oppgaver, 47000,
        "sammenheng_nivaa2.html",
        "/oppgaver/Sammenheng mellom to størrelser/nivaa2"
    )


# NIVÅ 3 – sammensatte sammenhenger og tekstoppgaver (ID 48001–48030)
sammenheng_nivaa3_oppgaver = [
    ("tekst",
     "🚗 Bil A kjører y = 80x km. Bil B kjører y = 60x + 40 km. Etter hvor mange timer er de like langt unna? (Løs: 80x = 60x + 40)",
     "2", None),
    ("flervalg",
     "To størrelser er omvendt proporsjonale. Når x = 2 er y = 12. Hva er y når x = 4?",
     "6", ["24", "10", "8"]),
    ("tekst",
     "💰 Plan A: 200 kr fast + 5 kr/min. Plan B: 10 kr/min. Etter hvor mange minutter koster de like mye?",
     "40", None),
    ("finn_feilen",
     "🔍 Noen sammenlignet y = 4x og y = 2x + 8. Sa de møtes ved x = 2. Finn feilen!",
     "2",
     ["Setter lik: 4x = 2x + 8",
      "Trekker fra 2x: 4x = 8 → x = 2  ← FEIL (4x − 2x = 2x, ikke 4x!)",
      "Riktig: 2x = 8 → x = 4"]),
    ("skriv",
     "y = x² − 2x. Hva er y når x = 5?",
     "15", None),
    ("flervalg",
     "En ball kastes opp. Høyden er h = −5t² + 20t. Hva er høyden etter t = 2 sekunder?",
     "20", ["30", "40", "10"]),
    ("tekst",
     "🏃 Lena starter 100 m foran Ole. Ole løper 8 m/s, Lena løper 5 m/s. Etter hvor mange sekunder tar Ole igjen Lena?",
     "33", None),
    ("steg",
     "📝 To planer: Plan A: y = 3x + 10. Plan B: y = 5x. Finn når de er like.",
     "alle",
     [("Steg 1: Sett lik hverandre: 3x + 10 = 5x", "3x + 10 = 5x"),
      ("Steg 2: Trekk 3x fra begge sider: 10 = ?", "2x"),
      ("Steg 3: Del på 2: x = ?", "5"),
      ("Steg 4: Finn y ved å sette inn x = 5 i 5x", "25")]),
    ("flervalg",
     "Tabellen:\nx: 1 → y: 1\nx: 2 → y: 4\nx: 3 → y: 9\nx: 4 → y: 16\nHvilken formel passer?",
     "y = x²", ["y = 4x", "y = 2x + 1", "y = x + 3"]),
    ("tekst",
     "📊 Befolkningen dobles hvert 10. år. Nå er det 1000 innbyggere. Etter 20 år er det?",
     "4000", None),
    ("flervalg",
     "y = 2x² − 3x + 1. Hva er y når x = 3?",
     "10", ["14", "8", "16"]),
    ("tekst",
     "🌊 Bølgehøyden er h = 0,5t² der t er tid i sekunder. Hva er høyden etter t = 4?",
     "8", None),
    ("finn_feilen",
     "🔍 Noen sa at y = x² alltid vokser raskere enn y = 10x. Finn feilen!",
     "1",
     ["Påstanden er at x² alltid > 10x  ← FEIL",
      "For x = 5: x² = 25, men 10x = 50 — her er 10x større",
      "x² > 10x bare når x > 10"]),
    ("skriv",
     "Butikk A: y = 4x + 20. Butikk B: y = 6x. Hvilken er billigst når x = 8?",
     "Butikk A", None),
    ("flervalg",
     "h = −5t² + 30t. Hva er maks høyde? (Maks ved t = 3)",
     "45", ["30", "60", "90"]),
    ("tekst",
     "🚕 Taxi A: 50 + 8 kr/km. Taxi B: 20 + 11 kr/km. Etter hvor mange km koster de likt?",
     "10", None),
    ("matching",
     "Match sammenhengen med riktig type",
     "riktig",
     [("y = 3x", "Rett proporsjonal"),
      ("y = 3x + 5", "Lineær, ikke proporsjonal"),
      ("y = x²", "Kvadratisk"),
      ("y = 10/x", "Omvendt proporsjonal")]),
    ("skriv",
     "y = −3x + 21. For hvilken x er y = 0?",
     "7", None),
    ("tekst",
     "💡 Strøm koster 1,5 kr per kWh. Du bruker x kWh per dag. Månedlig kostnad (30 dager) er?",
     "45x", None),
    ("flervalg",
     "To størrelser: x dobles → y firedobles. Hva slags sammenheng er dette?",
     "Kvadratisk (y = x²)", ["Lineær", "Proporsjonal", "Omvendt proporsjonal"]),
    ("tekst",
     "🏦 Du låner 10 000 kr og betaler 500 kr per måned. Etter hvor mange måneder er gjelden under 3000 kr?",
     "15", None),
    ("skriv",
     "Formelen er y = 2x² + x. Hva er y når x = 4?",
     "36", None),
    ("flervalg",
     "y = 12/x. Hva er y når x = 3?",
     "4", ["6", "9", "36"]),
    ("tekst",
     "🌡️ C = (F − 32) · 5/9. Hva er temperaturen i Celsius når F = 68?",
     "20", None),
    ("finn_feilen",
     "🔍 Noen løste 2x + 6 = 4x − 2. Finn feilen!",
     "2",
     ["Trekker 2x fra begge sider: 6 = 2x − 2",
      "Legger til 2: 8 = 2x → x = 2  ← FEIL (8/2 = 4, ikke 2!)",
      "Riktig: x = 4"]),
    ("skriv",
     "Tabell:\nx: 1 → y: 5\nx: 2 → y: 11\nx: 3 → y: 19\nx: 4 → y: 29\nHva er y når x = 5?",
     "41", None),
    ("flervalg",
     "En formel er y = ax + b. Når x = 0 er y = 4 og når x = 2 er y = 10. Hva er a?",
     "3", ["2", "5", "4"]),
    ("tekst",
     "🎯 Kula treffer blinken etter t sekunder: s = 5t. Skiva er 35 m unna. Etter hvor mange sekunder treffer kula?",
     "7", None),
    ("steg",
     "📝 Finn formelen y = ax + b fra tabellen: x=0→y=3, x=1→y=7, x=2→y=11",
     "alle",
     [("Steg 1: Finn stigning a (økning i y per x)", "4"),
      ("Steg 2: Finn b (y-verdi når x = 0)", "3"),
      ("Steg 3: Skriv formelen", "y = 4x + 3"),
      ("Steg 4: Hva er y når x = 5?", "23")]),
    ("tekst",
     "💰 Du og kompisen sparer. Du har y = 50x + 100 kr. Han har y = 80x. Etter hvor mange uker har han mer enn deg?",
     "4", None),
]


@app.route('/oppgaver/Sammenheng mellom to størrelser/nivaa3', methods=['GET', 'POST'])
@login_required
def sammenheng_nivaa3_route():
    return kjor_sette_inn(
        sammenheng_nivaa3_oppgaver, 48000,
        "sammenheng_nivaa3.html",
        "/oppgaver/Sammenheng mellom to størrelser/nivaa3"
    )



# ─────────────────────────────────────────────
# FUNKSJONSTABELLER
# ─────────────────────────────────────────────

@app.route('/oppgaver/funksjonstabeller')
@login_required
def funksjonstabeller():
    return render_template('oppgaver_funksjonstabeller.html')


def kjor_funkstabell(oppgaver, id_base, template_navn, link_prefix):
    """Kjører funksjonstabeller — støtter type 'tabell' i tillegg til alle sette_inn-typer."""
    import json
    nummer = int(request.args.get("n", 1))
    total = len(oppgaver)
    oppgave_id = id_base + nummer

    if nummer > total:
        return render_template("ferdig.html", tittel="Funksjonstabeller", melding="Du fullførte dette nivået! 🎉")

    o = oppgaver[nummer - 1]
    type_ = o[0]
    oppgave_html = o[1]
    fasit = o[2]
    ekstra = o[3]

    alternativer = []
    steg_liste = []
    par_liste = []
    par_liste_blandet = []
    tabell_headers = []
    tabell_rader = []
    tabell_svar = []
    tabell_labels = []

    if type_ == "flervalg":
        alternativer = _fv_tall(fasit, ekstra)
    elif type_ == "finn_feilen":
        steg_liste = ekstra
    elif type_ == "matching":
        par_liste = ekstra
        par_liste_blandet = lag_blandet_matching(ekstra)
    elif type_ == "steg":
        steg_liste = [s[0] for s in ekstra]
    elif type_ == "tabell":
        # ekstra = (headers, rader_med_?, svar_liste, labels_liste)
        tabell_headers = ekstra[0]
        tabell_rader = ekstra[1]
        tabell_svar = ekstra[2]
        tabell_labels = ekstra[3]
        steg_liste = tabell_labels  # reuse steg-mekanisme for inputs

    resultat = ""
    riktig = None
    tabell_feil_indekser = []
    tabell_innsendte = []
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        ok = False

        if type_ in ["skriv", "tekst"]:
            svar = request.form.get("svar", "").strip().replace(".", ",")
            ok = svar.lower() == fasit.lower().replace(".", ",")
            if svar == "67":
                resultat = "🤡🤮 Du er ikke morsom 🖕"
                ok = False

        elif type_ == "flervalg":
            svar = request.form.get("svar_flervalg", "").strip()
            ok = svar.lower() == fasit.lower()
            if svar == "67":
                resultat = "🤡🤮 Du er ikke morsom 🖕"
                ok = False

        elif type_ == "finn_feilen":
            ok = request.form.get("svar_flervalg", "").strip() == fasit

        elif type_ == "matching":
            svar_json = request.form.get("matching_svar", "{}")
            riktige = {str(i+1): str(i+1) for i in range(len(ekstra))}
            ok = sjekk_matching(svar_json, riktige)

        elif type_ in ["steg", "tabell"]:
            svar_liste = tabell_svar if type_ == "tabell" else [s[1] for s in ekstra]
            innsendte = [request.form.get(f"steg_{i+1}", "").strip() for i in range(len(svar_liste))]
            if type_ == "tabell":
                tabell_innsendte = innsendte
            alle_riktige = all(
                innsendte[i].replace(".", ",").lower()
                == str(svar_liste[i]).replace(".", ",").lower()
                for i in range(len(svar_liste))
            )
            if alle_riktige:
                ok = True
            else:
                feil_idx = [i for i in range(len(svar_liste))
                            if innsendte[i].replace(".", ",").lower()
                            != str(svar_liste[i]).replace(".", ",").lower()]
                if type_ == "tabell":
                    tabell_feil_indekser = feil_idx
                feil = [tabell_labels[i] if type_ == "tabell" else ekstra[i][0]
                        for i in feil_idx]
                resultat = "❌ Feil i: " + ", ".join(feil)

        if ok:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status, timestamp) VALUES (?, ?, ?, datetime('now'))",
                (session["user_id"], oppgave_id, "riktig"))
            conn.commit()
            riktige_oppgaver.add(oppgave_id)
        elif not resultat:
            resultat = "❌ Feil, prøv igjen!"
            riktig = False

    venstre_meny = [{"nummer": i, "id": id_base + i, "link": f"{link_prefix}?n={i}"} for i in range(1, total + 1)]
    return render_template(template_navn,
        oppgave_html=f'<p class="task-question-text">{oppgave_html}</p>',
        type=type_, alternativer=alternativer,
        steg_liste=steg_liste,
        par_liste=par_liste, par_liste_blandet=par_liste_blandet,
        tabell_headers=tabell_headers, tabell_rader=tabell_rader,
        tabell_svar=tabell_svar, tabell_labels=tabell_labels,
        nummer=nummer, total=total, resultat=resultat, riktig=riktig,
        oppgave_nummer=nummer, oppgaver=venstre_meny, riktige_oppgaver=riktige_oppgaver
    )


# NIVÅ 1 – lese og fylle inn enkle funksjonstabeller (ID 49001–49030)
# Ny type "tabell": (headers, rader, svar_liste, labels)
funksjonstabeller_nivaa1_oppgaver = [
    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 2x",
     "alle",
     (["x", "y = 2x"],
      [["0","?"],["1","?"],["2","?"],["3","?"]],
      ["0","2","4","6"],
      ["y når x=0","y når x=1","y når x=2","y når x=3"])),

    ("flervalg",
     "Tabellen for y = 3x:\nx=1→y=3, x=2→y=6, x=3→y=9\nHva er y når x=5?",
     "15", ["12","18","10"]),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = x + 5",
     "alle",
     (["x", "y = x + 5"],
      [["1","?"],["2","?"],["3","?"],["4","?"]],
      ["6","7","8","9"],
      ["y når x=1","y når x=2","y når x=3","y når x=4"])),

    ("skriv",
     "Tabellen for y = 4x:\nx=0→?, x=1→4, x=2→8\nHva er y når x=0?",
     "0", None),

    ("tekst",
     "🚗 En bil kjører 70 km/t. Fullfør tabellen:\n1 time → 70 km\n2 timer → 140 km\n3 timer → ? km",
     "210", None),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 5x − 1",
     "alle",
     (["x", "y = 5x − 1"],
      [["1","?"],["2","?"],["3","?"],["4","?"]],
      ["4","9","14","19"],
      ["y når x=1","y når x=2","y når x=3","y når x=4"])),

    ("flervalg",
     "Tabellen:\nx=0→y=3\nx=1→y=5\nx=2→y=7\nx=3→y=?\nHva er y når x=3?",
     "9", ["8","10","11"]),

    ("matching",
     "Match x-verdien med riktig y-verdi for y = 3x + 2",
     "riktig",
     [("x = 0","2"),("x = 1","5"),("x = 2","8"),("x = 3","11")]),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 10x",
     "alle",
     (["x","y = 10x"],
      [["2","?"],["4","?"],["6","?"],["8","?"]],
      ["20","40","60","80"],
      ["y når x=2","y når x=4","y når x=6","y når x=8"])),

    ("skriv",
     "y = x + 7. Tabellen: x=3→?, x=5→12, x=8→15\nHva er y når x=3?",
     "10", None),

    ("tekst",
     "💧 En kran fyller 5 liter per minutt.\n1 min → 5 l\n2 min → 10 l\n4 min → ? l",
     "20", None),

    ("finn_feilen",
     "🔍 Noen laget tabell for y = 2x + 1. Finn feilen!",
     "2",
     ["x=0: 2·0+1 = 1  ✓",
      "x=1: 2·1+1 = 4  ← FEIL (skal være 3)",
      "x=2: 2·2+1 = 5  ✓",
      "x=3: 2·3+1 = 7  ✓"]),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = x²",
     "alle",
     (["x","y = x²"],
      [["1","?"],["2","?"],["3","?"],["4","?"]],
      ["1","4","9","16"],
      ["y når x=1","y når x=2","y når x=3","y når x=4"])),

    ("flervalg",
     "Tabellen for y = x²:\nx=1→1, x=2→4, x=3→9, x=4→?\nHva er y når x=4?",
     "16", ["12","20","8"]),

    ("skriv",
     "y = 6x. Tabellen:\nx=0→0, x=1→6, x=2→12\nHva er y når x=7?",
     "42", None),

    ("tekst",
     "🎮 Du får 10 poeng per level. Fullfør tabellen:\n1 level → 10 poeng\n3 levels → 30 poeng\n6 levels → ? poeng",
     "60", None),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 3x + 4",
     "alle",
     (["x","y = 3x + 4"],
      [["0","?"],["1","?"],["2","?"],["5","?"]],
      ["4","7","10","19"],
      ["y når x=0","y når x=1","y når x=2","y når x=5"])),

    ("flervalg",
     "y = 2x − 3. Tabellen:\nx=2→1, x=3→3, x=4→?\nHva er y når x=4?",
     "5", ["6","4","8"]),

    ("steg",
     "📝 Lag tabell for y = 4x når x = 1, 2, 3, 4",
     "alle",
     [("y når x = 1","4"),
      ("y når x = 2","8"),
      ("y når x = 3","12"),
      ("y når x = 4","16")]),

    ("skriv",
     "Tabellen:\nx=1→y=8\nx=2→y=16\nx=3→y=24\nHva er y når x=10?",
     "80", None),

    ("tekst",
     "📦 En pakke veier 3 kg. Tabellen:\n1 pakke → 3 kg\n2 pakker → 6 kg\n5 pakker → ? kg",
     "15", None),

    ("finn_feilen",
     "🔍 Noen laget tabell for y = x + 4. Finn feilen!",
     "3",
     ["x=1: 1+4=5  ✓",
      "x=2: 2+4=6  ✓",
      "x=3: 3+4=8  ← FEIL (skal være 7)",
      "x=4: 4+4=8  ✓"]),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 2x + 3",
     "alle",
     (["x","y = 2x + 3"],
      [["0","?"],["2","?"],["4","?"],["6","?"]],
      ["3","7","11","15"],
      ["y når x=0","y når x=2","y når x=4","y når x=6"])),

    ("flervalg",
     "Tabellen for y = 7x:\nx=1→7, x=2→14, x=3→21\nHvilken verdi hører IKKE hjemme?",
     "x=4→30", ["x=4→28","x=5→35","x=6→42"]),

    ("skriv",
     "y = 3x − 2. Hva er y når x = 0?",
     "-2", None),

    ("tekst",
     "🌡️ Temperaturen stiger 2°C per time fra 4°C.\n1 time → 6°C\n2 timer → 8°C\n5 timer → ?°C",
     "14", None),

    ("matching",
     "Match formelen med riktig tabell-rad (x=3)",
     "riktig",
     [("y = 2x","6"),("y = x + 5","8"),("y = 3x − 1","8 — nei, 8"),("y = 10 − x","7")]),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 20 − 3x",
     "alle",
     (["x","y = 20 − 3x"],
      [["0","?"],["2","?"],["4","?"],["6","?"]],
      ["20","14","8","2"],
      ["y når x=0","y når x=2","y når x=4","y når x=6"])),

    ("flervalg",
     "Tabellen for y = x + 3:\nx=0→3, x=1→4, x=2→5\nHva er x når y = 10?",
     "7", ["6","8","9"]),

    ("steg",
     "📝 Lag tabell for y = x² + 1 når x = 0, 1, 2, 3",
     "alle",
     [("y når x=0","1"),
      ("y når x=1","2"),
      ("y når x=2","5"),
      ("y når x=3","10")]),

    # --- NYE OPPGAVER (tabellutfylling) ---
    ("tabell",
     "📋 Fyll inn tabellen for f(x) = x + 10",
     "alle",
     (["x", "y = x + 10"],
      [["0","?"],["5","?"],["10","?"],["15","?"]],
      ["10","15","20","25"],
      ["y når x=0","y når x=5","y når x=10","y når x=15"])),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 4x",
     "alle",
     (["x", "y = 4x"],
      [["0","?"],["2","?"],["5","?"],["10","?"]],
      ["0","8","20","40"],
      ["y når x=0","y når x=2","y når x=5","y når x=10"])),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 6x − 2",
     "alle",
     (["x", "y = 6x − 2"],
      [["1","?"],["2","?"],["3","?"],["4","?"]],
      ["4","10","16","22"],
      ["y når x=1","y når x=2","y når x=3","y når x=4"])),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 2x + 6",
     "alle",
     (["x", "y = 2x + 6"],
      [["0","?"],["3","?"],["6","?"],["9","?"]],
      ["6","12","18","24"],
      ["y når x=0","y når x=3","y når x=6","y når x=9"])),

    ("tabell",
     "🛒 En butikk selger is til 15 kr stykket.\n📋 Fyll inn tabellen (x = antall is, y = pris i kr)",
     "alle",
     (["x (antall)", "y (kr)"],
      [["1","?"],["2","?"],["5","?"],["10","?"]],
      ["15","30","75","150"],
      ["y når x=1","y når x=2","y når x=5","y når x=10"])),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 30 − 5x",
     "alle",
     (["x", "y = 30 − 5x"],
      [["0","?"],["2","?"],["4","?"],["6","?"]],
      ["30","20","10","0"],
      ["y når x=0","y når x=2","y når x=4","y når x=6"])),

    ("tabell",
     "🚴 En syklist sykler 15 km/t.\n📋 Fyll inn tabellen (x = timer, y = km)",
     "alle",
     (["x (timer)", "y (km)"],
      [["1","?"],["2","?"],["3","?"],["4","?"]],
      ["15","30","45","60"],
      ["y når x=1","y når x=2","y når x=3","y når x=4"])),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = x² + x",
     "alle",
     (["x", "y = x² + x"],
      [["1","?"],["2","?"],["3","?"],["4","?"]],
      ["2","6","12","20"],
      ["y når x=1","y når x=2","y når x=3","y når x=4"])),

    ("flervalg",
     "Tabellen for y = 5x:\nx=1→5, x=2→10, x=3→15\nHva er y når x=8?",
     "40", ["35","45","25"]),

    ("skriv",
     "Tabellen:\nx=0→y=0\nx=1→y=7\nx=2→y=14\nHva er y når x=6?",
     "42", None),

]


@app.route('/oppgaver/Funksjonstabeller/nivaa1', methods=['GET', 'POST'])
@login_required
def funksjonstabeller_nivaa1_route():
    return kjor_funkstabell(
        funksjonstabeller_nivaa1_oppgaver, 49000,
        "funksjonstabeller_nivaa1.html",
        "/oppgaver/Funksjonstabeller/nivaa1"
    )


# NIVÅ 2 – finne formelen fra en tabell (ID 50001–50030)
funksjonstabeller_nivaa2_oppgaver = [
    ("flervalg",
     "Tabellen:\nx=0→y=2, x=1→y=5, x=2→y=8, x=3→y=11\nHvilken formel passer?",
     "y = 3x + 2", ["y = 2x + 3","y = 3x","y = x + 4"]),

    ("skriv",
     "Tabellen:\nx=1→y=7, x=2→y=12, x=3→y=17\nHva er stigningen (økning i y per x)?",
     "5", None),

    ("steg",
     "📝 Finn formelen fra tabellen:\nx=0→y=1, x=1→y=4, x=2→y=7",
     "alle",
     [("Steg 1: Finn stigning (økning per x)","3"),
      ("Steg 2: Finn konstantledd b (y når x=0)","1"),
      ("Steg 3: Skriv formelen y = ax + b","y = 3x + 1"),
      ("Steg 4: Hva er y når x = 5?","16")]),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 4x − 3",
     "alle",
     (["x","y = 4x − 3"],
      [["1","?"],["3","?"],["5","?"],["7","?"]],
      ["1","9","17","25"],
      ["y når x=1","y når x=3","y når x=5","y når x=7"])),

    ("flervalg",
     "Tabellen:\nx=2→y=7, x=4→y=13, x=6→y=19\nHvilken formel passer?",
     "y = 3x + 1", ["y = 2x + 3","y = 3x","y = 4x − 1"]),

    ("tekst",
     "🚕 Taxi: x=1→y=42, x=2→y=54, x=3→y=66 (x=km, y=pris i kr)\nHva er startprisen (b)?",
     "30", None),

    ("finn_feilen",
     "🔍 Noen fant formelen fra x=0→y=4, x=1→y=7, x=2→y=10.\nSa formelen er y = 4x + 3. Finn feilen!",
     "1",
     ["Formelen er y = 4x + 3  ← FEIL (stigningen er 3, ikke 4)",
      "Sjekk: 4·1+3=7 og 4·2+3=11 (men tabellen sier 10)",
      "Riktig: y = 3x + 4"]),

    ("skriv",
     "Tabellen:\nx=0→y=10, x=2→y=16, x=4→y=22\nHva er formelen?",
     "y = 3x + 10", None),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = −2x + 8",
     "alle",
     (["x","y = −2x + 8"],
      [["0","?"],["1","?"],["2","?"],["4","?"]],
      ["8","6","4","0"],
      ["y når x=0","y når x=1","y når x=2","y når x=4"])),

    ("flervalg",
     "Tabellen:\nx=1→y=3, x=2→y=9, x=3→y=27\nHva slags sammenheng er dette?",
     "Eksponentiell (3^x)", ["Lineær","Kvadratisk","Proporsjonal"]),

    ("tekst",
     "💡 x=1→y=10, x=2→y=20, x=3→y=30\nEr dette en proporsjonal sammenheng? Skriv ja eller nei.",
     "ja", None),

    ("matching",
     "Match tabellen med riktig formel",
     "riktig",
     [("x=0→2, x=1→5, x=2→8","y = 3x + 2"),
      ("x=0→0, x=1→4, x=2→8","y = 4x"),
      ("x=0→5, x=1→4, x=2→3","y = −x + 5"),
      ("x=1→3, x=2→9, x=3→19","y = x² + 2")]),

    ("skriv",
     "Tabellen:\nx=0→y=6, x=3→y=18, x=6→y=30\nHva er y når x=10?",
     "46", None),

    ("tabell",
     "📋 Lag tabell for f(x) = x² − x når x = 1, 2, 3, 4",
     "alle",
     (["x","y = x² − x"],
      [["1","?"],["2","?"],["3","?"],["4","?"]],
      ["0","2","6","12"],
      ["y når x=1","y når x=2","y når x=3","y når x=4"])),

    ("flervalg",
     "Formelen y = ax + b. Tabellen sier: x=0→y=3 og x=1→y=7.\nHva er a?",
     "4", ["3","7","1"]),

    ("finn_feilen",
     "🔍 Noen laget tabell for y = −3x + 9. Finn feilen!",
     "3",
     ["x=0: −3·0+9 = 9  ✓",
      "x=1: −3·1+9 = 6  ✓",
      "x=2: −3·2+9 = 4  ← FEIL (skal være 3)",
      "x=3: −3·3+9 = 0  ✓"]),

    ("tekst",
     "📊 Tabellen for en butikk:\nx (antall varer) = 5 → y (inntekt) = 75\nx = 10 → y = 150\nHva er prisen per vare?",
     "15", None),

    ("steg",
     "📝 Finn formelen fra tabellen:\nx=2→y=9, x=4→y=17, x=6→y=25",
     "alle",
     [("Steg 1: Finn stigning: (17−9)/(4−2)","4"),
      ("Steg 2: Bruk y = 4x + b: 9 = 4·2 + b → b = ?","1"),
      ("Steg 3: Skriv formelen","y = 4x + 1"),
      ("Steg 4: Hva er y når x = 8?","33")]),

    ("skriv",
     "Tabellen:\nx=1→y=4, x=2→y=7, x=3→y=10\nHva er x når y=19?",
     "6", None),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 2x²",
     "alle",
     (["x","y = 2x²"],
      [["1","?"],["2","?"],["3","?"],["4","?"]],
      ["2","8","18","32"],
      ["y når x=1","y når x=2","y når x=3","y når x=4"])),

    ("flervalg",
     "Tabellen:\nx=0→y=0, x=1→y=2, x=2→y=8, x=3→y=18\nHvilken formel passer?",
     "y = 2x²", ["y = 2x","y = x² + x","y = 3x²"]),

    ("tekst",
     "🏊 Basseng: x=0→500 l, x=5→375 l, x=10→250 l\nHvor mange liter tappes per minutt?",
     "25", None),

    ("skriv",
     "Tabellen:\nx=0→y=−2, x=1→y=1, x=2→y=4, x=3→y=7\nHva er formelen?",
     "y = 3x − 2", None),

    ("finn_feilen",
     "🔍 Tabellen: x=1→6, x=2→11, x=3→16.\nNoen sa formelen er y = 5x. Finn feilen!",
     "1",
     ["Formelen er y = 5x  ← FEIL (sjekk: 5·1=5, men tabellen sier 6)",
      "Stigningen er 5  ✓",
      "Konstantleddet: y = 5·1 + b → 6 = 5 + b → b = 1",
      "Riktig formel: y = 5x + 1"]),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 100 − 10x",
     "alle",
     (["x","y = 100 − 10x"],
      [["0","?"],["3","?"],["7","?"],["10","?"]],
      ["100","70","30","0"],
      ["y når x=0","y når x=3","y når x=7","y når x=10"])),

    ("flervalg",
     "y = ax + 4. Når x = 3 er y = 13. Hva er a?",
     "3", ["4","9","2"]),

    ("skriv",
     "Tabellen:\nx=0→y=5, x=1→y=10, x=2→y=20, x=3→y=40\nHva er mønsteret? (Skriv dobles, tredobles, eller kvadreres)",
     "dobles", None),

    ("tekst",
     "💰 Plan A: y = 6x + 10. Plan B: y = 8x.\nVed hvilken x-verdi er Plan B billigst?",
     "5", None),

    ("steg",
     "📝 Tabell: x=0→3, x=2→7, x=4→11\nFinn formelen og bruk den.",
     "alle",
     [("Steg 1: Stigning a = (7−3)/(2−0)","2"),
      ("Steg 2: Konstantledd b (y når x=0)","3"),
      ("Steg 3: Formelen","y = 2x + 3"),
      ("Steg 4: Hva er y når x=6?","15")]),

    ("matching",
     "Match x-verdien med riktig y-verdi for y = 5x − 2",
     "riktig",
     [("x=1","3"),("x=2","8"),("x=3","13"),("x=4","18")]),

    # --- NYE OPPGAVER NIVÅ 2 (tabellutfylling + finn formel) ---
    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 3x − 5",
     "alle",
     (["x", "y = 3x − 5"],
      [["2","?"],["4","?"],["6","?"],["8","?"]],
      ["1","7","13","19"],
      ["y når x=2","y når x=4","y når x=6","y når x=8"])),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 0.5x + 3",
     "alle",
     (["x", "y = 0.5x + 3"],
      [["0","?"],["2","?"],["4","?"],["6","?"]],
      ["3","4","5","6"],
      ["y når x=0","y når x=2","y når x=4","y når x=6"])),

    ("tabell",
     "🏃 En jogger øker farten gradvis: y = 2x + 5 km/t (x = minutter).\n📋 Fyll inn tabellen",
     "alle",
     (["x (min)", "y = 2x + 5"],
      [["0","?"],["5","?"],["10","?"],["15","?"]],
      ["5","15","25","35"],
      ["y når x=0","y når x=5","y når x=10","y når x=15"])),

    ("steg",
     "📝 Finn formelen fra tabellen:\nx=0→y=4, x=2→y=10, x=4→y=16",
     "alle",
     [("Steg 1: Finn stigning: (10−4)/(2−0)","3"),
      ("Steg 2: Konstantledd b (y når x=0)","4"),
      ("Steg 3: Skriv formelen y = ax + b","y = 3x + 4"),
      ("Steg 4: Hva er y når x = 6?","22")]),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = x² − 1",
     "alle",
     (["x", "y = x² − 1"],
      [["1","?"],["2","?"],["3","?"],["4","?"]],
      ["0","3","8","15"],
      ["y når x=1","y når x=2","y når x=3","y når x=4"])),

    ("tabell",
     "💵 Taxipris: y = 12x + 25 (x = km, y = pris i kr).\n📋 Fyll inn tabellen",
     "alle",
     (["x (km)", "y (kr)"],
      [["1","?"],["3","?"],["5","?"],["10","?"]],
      ["37","61","85","145"],
      ["y når x=1","y når x=3","y når x=5","y når x=10"])),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = −3x + 12",
     "alle",
     (["x", "y = −3x + 12"],
      [["0","?"],["2","?"],["3","?"],["4","?"]],
      ["12","6","3","0"],
      ["y når x=0","y når x=2","y når x=3","y når x=4"])),

    ("flervalg",
     "Tabellen:\nx=0→y=1, x=1→y=3, x=2→y=9, x=3→y=27\nHva slags sammenheng er dette?",
     "Eksponentiell (3^x)", ["Lineær","Kvadratisk","Proporsjonal"]),

    ("skriv",
     "Tabellen:\nx=1→y=6, x=3→y=14, x=5→y=22\nHva er formelen? (formen y = ax + b)",
     "y = 4x + 2", None),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 5x²",
     "alle",
     (["x", "y = 5x²"],
      [["1","?"],["2","?"],["3","?"],["4","?"]],
      ["5","20","45","80"],
      ["y når x=1","y når x=2","y når x=3","y når x=4"])),

]


@app.route('/oppgaver/Funksjonstabeller/nivaa2', methods=['GET', 'POST'])
@login_required
def funksjonstabeller_nivaa2_route():
    return kjor_funkstabell(
        funksjonstabeller_nivaa2_oppgaver, 50000,
        "funksjonstabeller_nivaa2.html",
        "/oppgaver/Funksjonstabeller/nivaa2"
    )


# NIVÅ 3 – analysere og bruke funksjonstabeller (ID 51001–51030)
funksjonstabeller_nivaa3_oppgaver = [
    ("tekst",
     "🚗 Bil A: y = 80x. Bil B: y = 60x + 40.\nFinn tabellverdier for x=0,1,2,3 og finn når Bil A er raskere.",
     "2", None),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = x² + 2x",
     "alle",
     (["x","y = x² + 2x"],
      [["0","?"],["1","?"],["2","?"],["3","?"],["4","?"]],
      ["0","3","8","15","24"],
      ["x=0","x=1","x=2","x=3","x=4"])),

    ("flervalg",
     "Tabellen:\nx=1→y=5, x=2→y=9, x=3→y=13, x=4→y=17\nHva er y når x=10?",
     "41", ["39","43","37"]),

    ("finn_feilen",
     "🔍 Tabellen for y = x² − 1:\nx=1→0, x=2→3, x=3→8, x=4→14\nFinne feilen!",
     "4",
     ["x=1: 1−1=0  ✓",
      "x=2: 4−1=3  ✓",
      "x=3: 9−1=8  ✓",
      "x=4: 16−1=14  ← FEIL (16−1=15, ikke 14)"]),

    ("steg",
     "📝 To funksjoner: f(x) = 2x + 3 og g(x) = x² − 1.\nFinn x der de er like.",
     "alle",
     [("Sett lik: 2x + 3 = x² − 1 → x² − 2x − 4 = 0\nPrøv x = 4: f(4) = ?","11"),
      ("g(4) = 4² − 1 = ?","15"),
      ("Prøv x = 3: f(3) = ?","9"),
      ("g(3) = 3² − 1 = ?","8"),
      ("Er de like ved x=3? Skriv ja eller nei","nei")]),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 3x² − x",
     "alle",
     (["x","y = 3x² − x"],
      [["1","?"],["2","?"],["3","?"],["4","?"]],
      ["2","10","24","44"],
      ["x=1","x=2","x=3","x=4"])),

    ("flervalg",
     "Tabellen:\nx=1→2, x=2→8, x=3→18, x=4→32\nHvilken formel passer?",
     "y = 2x²", ["y = x² + 1","y = 3x − 1","y = 2x³"]),

    ("tekst",
     "💰 Fortjeneste: f(x) = 50x − 200 der x=antall solgte varer.\nVed hvilken x begynner man å tjene penger?",
     "5", None),

    ("finn_feilen",
     "🔍 Noen sammenlignet f(x)=3x+1 og g(x)=x²+1.\nSa de er like ved x=0 og x=2. Finn feilen!",
     "2",
     ["x=0: f(0)=1 og g(0)=1 — like  ✓",
      "x=2: f(2)=7 og g(2)=5 — like  ← FEIL (7≠5, de er IKKE like ved x=2)",
      "Riktig: like ved x=0 og x=3"]),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = −x² + 6x",
     "alle",
     (["x","y = −x² + 6x"],
      [["0","?"],["1","?"],["2","?"],["3","?"],["6","?"]],
      ["0","5","8","9","0"],
      ["x=0","x=1","x=2","x=3","x=6"])),

    ("skriv",
     "Tabellen:\nx=1→3, x=4→9, x=9→15\nHvilken formel passer? Hint: prøv y = a·√x + b",
     "y = 2√x + 1", None),

    ("flervalg",
     "f(x) = 2x og g(x) = x + 6.\nVed hvilken x er f(x) = g(x)?",
     "6", ["3","4","8"]),

    ("tekst",
     "🏃 Lena løper: f(t) = 6t km. Ole sykler: g(t) = 15t − 9 km.\nNår har Ole kjørt lengre? (Finn t der g > f)",
     "1", None),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = (x+1)²",
     "alle",
     (["x","y = (x+1)²"],
      [["0","?"],["1","?"],["2","?"],["3","?"],["4","?"]],
      ["1","4","9","16","25"],
      ["x=0","x=1","x=2","x=3","x=4"])),

    ("matching",
     "Match tabellen med riktig formel",
     "riktig",
     [("x=1→4, x=2→16, x=3→36","y = (2x)²"),
      ("x=0→1, x=1→4, x=2→9","y = (x+1)²"),
      ("x=1→0, x=2→3, x=3→8","y = x²−1"),
      ("x=0→0, x=1→2, x=2→8","y = 2x²")]),

    ("skriv",
     "f(x) = 4x − 2. Tabellen:\nx=?→10, x=?→18\nHva er x når y=10?",
     "3", None),

    ("tekst",
     "📊 Gjennomsnittlig vekst: x=2020→100, x=2021→110, x=2022→121\nHva er prosentvis vekst per år?",
     "10", None),

    ("finn_feilen",
     "🔍 Tabellen for y = 2x² + 1:\nx=1→3, x=2→9, x=3→19, x=4→31\nFinne feilen!",
     "2",
     ["x=1: 2·1+1=3  ✓",
      "x=2: 2·4+1=9  ← FEIL (2·4=8, 8+1=9 — faktisk ✓, feilen er x=3)",
      "x=3: 2·9+1=18  ← VIRKELIG FEIL (tabellen sier 19 men 2·9+1=19) — altså er x=4 feil",
      "x=4: 2·16+1=31  ← FEIL (2·16=32, 32+1=33, ikke 31)"]),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = x³",
     "alle",
     (["x","y = x³"],
      [["1","?"],["2","?"],["3","?"],["4","?"]],
      ["1","8","27","64"],
      ["x=1","x=2","x=3","x=4"])),

    ("flervalg",
     "Tabellen: x=0→0, x=1→1, x=2→8, x=3→27\nHvilken formel passer?",
     "y = x³", ["y = 3x","y = x² + x","y = 2x³"]),

    ("steg",
     "📝 f(x) = 2x + 1 og g(x) = 3x − 4.\nBruk tabell (x=0..5) og finn der g(x) > f(x).",
     "alle",
     [("f(5) = 2·5+1","11"),
      ("g(5) = 3·5−4","11"),
      ("Er f(5) = g(5)? Skriv ja eller nei","ja"),
      ("For x=6: g(6)−f(6) = ?","1"),
      ("Første x der g(x) > f(x)","6")]),

    ("tekst",
     "💰 Bedrift A: f(x) = 3x² (kostnad). Bedrift B: g(x) = 10x + 50.\nHvilken er billigst når x = 5?",
     "Bedrift B", None),

    ("skriv",
     "f(x) = x² og g(x) = 4x.\nTabell for x=0..4. Ved hvilken x er f(x) > g(x) for første gang?",
     "5", None),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 2x² − 3x + 1",
     "alle",
     (["x","y = 2x²−3x+1"],
      [["0","?"],["1","?"],["2","?"],["3","?"]],
      ["1","0","3","10"],
      ["x=0","x=1","x=2","x=3"])),

    ("flervalg",
     "Tabellen: x=1→6, x=2→11, x=3→18, x=4→27\nHvilken formel passer best?",
     "y = x² + 2x + 3", ["y = 5x + 1","y = 3x + 3","y = x² + 5"]),

    ("tekst",
     "🌍 Befolkning: x=0→1000, x=1→1100, x=2→1210\nHva er formelen? (Skriv som y = 1000 · 1,1^x eller lignende)",
     "y = 1000 · 1,1^x", None),

    ("finn_feilen",
     "🔍 Noen lagde tabell for y = −x² + 4x:\nx=0→0, x=1→3, x=2→4, x=3→3, x=4→0\nFinne feilen!",
     "2",
     ["x=0: 0+0=0  ✓",
      "x=1: −1+4=3  ← FEIL (−1²+4·1 = −1+4=3 — faktisk ✓ — feilen er x=2)",
      "x=2: −4+8=4  ✓",
      "x=3: −9+12=3  ✓"]),

    ("skriv",
     "Tabellen: x=0→2, x=1→5, x=2→10, x=3→17\nHva er formelen?",
     "y = x² + 2x + 2", None),

    ("tabell",
     "📋 Sammenlign f(x) = 3x + 2 og g(x) = x² for x = 0, 1, 2, 3, 4",
     "alle",
     (["x","f(x) = 3x+2","g(x) = x²"],
      [["0","?","?"],["1","?","?"],["2","?","?"],["3","?","?"],["4","?","?"]],
      ["2","0","5","1","8","4","11","9","14","16"],
      ["f(0)","g(0)","f(1)","g(1)","f(2)","g(2)","f(3)","g(3)","f(4)","g(4)"])),

    ("flervalg",
     "Fra tabellen over: ved hvilken x-verdi er g(x) > f(x) for første gang?",
     "4", ["3","5","2"]),

    ("steg",
     "📝 Finn formelen y = ax² + b fra:\nx=0→3, x=1→5, x=2→11",
     "alle",
     [("b = y når x=0","3"),
      ("a = (y(1)−b) / 1² = (5−3)/1","2"),
      ("Sjekk: 2·2²+3 = ?","11"),
      ("Formelen er y = ?","y = 2x² + 3")]),

    # --- NYE OPPGAVER NIVÅ 3 (avansert tabellanalyse) ---
    ("tabell",
     "📋 Fyll inn tabellen for f(x) = x³",
     "alle",
     (["x", "y = x³"],
      [["1","?"],["2","?"],["3","?"],["4","?"]],
      ["1","8","27","64"],
      ["y når x=1","y når x=2","y når x=3","y når x=4"])),

    ("tabell",
     "📋 To planer sammenliknet.\nPlan A: y = 5x. Plan B: y = 3x + 8.\nFyll inn for Plan A:",
     "alle",
     (["x", "Plan A: y=5x"],
      [["0","?"],["2","?"],["4","?"],["6","?"]],
      ["0","10","20","30"],
      ["y når x=0","y når x=2","y når x=4","y når x=6"])),

    ("steg",
     "📝 Analyse: Tabellen viser x=0→2, x=1→5, x=2→10, x=3→17.\nEr det lineær, kvadratisk eller noe annet?",
     "alle",
     [("Steg 1: Finn differansene: 5−2, 10−5, 17−10","3, 5, 7"),
      ("Steg 2: Er differansene like? (ja/nei)","nei"),
      ("Steg 3: Finn 2. differanse: 5−3, 7−5","2, 2"),
      ("Steg 4: Hva slags sammenheng er det?","kvadratisk")]),

    ("tabell",
     "🏦 Spareplan: y = 1000 + 200x (x = måneder, y = kr på konto).\n📋 Fyll inn tabellen",
     "alle",
     (["x (mnd)", "y (kr)"],
      [["0","?"],["6","?"],["12","?"],["24","?"]],
      ["1000","2200","3400","5800"],
      ["y når x=0","y når x=6","y når x=12","y når x=24"])),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = 2x² + 3x",
     "alle",
     (["x", "y = 2x² + 3x"],
      [["0","?"],["1","?"],["2","?"],["3","?"]],
      ["0","5","14","27"],
      ["y når x=0","y når x=1","y når x=2","y når x=3"])),

    ("flervalg",
     "Tabellen: x=0→100, x=1→50, x=2→25, x=3→12.5\nHva slags funksjon er dette?",
     "Eksponentiell nedgang (halvering)", ["Lineær","Proporsjonal","Kvadratisk"]),

    ("tabell",
     "🌡️ Kjøling: y = 80 − 10x (x = minutter, y = temperatur i °C).\n📋 Fyll inn tabellen",
     "alle",
     (["x (min)", "y (°C)"],
      [["0","?"],["2","?"],["5","?"],["8","?"]],
      ["80","60","30","0"],
      ["y når x=0","y når x=2","y når x=5","y når x=8"])),

    ("steg",
     "📝 To bedrifter: A: y = 8x + 50, B: y = 12x.\nFinn når de tjener like mye.",
     "alle",
     [("Steg 1: Sett 8x + 50 = 12x og trekk fra 8x","4x = 50"),
      ("Steg 2: Del på 4","x = 12.5"),
      ("Steg 3: Hva er y for begge når x = 12.5?","150"),
      ("Steg 4: Hvilken er best når x > 12.5?","B")]),

    ("skriv",
     "Tabellen: x=1→5, x=4→17, x=7→29.\nHva er stigningstallet (a)?",
     "4", None),

    ("tabell",
     "📋 Fyll inn tabellen for f(x) = (x+1)²",
     "alle",
     (["x", "y = (x+1)²"],
      [["0","?"],["1","?"],["2","?"],["3","?"]],
      ["1","4","9","16"],
      ["y når x=0","y når x=1","y når x=2","y når x=3"])),

]


@app.route('/oppgaver/Funksjonstabeller/nivaa3', methods=['GET', 'POST'])
@login_required
def funksjonstabeller_nivaa3_route():
    return kjor_funkstabell(
        funksjonstabeller_nivaa3_oppgaver, 51000,
        "funksjonstabeller_nivaa3.html",
        "/oppgaver/Funksjonstabeller/nivaa3"
    )




# ============================================================
# PVP – KONKURRANSEMODUS
# ============================================================
import random as _random

def _simple(lst):
    """Hent bare enkle 2-tupler (spørsmål, svar) fra en oppgaveliste."""
    return [{"q": item[0], "a": item[1]}
            for item in lst
            if isinstance(item, tuple) and len(item) == 2
            and isinstance(item[0], str) and isinstance(item[1], str)]

# Lett: bare nivå 1-oppgaver (enkel matte)
PVP_POOL_EASY = []
for _lst in [
    hele_tall_nivaa1_oppgaver, desimaltall_nivaa1_oppgaver, prosent_nivaa1_oppgaver,
    negative_tall_nivaa1_oppgaver, overslag_nivaa1_oppgaver, brok_nivaa1_oppgaver,
    variabler_nivaa1_oppgaver, enkle_uttrykk_nivaa1_oppgaver,
    regning_uttrykk_nivaa1_oppgaver, likninger_nivaa1_oppgaver,
]:
    PVP_POOL_EASY.extend(_simple(_lst))

# Middels: nivå 2-oppgaver
PVP_POOL_MEDIUM = []
for _lst in [
    hele_tall_nivaa2_oppgaver, desimaltall_nivaa2_oppgaver, prosent_nivaa2_oppgaver,
    negative_tall_nivaa2_oppgaver, overslag_nivaa2_oppgaver, brok_nivaa2_oppgaver,
    potenser_nivaa2_oppgaver, variabler_nivaa2_oppgaver, enkle_uttrykk_nivaa2_oppgaver,
    regning_uttrykk_nivaa2_oppgaver, likninger_nivaa2_oppgaver,
    forhold_nivaa2_oppgaver, sette_inn_nivaa2_oppgaver,
]:
    PVP_POOL_MEDIUM.extend(_simple(_lst))

# Vanskelig: nivå 3-oppgaver (avansert)
PVP_POOL_HARD = []
for _lst in [
    hele_tall_nivaa3_oppgaver, desimaltall_nivaa3_oppgaver, prosent_nivaa3_oppgaver,
    negative_tall_nivaa3_oppgaver, brok_nivaa3_oppgaver, potenser_nivaa3_oppgaver,
    variabler_nivaa3_oppgaver, enkle_uttrykk_nivaa3_oppgaver,
    regning_uttrykk_nivaa3_oppgaver, likninger_nivaa3_oppgaver,
    forhold_nivaa3_oppgaver, sette_inn_nivaa3_oppgaver,
    tall_symboler_nivaa3_oppgaver, sammenheng_nivaa3_oppgaver,
]:
    PVP_POOL_HARD.extend(_simple(_lst))


@app.route('/pvp')
@login_required
def pvp_menu():
    return render_template('pvp_menu.html')


@app.route('/pvp/mot-ai')
@login_required
def pvp_ai():
    return render_template('pvp_ai.html')


@app.route('/pvp/ai-oppgave')
@login_required
def pvp_ai_oppgave():
    diff = request.args.get('diff', 'medium')
    pool = {'easy': PVP_POOL_EASY, 'medium': PVP_POOL_MEDIUM, 'hard': PVP_POOL_HARD}.get(diff, PVP_POOL_MEDIUM)
    if not pool:
        return {"error": "Ingen oppgaver"}, 500
    oppgave = _random.choice(pool)
    return {"q": oppgave["q"], "a": oppgave["a"]}




# ============================================================
# LÆRER-SYSTEM
# ============================================================

TOPIC_MAP = {
    1:     ("Regnerekkefølge", "Nivå 1"),
    2000:  ("Regnerekkefølge", "Nivå 2"),
    3000:  ("Regnerekkefølge", "Nivå 3"),
    4000:  ("Hele tall", "Nivå 1"),
    5000:  ("Hele tall", "Nivå 2"),
    6000:  ("Hele tall", "Nivå 3"),
    7000:  ("Desimaltall", "Nivå 1"),
    8000:  ("Desimaltall", "Nivå 2"),
    9000:  ("Desimaltall", "Nivå 3"),
    10000: ("Prosent", "Nivå 1"),
    11000: ("Prosent", "Nivå 2"),
    12000: ("Prosent", "Nivå 3"),
    13000: ("Negative tall", "Nivå 1"),
    14000: ("Negative tall", "Nivå 2"),
    15000: ("Negative tall", "Nivå 3"),
    16000: ("Brøker", "Nivå 1"),
    17000: ("Brøker", "Nivå 2"),
    18000: ("Brøker", "Nivå 3"),
    19000: ("Potenser (enkle)", "Nivå 1"),
    20000: ("Potenser (enkle)", "Nivå 2"),
    21000: ("Potenser (enkle)", "Nivå 3"),
    22000: ("Overslag og hoderegning", "Nivå 1"),
    23000: ("Overslag og hoderegning", "Nivå 2"),
    24000: ("Overslag og hoderegning", "Nivå 3"),
    25000: ("Forhold og brøk–desimal–prosent", "Nivå 1"),
    26000: ("Forhold og brøk–desimal–prosent", "Nivå 2"),
    27000: ("Forhold og brøk–desimal–prosent", "Nivå 3"),
    28000: ("Variabler", "Nivå 1"),
    29000: ("Variabler", "Nivå 2"),
    30000: ("Variabler", "Nivå 3"),
    31000: ("Enkle algebraiske uttrykk", "Nivå 1"),
    32000: ("Enkle algebraiske uttrykk", "Nivå 2"),
    33000: ("Enkle algebraiske uttrykk", "Nivå 3"),
    34000: ("Regning med uttrykk", "Nivå 1"),
    35000: ("Regning med uttrykk", "Nivå 2"),
    36000: ("Regning med uttrykk", "Nivå 3"),
    37000: ("Likninger", "Nivå 1"),
    38000: ("Likninger", "Nivå 2"),
    39000: ("Likninger", "Nivå 3"),
    40000: ("Sette inn verdier", "Nivå 1"),
    41000: ("Sette inn verdier", "Nivå 2"),
    42000: ("Sette inn verdier", "Nivå 3"),
    43000: ("Tall og symboler", "Nivå 1"),
    44000: ("Tall og symboler", "Nivå 2"),
    45000: ("Tall og symboler", "Nivå 3"),
    46000: ("Sammenheng mellom to størrelser", "Nivå 1"),
    47000: ("Sammenheng mellom to størrelser", "Nivå 2"),
    48000: ("Sammenheng mellom to størrelser", "Nivå 3"),
    49000: ("Funksjonstabeller", "Nivå 1"),
    50000: ("Funksjonstabeller", "Nivå 2"),
    51000: ("Funksjonstabeller", "Nivå 3"),
}

def oppgave_id_to_topic(oid):
    """Return (tema, nivå) for a given oppgave_id."""
    # Check exact base (old style: base+1..30 or base+1..50)
    for base, (tema, nivaa) in sorted(TOPIC_MAP.items(), reverse=True):
        if base == 1 and oid <= 30:
            return tema, nivaa
        elif base > 1 and base < oid <= base + 200:
            return tema, nivaa
    return "Ukjent", ""

def teacher_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if session.get("role") not in ("teacher", "admin"):
            return redirect("/dashboard")
        return f(*args, **kwargs)
    return wrapper


@app.route("/laerer")
@login_required
@teacher_required
def laerer_dashboard():
    conn = get_db()
    klasser = conn.execute(
        "SELECT k.*, COUNT(ke.elev_id) as antall_elever FROM klasser k "
        "LEFT JOIN klasse_elever ke ON ke.klasse_id = k.id "
        "WHERE k.laerer_id = ? GROUP BY k.id ORDER BY k.id DESC",
        (session["user_id"],)
    ).fetchall()
    return render_template("laerer_dashboard.html", klasser=klasser)


@app.route("/laerer/klasse/ny", methods=["POST"])
@login_required
@teacher_required
def laerer_ny_klasse():
    navn = request.form.get("navn", "").strip()
    if navn:
        conn = get_db()
        conn.execute("INSERT INTO klasser (navn, laerer_id) VALUES (?, ?)",
                     (navn, session["user_id"]))
        conn.commit()
    return redirect("/laerer")


@app.route("/laerer/klasse/<int:klasse_id>")
@login_required
@teacher_required
def laerer_klasse(klasse_id):
    conn = get_db()

    # Verify ownership
    klasse = conn.execute(
        "SELECT * FROM klasser WHERE id = ? AND laerer_id = ?",
        (klasse_id, session["user_id"])
    ).fetchone()
    if not klasse:
        return redirect("/laerer")

    # Students in class
    elever = conn.execute(
        "SELECT u.id, u.username, u.created_at, "
        "COUNT(p.id) as totalt_loste, "
        "MAX(p.id) as siste_aktivitet_id "
        "FROM klasse_elever ke "
        "JOIN users u ON u.id = ke.elev_id "
        "LEFT JOIN progress p ON p.user_id = u.id "
        "WHERE ke.klasse_id = ? "
        "GROUP BY u.id ORDER BY u.username",
        (klasse_id,)
    ).fetchall()

    # Progress per student per topic
    elev_topics = {}
    for elev in elever:
        rows = conn.execute(
            "SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'",
            (elev["id"],)
        ).fetchall()
        topic_count = {}
        for r in rows:
            oid = r["oppgave_id"]
            tema, nivaa = oppgave_id_to_topic(oid)
            key = f"{tema} – {nivaa}"
            topic_count[key] = topic_count.get(key, 0) + 1
        elev_topics[elev["id"]] = topic_count

    # All users not in this class (for adding)
    alle_brukere = conn.execute(
        "SELECT u.id, u.username FROM users u "
        "WHERE u.role = 'user' AND u.id NOT IN "
        "(SELECT elev_id FROM klasse_elever WHERE klasse_id = ?) "
        "ORDER BY u.username",
        (klasse_id,)
    ).fetchall()

    # Weak topics across class (where avg completion is lowest)
    all_topic_counts = {}
    for elev_id, topics in elev_topics.items():
        for t, cnt in topics.items():
            if t not in all_topic_counts:
                all_topic_counts[t] = []
            all_topic_counts[t].append(cnt)

    # Topics sorted by average completion ascending (weakest first)
    topic_avg = []
    for t, counts in all_topic_counts.items():
        avg = sum(counts) / len(elever) if elever else 0
        topic_avg.append((t, round(avg, 1)))
    topic_avg.sort(key=lambda x: x[1])
    svake_temaer = topic_avg[:5]  # top 5 weakest

    # Tildelinger (oppgaver gitt til klassen) + fremgang per elev
    tildelinger_rows = conn.execute(
        "SELECT * FROM tildelinger WHERE klasse_id = ? ORDER BY id DESC",
        (klasse_id,)
    ).fetchall()

    tildelinger = []
    for t in tildelinger_rows:
        id_base = t["id_base"]
        ferdige = 0
        for elev in elever:
            rows = conn.execute(
                "SELECT COUNT(*) as cnt FROM progress WHERE user_id = ? AND status = 'riktig' "
                "AND oppgave_id > ? AND oppgave_id <= ?",
                (elev["id"], id_base, id_base + 200)
            ).fetchone()
            if rows["cnt"] >= 5:  # anses som "i gang/ferdig" ved minst 5 riktige
                ferdige += 1
        tildelinger.append({
            "id": t["id"],
            "tema": t["tema"],
            "nivaa": t["nivaa"],
            "frist": t["frist"],
            "melding": t["melding"],
            "opprettet": t["opprettet"],
            "ferdige": ferdige,
            "totalt": len(elever),
        })

    # Liste over alle temaer/nivåer for tildelings-dropdown
    alle_temaer = sorted(
        [(base, tema, nivaa) for base, (tema, nivaa) in TOPIC_MAP.items() if base > 1],
        key=lambda x: (x[1], x[2])
    )

    # Fremgang over tid – løste oppgaver per uke, siste 8 uker, for hele klassen
    elev_ider = [e["id"] for e in elever]
    uke_data = []
    if elev_ider:
        placeholders = ",".join("?" * len(elev_ider))
        rows = conn.execute(
            f"SELECT strftime('%Y-W%W', timestamp) as uke, COUNT(*) as antall "
            f"FROM progress WHERE user_id IN ({placeholders}) AND status = 'riktig' "
            f"AND timestamp >= datetime('now', '-56 days') "
            f"GROUP BY uke ORDER BY uke ASC",
            elev_ider
        ).fetchall()
        uke_data = [{"uke": r["uke"], "antall": r["antall"]} for r in rows]

    return render_template("laerer_klasse.html",
        klasse=klasse,
        elever=elever,
        elev_topics=elev_topics,
        alle_brukere=alle_brukere,
        svake_temaer=svake_temaer,
        tildelinger=tildelinger,
        alle_temaer=alle_temaer,
        uke_data=uke_data
    )


@app.route("/laerer/klasse/<int:klasse_id>/legg-til", methods=["POST"])
@login_required
@teacher_required
def laerer_legg_til_elev(klasse_id):
    conn = get_db()
    klasse = conn.execute("SELECT * FROM klasser WHERE id = ? AND laerer_id = ?",
                          (klasse_id, session["user_id"])).fetchone()
    if not klasse:
        return redirect("/laerer")
    elev_id = request.form.get("elev_id")
    if elev_id:
        try:
            conn.execute("INSERT INTO klasse_elever (klasse_id, elev_id) VALUES (?, ?)",
                         (klasse_id, int(elev_id)))
            conn.commit()
        except Exception:
            pass
    return redirect(f"/laerer/klasse/{klasse_id}")


@app.route("/laerer/klasse/<int:klasse_id>/fjern/<int:elev_id>", methods=["POST"])
@login_required
@teacher_required
def laerer_fjern_elev(klasse_id, elev_id):
    conn = get_db()
    klasse = conn.execute("SELECT * FROM klasser WHERE id = ? AND laerer_id = ?",
                          (klasse_id, session["user_id"])).fetchone()
    if not klasse:
        return redirect("/laerer")
    conn.execute("DELETE FROM klasse_elever WHERE klasse_id = ? AND elev_id = ?",
                 (klasse_id, elev_id))
    conn.commit()
    return redirect(f"/laerer/klasse/{klasse_id}")


@app.route("/laerer/klasse/<int:klasse_id>/slett", methods=["POST"])
@login_required
@teacher_required
def laerer_slett_klasse(klasse_id):
    conn = get_db()
    klasse = conn.execute("SELECT * FROM klasser WHERE id = ? AND laerer_id = ?",
                          (klasse_id, session["user_id"])).fetchone()
    if not klasse:
        return redirect("/laerer")
    conn.execute("DELETE FROM klasse_elever WHERE klasse_id = ?", (klasse_id,))
    conn.execute("DELETE FROM tildelinger WHERE klasse_id = ?", (klasse_id,))
    conn.execute("DELETE FROM klasser WHERE id = ?", (klasse_id,))
    conn.commit()
    return redirect("/laerer")


@app.route("/laerer/klasse/<int:klasse_id>/tildel", methods=["POST"])
@login_required
@teacher_required
def laerer_tildel(klasse_id):
    conn = get_db()
    klasse = conn.execute("SELECT * FROM klasser WHERE id = ? AND laerer_id = ?",
                          (klasse_id, session["user_id"])).fetchone()
    if not klasse:
        return redirect("/laerer")

    tema_nivaa = request.form.get("tema_nivaa", "")  # format: "id_base|Tema|Nivå X"
    melding = request.form.get("melding", "").strip()

    # Bygg frist-dato fra dag/måned/år-felter (norsk format)
    dag = request.form.get("frist_dag", "").strip()
    maaned = request.form.get("frist_maaned", "").strip()
    aar = request.form.get("frist_aar", "").strip()
    frist = f"{aar}-{maaned}-{dag}" if dag and maaned and aar else None

    if "|" in tema_nivaa:
        id_base_str, tema, nivaa = tema_nivaa.split("|", 2)
        conn.execute(
            "INSERT INTO tildelinger (klasse_id, laerer_id, tema, nivaa, id_base, frist, melding) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (klasse_id, session["user_id"], tema, nivaa, int(id_base_str), frist, melding or None)
        )
        conn.commit()
    return redirect(f"/laerer/klasse/{klasse_id}")


@app.route("/laerer/klasse/<int:klasse_id>/tildel/<int:tildeling_id>/slett", methods=["POST"])
@login_required
@teacher_required
def laerer_slett_tildeling(klasse_id, tildeling_id):
    conn = get_db()
    klasse = conn.execute("SELECT * FROM klasser WHERE id = ? AND laerer_id = ?",
                          (klasse_id, session["user_id"])).fetchone()
    if not klasse:
        return redirect("/laerer")
    conn.execute("DELETE FROM tildelinger WHERE id = ? AND klasse_id = ?", (tildeling_id, klasse_id))
    conn.commit()
    return redirect(f"/laerer/klasse/{klasse_id}")


# START SERVER
if __name__ == '__main__':
    app.run(debug=True)
