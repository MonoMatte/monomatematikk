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

    return render_template("dashboard.jinja2",
        username=session["username"],
        role=session.get("role", "user"),
        total=total,
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
    if ny_rolle in ["user", "admin"]:
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
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], nummer, "riktig"))
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
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip().replace(".", ",")
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip().replace(".", ",")
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip().replace(".", ",")
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip().replace("%", "")
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip().replace(" ", "").replace("kr", "").replace(",", ".")
        fasit_norm = fasit.replace(" ", "").replace(",", ".")
        if svar == fasit_norm:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
    conn = get_db()
    rows = conn.execute("SELECT oppgave_id FROM progress WHERE user_id = ? AND status = 'riktig'", (session["user_id"],)).fetchall()
    riktige_oppgaver = {row["oppgave_id"] for row in rows}

    if request.method == "POST":
        svar = request.form["svar"].strip()
        if svar == fasit:
            resultat = "✅ Riktig!"
            riktig = True
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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
            conn.execute("INSERT OR REPLACE INTO progress (user_id, oppgave_id, status) VALUES (?, ?, ?)", (session["user_id"], oppgave_id, "riktig"))
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


# START SERVER
if __name__ == '__main__':
    app.run(debug=True)
