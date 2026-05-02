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


# START SERVER
if __name__ == '__main__':
    app.run(debug=True)
