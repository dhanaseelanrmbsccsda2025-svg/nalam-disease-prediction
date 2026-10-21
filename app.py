"""
Disease Prediction
------------------
A symptom-based disease prediction web app written only in Python.

Stack : Streamlit (web UI) + SQLite (users and history, built into Python)
Run   : pip install -r requirements.txt
        streamlit run app.py

Important: this is an educational, rule-based tool. The "match" score shows how
closely symptoms fit a condition. It is not a probability and not a diagnosis.
"""
import hashlib
import json
import secrets
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

import streamlit as st

DB_PATH = Path(__file__).with_name("disease_prediction.db")

# ---------------------------------------------------------------------------
# Medical data
# ---------------------------------------------------------------------------
SYMPTOM_GROUPS = {
    "General": {
        "fever": "Fever", "chills": "Chills or shivering", "fatigue": "Tiredness",
        "body_pain": "Body ache", "sweating": "Heavy sweating",
        "loss_appetite": "Loss of appetite", "weight_loss": "Unexplained weight loss",
        "dizziness": "Dizziness",
    },
    "Head, eyes and throat": {
        "headache": "Headache", "light_sens": "Sensitivity to light",
        "retro_eye": "Pain behind the eyes", "itchy_eyes": "Itchy, watery eyes",
        "blur_vision": "Blurred vision", "sore_throat": "Sore throat",
        "runny_nose": "Runny or blocked nose", "sneezing": "Sneezing",
        "smell_loss": "Loss of smell or taste",
    },
    "Chest and breathing": {
        "cough": "Cough", "short_breath": "Shortness of breath", "wheezing": "Wheezing",
        "chest_pain": "Chest pain or tightness", "fast_heart": "Fast heartbeat",
    },
    "Stomach": {
        "nausea": "Nausea", "vomiting": "Vomiting", "diarrhea": "Loose stools",
        "abd_pain": "Stomach pain",
    },
    "Urine and thirst": {
        "thirst": "Excess thirst", "freq_urine": "Frequent urination",
        "burn_urine": "Burning while passing urine", "dark_urine": "Dark yellow or brown urine",
    },
    "Skin and joints": {
        "rash": "Skin rash", "joint_pain": "Joint pain", "swollen_joints": "Swollen joints",
        "yellow": "Yellow skin or eyes", "pale": "Pale skin",
        "bleeding_gums": "Bleeding gums or nose",
    },
}
LABEL = {k: v for group in SYMPTOM_GROUPS.values() for k, v in group.items()}

# dur = (min_days, max_days) in which the illness normally shows up
DISEASES = [
    {"id": "cold", "name": "Common Cold", "icon": "virus", "dur": (1, 10),
     "sym": {"runny_nose": 3, "sneezing": 3, "sore_throat": 2, "cough": 2, "headache": 1, "fatigue": 1, "fever": 1},
     "desc": "A mild viral infection of the nose and throat. It usually clears by itself in about a week.",
     "care": ["Rest and drink plenty of warm fluids", "Steam inhalation and warm salt-water gargles",
              "Paracetamol for fever or aches if needed", "See a doctor if symptoms last beyond 10 days"],
     "doctor": "General physician"},
    {"id": "flu", "name": "Influenza (Flu)", "icon": "virus", "dur": (1, 10),
     "sym": {"fever": 3, "chills": 2, "body_pain": 3, "fatigue": 2, "headache": 2, "cough": 2, "sore_throat": 1, "loss_appetite": 1},
     "desc": "Flu spreads easily and causes sudden fever, aches and tiredness. Most people recover in 5 to 7 days.",
     "care": ["Rest and drink plenty of fluids", "Paracetamol for fever and body ache",
              "Stay away from others while you have fever",
              "See a doctor early if you are elderly, pregnant or have a long-term illness"],
     "doctor": "General physician"},
    {"id": "covid", "name": "COVID-19", "icon": "virus", "dur": (2, 14),
     "sym": {"fever": 2, "cough": 2, "fatigue": 2, "smell_loss": 3, "sore_throat": 1, "body_pain": 1, "headache": 1, "short_breath": 2},
     "desc": "A viral respiratory infection. Loss of smell or taste is a distinctive sign.",
     "care": ["Take a rapid antigen or RT-PCR test", "Isolate and wear a mask around others",
              "If you have a pulse oximeter, seek care when oxygen falls below 94%", "Rest and drink fluids"],
     "doctor": "General physician or pulmonologist"},
    {"id": "dengue", "name": "Dengue Fever", "icon": "drop", "dur": (2, 10),
     "sym": {"fever": 3, "retro_eye": 3, "joint_pain": 2, "body_pain": 2, "headache": 2, "rash": 2, "nausea": 1, "vomiting": 1, "bleeding_gums": 2, "fatigue": 1},
     "desc": "A mosquito-borne viral fever. Look for fever with pain behind the eyes, severe body ache and rash.",
     "care": ["Get a blood test (NS1 antigen and platelet count) without delay",
              "Drink plenty of fluids, ORS and coconut water",
              "Use paracetamol only. Avoid aspirin and ibuprofen",
              "Watch for bleeding, severe stomach pain or repeated vomiting"],
     "doctor": "General physician or internal medicine"},
    {"id": "malaria", "name": "Malaria", "icon": "drop", "dur": (2, 30),
     "sym": {"fever": 3, "chills": 3, "sweating": 3, "headache": 1, "nausea": 1, "vomiting": 1, "body_pain": 1, "fatigue": 1},
     "desc": "Spread by Anopheles mosquitoes. Fever often comes in cycles of chills, high fever and heavy sweating.",
     "care": ["Get a blood smear or rapid malaria test", "Take medicines only as prescribed",
              "Use mosquito nets and repellents", "Seek care the same day if you feel confused or very weak"],
     "doctor": "General physician or internal medicine"},
    {"id": "typhoid", "name": "Typhoid Fever", "icon": "virus", "dur": (4, 28),
     "sym": {"fever": 3, "abd_pain": 2, "loss_appetite": 2, "fatigue": 2, "headache": 1, "diarrhea": 1, "rash": 1, "nausea": 1},
     "desc": "A bacterial infection from contaminated food or water. Fever rises step by step over several days.",
     "care": ["Get blood tests as your doctor advises", "Eat soft home-cooked food and drink boiled water",
              "Finish antibiotics exactly as prescribed", "Wash hands before meals"],
     "doctor": "General physician"},
    {"id": "gastro", "name": "Gastroenteritis (Stomach infection)", "icon": "stomach", "dur": (1, 5),
     "sym": {"diarrhea": 3, "vomiting": 3, "nausea": 2, "abd_pain": 2, "fever": 1, "fatigue": 1, "loss_appetite": 1},
     "desc": "A stomach infection that causes vomiting and loose stools, often from food or water. Dehydration is the main risk.",
     "care": ["Sip ORS often in small amounts", "Eat light food such as rice, banana and curd",
              "Avoid oily and spicy food",
              "See a doctor if there is blood in stools or you pass no urine for 8 hours"],
     "doctor": "General physician or gastroenterologist"},
    {"id": "migraine", "name": "Migraine", "icon": "head", "dur": (0, 3),
     "sym": {"headache": 3, "light_sens": 3, "nausea": 2, "vomiting": 1, "dizziness": 1, "blur_vision": 1},
     "desc": "A throbbing headache, often on one side, with sensitivity to light and nausea.",
     "care": ["Rest in a dark, quiet room", "Keep regular meals, sleep and water intake",
              "Note your triggers, such as stress, skipped meals or bright light",
              "See a neurologist if attacks are frequent or suddenly severe"],
     "doctor": "Neurologist"},
    {"id": "pneumonia", "name": "Pneumonia (Lung infection)", "icon": "lungs", "dur": (3, 21),
     "sym": {"cough": 3, "fever": 2, "short_breath": 3, "chest_pain": 2, "chills": 1, "fatigue": 1, "fast_heart": 1},
     "desc": "An infection of the lungs that causes cough, fever and breathlessness. It needs a medical check.",
     "care": ["See a doctor for a chest examination and X-ray", "Do not self-treat with antibiotics",
              "Rest, drink fluids and take steam", "Go to hospital if breathing is fast or the lips look blue"],
     "doctor": "Pulmonologist or general physician"},
    {"id": "asthma", "name": "Asthma", "icon": "lungs", "dur": (0, 9999),
     "sym": {"wheezing": 3, "short_breath": 3, "cough": 2, "chest_pain": 1},
     "desc": "The airways narrow and cause wheezing, cough and breathlessness, often at night or with dust and cold air.",
     "care": ["Use your prescribed inhaler as directed", "Avoid triggers such as dust, smoke and cold air",
              "Ask for a lung function test (spirometry)", "Get urgent care if the inhaler does not help"],
     "doctor": "Pulmonologist"},
    {"id": "allergy", "name": "Allergic Rhinitis", "icon": "lungs", "dur": (0, 9999),
     "sym": {"sneezing": 3, "itchy_eyes": 3, "runny_nose": 3, "headache": 1, "cough": 1},
     "desc": "An allergy to dust, pollen or pets. It causes sneezing, a runny nose and itchy eyes, usually without fever.",
     "care": ["Avoid dust and strong smells, and wash bedding weekly", "Try a saline nasal rinse",
              "Ask a doctor or pharmacist about antihistamines", "See a doctor if symptoms last more than 2 weeks"],
     "doctor": "ENT specialist or allergist"},
    {"id": "diabetes", "name": "High Blood Sugar (diabetes warning signs)", "icon": "heart", "dur": (14, 9999),
     "sym": {"thirst": 3, "freq_urine": 3, "blur_vision": 2, "fatigue": 2, "weight_loss": 1},
     "desc": "Excess thirst and frequent urination can be early signs of high blood sugar. Only a blood test can confirm it.",
     "care": ["Get fasting and post-meal blood sugar and HbA1c tests",
              "Cut down sugary drinks and refined carbohydrates", "Walk for 30 minutes a day",
              "See a doctor soon for tests"],
     "doctor": "Diabetologist or general physician"},
    {"id": "uti", "name": "Urinary Tract Infection", "icon": "stomach", "dur": (1, 14),
     "sym": {"burn_urine": 3, "freq_urine": 3, "abd_pain": 1, "fever": 1, "dark_urine": 1},
     "desc": "A bacterial infection of the urinary tract that causes burning and frequent urination.",
     "care": ["Drink plenty of water and do not hold urine", "Get a urine test before taking any antibiotic",
              "See a doctor within a day or two", "Go sooner if you have fever or back pain"],
     "doctor": "General physician or urologist"},
    {"id": "anemia", "name": "Anaemia (low haemoglobin)", "icon": "heart", "dur": (7, 9999),
     "sym": {"fatigue": 3, "pale": 3, "dizziness": 2, "short_breath": 1, "fast_heart": 1, "headache": 1},
     "desc": "Low haemoglobin means the body gets less oxygen. It causes tiredness, pale skin and dizziness.",
     "care": ["Get a complete blood count (CBC)",
              "Eat iron-rich foods such as greens, ragi, dates, jaggery and pulses",
              "Add vitamin C foods to help iron absorption", "Ask your doctor before starting iron tablets"],
     "doctor": "General physician"},
    {"id": "bp", "name": "High Blood Pressure", "icon": "heart", "dur": (0, 9999),
     "sym": {"headache": 2, "dizziness": 2, "blur_vision": 1, "chest_pain": 1, "fast_heart": 1, "short_breath": 1},
     "desc": "Long-term high blood pressure often has no symptoms. Headache and dizziness can occur.",
     "care": ["Measure your BP at rest on two or three different days", "Cut down salt and processed food",
              "Exercise regularly and manage your weight", "See a doctor if readings stay above 140/90"],
     "doctor": "General physician or cardiologist"},
    {"id": "jaundice", "name": "Jaundice (liver problem)", "icon": "stomach", "dur": (3, 60),
     "sym": {"yellow": 3, "dark_urine": 3, "fatigue": 1, "nausea": 1, "abd_pain": 1, "loss_appetite": 1, "fever": 1},
     "desc": "Yellow skin or eyes with dark urine point to a liver or bile problem. It needs a blood test.",
     "care": ["Get liver function tests (bilirubin, SGOT, SGPT)",
              "Avoid alcohol and medicines that were not prescribed",
              "Drink boiled water and eat light food", "See a doctor soon"],
     "doctor": "Gastroenterologist or hepatologist"},
    {"id": "chik", "name": "Chikungunya", "icon": "drop", "dur": (2, 30),
     "sym": {"fever": 3, "joint_pain": 3, "swollen_joints": 2, "rash": 2, "headache": 1, "body_pain": 1, "fatigue": 1},
     "desc": "A mosquito-borne viral fever with severe joint pain and swelling. Joint pain can last for weeks.",
     "care": ["Rest and drink plenty of fluids", "Use paracetamol for pain. Avoid aspirin",
              "Confirm with a blood test and rule out dengue", "Start gentle movement once the fever settles"],
     "doctor": "General physician or rheumatologist"},
]
DIS = {d["id"]: d for d in DISEASES}
SERIOUS = {"dengue", "malaria", "typhoid", "pneumonia", "jaundice", "diabetes"}

DURATIONS = {"Under a day": 1, "1 to 3 days": 2, "4 to 7 days": 5, "8 to 14 days": 10, "More than 2 weeks": 21}
SEVERITIES = ["Mild", "Moderate", "Severe"]
CONTEXT = {
    "mosquito": "Mosquito bites or stagnant water nearby",
    "water": "Street food or untreated water recently",
    "contact": "Someone around me has a similar illness",
    "dust": "Dust, smoke, pollen or pets nearby",
}
CONDITIONS = {"diabetes": "Diabetes", "bp": "High blood pressure", "asthma": "Asthma", "heart": "Heart disease"}

URGENCY = {
    "emergency": {"tone": "crit", "title": "Get emergency care now",
                  "text": "Go to the nearest hospital or call 108 or 112. Do not wait for the symptoms to settle."},
    "soon": {"tone": "warn", "title": "See a doctor within 24 to 48 hours",
             "text": "Your symptoms deserve a medical check and probably a blood test. Go earlier if you feel worse."},
    "home": {"tone": "ok", "title": "Home care is reasonable for now",
             "text": "Rest, fluids and watching your symptoms are usually enough. See a doctor if you get worse or if nothing improves in 3 days."},
}
TIPS = [
    "Drink at least 2 to 3 litres of water through the day, more in hot weather.",
    "A 30-minute brisk walk most days lowers the risk of high blood pressure and diabetes.",
    "Sleep 7 to 8 hours. Poor sleep weakens your defence against infections.",
    "Empty water from coolers, pots and tyres every week to stop mosquitoes breeding.",
    "Wash hands with soap for 20 seconds before meals and after using the toilet.",
    "Fill half your plate with vegetables and add one fruit a day.",
    "Check your blood pressure once a month if you are over 30.",
]
AREAS = [
    ("virus", "Fever and infections", "Cold, flu, COVID-19, typhoid"),
    ("drop", "Mosquito-borne fevers", "Dengue, malaria, chikungunya"),
    ("lungs", "Lungs and breathing", "Pneumonia, asthma, allergy"),
    ("stomach", "Stomach, liver and urine", "Gastroenteritis, jaundice, UTI"),
    ("head", "Head and nerves", "Migraine"),
    ("heart", "Heart, sugar and blood", "High BP, blood sugar, anaemia"),
]

# ---------------------------------------------------------------------------
# Images (inline SVG drawn in Python, so no image files are needed)
# ---------------------------------------------------------------------------
TEAL, TEAL_SOFT, RED = "#1FA396", "#CFEAE6", "#D9463B"
HEART_PATH = ("M12 21.35l-1.45-1.32C5.4 15.36 2 12.28 2 8.5 2 5.42 4.42 3 7.5 3c1.74 0 3.41.81 4.5 2.09"
              "C13.09 3.81 14.76 3 16.5 3 19.58 3 22 5.42 22 8.5c0 3.78-3.4 6.86-8.55 11.54L12 21.35z")
ICON_PATHS = {
    "virus": '<circle cx="12" cy="12" r="4.5"/><path d="M12 2v3.5M12 18.5V22M2 12h3.5M18.5 12H22M5 5l2.5 2.5M16.5 16.5L19 19M19 5l-2.5 2.5M7.5 16.5L5 19"/>',
    "drop": '<path d="M12 2.5s6 6.2 6 10.5a6 6 0 0 1-12 0C6 8.7 12 2.5 12 2.5z"/><path d="M9.5 14a2.6 2.6 0 0 0 2.5 2.5"/>',
    "lungs": '<path d="M9 4v8.5c0 2.8-2 4.5-5 4.5 0-5 1-9 3-12.5M15 4v8.5c0 2.8 2 4.5 5 4.5 0-5-1-9-3-12.5M12 3v7"/>',
    "stomach": '<path d="M8 3v4c0 2 2 3.5 4.5 3.5S17 12 17 15.5a4.5 4.5 0 0 1-9 0"/>',
    "head": '<path d="M6 11a6 6 0 1 1 12 0c0 2.2-1 3.2-1 5.2V19H9v-2.8c0-1.6-3-2.4-3-5.2z"/><path d="M10 9.5h4"/>',
    "heart": f'<path d="{HEART_PATH}"/>',
}


def icon_svg(name: str, size: int = 28) -> str:
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{TEAL}" '
            f'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">{ICON_PATHS[name]}</svg>')


HERO_SVG = f"""
<svg viewBox="0 0 280 220" width="100%" style="max-width:320px" role="img"
     aria-label="Health report clipboard with a magnifying glass and a heart">
  <circle cx="140" cy="112" r="92" fill="{TEAL_SOFT}"/>
  <rect x="86" y="36" width="118" height="148" rx="12" fill="#FFFFFF" stroke="{TEAL}" stroke-width="3"/>
  <rect x="118" y="26" width="54" height="20" rx="7" fill="{TEAL}"/>
  <rect x="104" y="66" width="82" height="8" rx="4" fill="#C9D5D2"/>
  <rect x="104" y="82" width="58" height="8" rx="4" fill="#C9D5D2"/>
  <path d="M102 130 H126 L134 108 L146 154 L156 122 L162 130 H188" fill="none" stroke="{TEAL}"
        stroke-width="3" stroke-linejoin="round" stroke-linecap="round"/>
  <circle cx="214" cy="60" r="22" fill="{TEAL}"/>
  <rect x="210" y="48" width="8" height="24" rx="2" fill="#FFFFFF"/>
  <rect x="202" y="56" width="24" height="8" rx="2" fill="#FFFFFF"/>
  <circle cx="64" cy="146" r="24" fill="#FFFFFF" fill-opacity=".85" stroke="{TEAL}" stroke-width="7"/>
  <path d="M82 164 L102 184" stroke="{TEAL}" stroke-width="9" stroke-linecap="round"/>
  <path d="{HEART_PATH}" transform="translate(204 140) scale(1.6)" fill="{RED}"/>
</svg>
"""

# ---------------------------------------------------------------------------
# Database (SQLite)
# ---------------------------------------------------------------------------


def db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with closing(db()) as conn, conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            salt TEXT NOT NULL,
            pw_hash TEXT,
            profile TEXT NOT NULL DEFAULT '{}')""")
        conn.execute("""CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            ts REAL NOT NULL,
            data TEXT NOT NULL)""")


def hash_pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 120_000).hex()


def create_user(name: str, email: str, password: str):
    salt = secrets.token_hex(16)
    try:
        with closing(db()) as conn, conn:
            cur = conn.execute("INSERT INTO users (email, name, salt, pw_hash) VALUES (?,?,?,?)",
                               (email, name, salt, hash_pw(password, salt)))
            return {"id": cur.lastrowid, "email": email, "name": name}, None
    except sqlite3.IntegrityError:
        return None, "An account with this email already exists. Sign in instead."


def verify_user(email: str, password: str):
    with closing(db()) as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if row and row["pw_hash"] and secrets.compare_digest(row["pw_hash"], hash_pw(password, row["salt"])):
        return {"id": row["id"], "email": row["email"], "name": row["name"]}
    return None


def guest_user():
    with closing(db()) as conn, conn:
        row = conn.execute("SELECT * FROM users WHERE email = 'guest@local'").fetchone()
        if row is None:
            cur = conn.execute("INSERT INTO users (email, name, salt, pw_hash) VALUES ('guest@local','Guest','00',NULL)")
            return {"id": cur.lastrowid, "email": "guest@local", "name": "Guest"}
        return {"id": row["id"], "email": row["email"], "name": row["name"]}


def get_profile(uid: int) -> dict:
    with closing(db()) as conn:
        row = conn.execute("SELECT profile FROM users WHERE id = ?", (uid,)).fetchone()
    return json.loads(row["profile"]) if row else {}


def save_profile(uid: int, profile: dict) -> None:
    with closing(db()) as conn, conn:
        conn.execute("UPDATE users SET profile = ? WHERE id = ?", (json.dumps(profile), uid))


def add_history(uid: int, result: dict) -> int:
    with closing(db()) as conn, conn:
        cur = conn.execute("INSERT INTO history (user_id, ts, data) VALUES (?,?,?)",
                           (uid, result["ts"], json.dumps(result)))
        return cur.lastrowid


def get_history(uid: int) -> list:
    with closing(db()) as conn:
        rows = conn.execute("SELECT id, data FROM history WHERE user_id = ? ORDER BY ts DESC", (uid,)).fetchall()
    out = []
    for row in rows:
        item = json.loads(row["data"])
        item["hid"] = row["id"]
        out.append(item)
    return out


def delete_history(uid: int, hid=None) -> None:
    with closing(db()) as conn, conn:
        if hid is None:
            conn.execute("DELETE FROM history WHERE user_id = ?", (uid,))
        else:
            conn.execute("DELETE FROM history WHERE user_id = ? AND id = ?", (uid, hid))


# ---------------------------------------------------------------------------
# Prediction logic
# ---------------------------------------------------------------------------


def to_celsius(temp):
    if not temp:
        return None
    temp = float(temp)
    return round((temp - 32) * 5 / 9, 1) if temp > 45 else temp


def bmi_calc(height, weight):
    try:
        h, w = float(height), float(weight)
    except (TypeError, ValueError):
        return None
    if h <= 0 or w <= 0:
        return None
    m = h / 100
    value = w / (m * m)
    if value < 18.5:
        category, tone = "Underweight", "warn"
    elif value < 25:
        category, tone = "Healthy weight", "ok"
    elif value < 30:
        category, tone = "Overweight", "warn"
    else:
        category, tone = "Obese range", "crit"
    return {"value": round(value, 1), "category": category, "tone": tone,
            "low": round(18.5 * m * m), "high": round(24.9 * m * m), "south_asian_risk": 23 <= value < 25}


def boost(disease, profile, ctx, age, bmi) -> float:
    did, b = disease["id"], 0.0
    cond = profile.get("cond", [])
    if "mosquito" in ctx and did in {"dengue", "malaria", "chik"}:
        b += .07
    if "water" in ctx and did in {"typhoid", "gastro", "jaundice"}:
        b += .07
    if "contact" in ctx and did in {"cold", "flu", "covid"}:
        b += .06
    if "dust" in ctx and did in {"allergy", "asthma"}:
        b += .07
    if did == "diabetes" and ("diabetes" in cond or bmi >= 25):
        b += .06
    if did == "bp" and ("bp" in cond or bmi >= 25):
        b += .06
    if did == "asthma" and "asthma" in cond:
        b += .10
    if age >= 60 and did in {"pneumonia", "flu", "covid"}:
        b += .05
    if profile.get("smoker") and did in {"pneumonia", "asthma"}:
        b += .03
    if profile.get("sex") == "female" and did in {"anemia", "uti"}:
        b += .04
    return b


def analyze(selected, dur_days, severity, temp, ctx, profile) -> dict:
    sel = set(selected)
    temp_c = to_celsius(temp)
    if temp_c is not None and temp_c >= 37.8:
        sel.add("fever")
    age = float(profile.get("age") or 0)
    bmi_info = bmi_calc(profile.get("height"), profile.get("weight"))
    bmi = bmi_info["value"] if bmi_info else 0
    damp = min(1.0, 0.7 + 0.1 * len(sel))

    ranked = []
    for d in DISEASES:
        weights = d["sym"]
        matched = [k for k in weights if k in sel]
        if not matched:
            continue
        coverage = sum(weights[k] for k in matched) / sum(weights.values())
        precision = len(matched) / len(sel)
        core = [k for k, w in weights.items() if w >= 3]
        core_hit = sum(1 for k in core if k in sel) / len(core) if core else 0
        score = (0.5 * coverage + 0.3 * precision + 0.2 * core_hit) * damp
        score += boost(d, profile, ctx, age, bmi)
        score += 0.03 if d["dur"][0] <= dur_days <= d["dur"][1] else -0.05
        pct = round(max(0.0, min(0.96, score)) * 100)
        if pct > 0:
            ranked.append({"id": d["id"], "pct": pct, "matched": matched})
    ranked.sort(key=lambda r: -r["pct"])

    flags, reasons = [], []
    if "chest_pain" in sel and "short_breath" in sel:
        flags.append("Chest pain with breathlessness can point to a heart or lung emergency.")
    if "short_breath" in sel and severity == "Severe":
        flags.append("Severe difficulty in breathing needs immediate care.")
    if "bleeding_gums" in sel and "fever" in sel and ("vomiting" in sel or "abd_pain" in sel):
        flags.append("Fever with bleeding and vomiting or stomach pain are dengue warning signs.")

    if flags:
        level = "emergency"
    else:
        if severity == "Severe":
            reasons.append("You rated your symptoms as severe.")
        if temp_c is not None and temp_c >= 39.5:
            reasons.append("Your temperature is above 39.5 °C.")
        if dur_days >= 10 and "fever" in sel:
            reasons.append("Fever that lasts more than a week needs a check.")
        if "yellow" in sel:
            reasons.append("Yellow skin or eyes need a blood test.")
        if ranked and ranked[0]["id"] in SERIOUS and ranked[0]["pct"] >= 50:
            reasons.append("The top match is a condition that needs a medical test.")
        level = "soon" if reasons else "home"

    return {"ts": datetime.now().timestamp(), "sel": sorted(sel), "dur": dur_days, "sev": severity,
            "temp": temp_c, "ctx": list(ctx), "level": level, "flags": flags, "reasons": reasons,
            "ranked": ranked[:6], "age": age or None, "bmi": bmi or None}


def bp_category(sys_bp: float, dia_bp: float):
    if sys_bp <= dia_bp:
        return "warn", "Check the numbers", "The top number should be higher than the bottom number."
    if sys_bp > 180 or dia_bp > 120:
        return "crit", "Very high range", "Rest for five minutes and measure again. If it stays this high, or you have chest pain, headache or breathlessness, get emergency care."
    if sys_bp >= 140 or dia_bp >= 90:
        return "crit", "Stage 2 high range", "See a doctor soon for a proper check and treatment plan."
    if sys_bp >= 130 or dia_bp >= 80:
        return "warn", "Stage 1 high range", "Cut down salt, exercise and recheck on other days. Talk to a doctor if it stays here."
    if sys_bp >= 120:
        return "warn", "Elevated", "Slightly above ideal. Lifestyle changes help."
    if sys_bp < 90 or dia_bp < 60:
        return "warn", "Low range", "If you feel faint or dizzy, sit down, drink water and see a doctor."
    return "ok", "Normal range", "Keep up regular exercise and low salt food."


def sugar_category(kind: str, value: float):
    if value < 70:
        return "warn", "Low range", "Take something sweet now if you feel shaky or sweaty, and speak to a doctor."
    low, high = (100, 126) if kind == "Fasting" else (140, 200)
    if value < low:
        return "ok", "Normal range", "Within the usual range for this type of reading."
    if value < high:
        return "warn", "Prediabetes range", "Higher than normal. Ask your doctor for an HbA1c test and review diet and exercise."
    return "crit", "Diabetes range", "This reading is in the diabetes range. Only a doctor can confirm, so book a test soon."


def duration_label(days: int) -> str:
    return next((k for k, v in DURATIONS.items() if v == days), f"{days} days")


def fmt_ts(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%d %b %Y, %I:%M %p")


def report_text(r: dict, name: str) -> str:
    lines = ["DISEASE PREDICTION - SYMPTOM REPORT", fmt_ts(r["ts"]), f"Name: {name}", "",
             "Symptoms: " + ", ".join(LABEL[k] for k in r["sel"]),
             f"Duration: {duration_label(r['dur'])} | Severity: {r['sev']}"
             + (f" | Temp: {r['temp']} C" if r.get("temp") else ""),
             "", f"Advice level: {URGENCY[r['level']]['title']}"]
    lines += [f"- {x}" for x in r["flags"] + r["reasons"]]
    lines += ["", "Possible matches:"]
    lines += [f"{i}. {DIS[x['id']]['name']} - {x['pct']}%" for i, x in enumerate(r["ranked"], 1)]
    if r["ranked"]:
        top = DIS[r["ranked"][0]["id"]]
        lines += ["", "Suggested steps:"] + [f"- {c}" for c in top["care"]] + [f"See: {top['doctor']}"]
    lines += ["", "This report is information only and not a medical diagnosis."]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------
TONE_BOX = {"crit": st.error, "warn": st.warning, "ok": st.success}


def goto(page: str) -> None:
    st.session_state.page = page


def login_user(user: dict) -> None:
    st.session_state.user = user
    st.session_state.page = "Dashboard"
    for key in ("step", "sel", "details", "result"):
        st.session_state.pop(key, None)


def render_result(r: dict, key: str, name: str) -> None:
    urg = URGENCY[r["level"]]
    msg = f"**{urg['title']}**  \n{urg['text']}"
    extra = r["flags"] + r["reasons"]
    if extra:
        msg += "\n\n" + "\n".join(f"- {x}" for x in extra)
    TONE_BOX[urg["tone"]](msg)

    facts = [fmt_ts(r["ts"]), f"{len(r['sel'])} symptoms", f"duration: {duration_label(r['dur']).lower()}",
             f"severity: {r['sev'].lower()}"]
    if r.get("temp"):
        facts.append(f"temperature: {r['temp']} °C")
    if r.get("age"):
        facts.append(f"age: {int(r['age'])}")
    if r.get("bmi"):
        facts.append(f"BMI: {r['bmi']}")
    st.caption(" · ".join(facts))

    ranked = r["ranked"]
    if not ranked:
        st.info("No clear match. Your symptoms do not line up with any condition in this checker. "
                "A doctor can examine you and decide on tests.")
    else:
        top = ranked[0]
        d = DIS[top["id"]]
        with st.container(border=True):
            c1, c2 = st.columns([1, 3], vertical_alignment="center")
            c1.metric("Symptom match", f"{top['pct']}%")
            c2.markdown(f"{icon_svg(d['icon'], 34)}", unsafe_allow_html=True)
            c2.markdown(f"#### {d['name']}")
            c2.write(d["desc"])
            st.markdown("**Why it matched**")
            st.markdown("  ".join(f"`{LABEL[k]}`" for k in top["matched"]))
            missing = sorted((k for k in d["sym"] if k not in r["sel"]), key=lambda k: -d["sym"][k])[:5]
            if missing:
                st.markdown("**Typical signs you did not select**")
                st.markdown("  ".join(f"`{LABEL[k]}`" for k in missing))
            st.markdown("**What you can do**")
            st.markdown("\n".join(f"- {c}" for c in d["care"]))
            st.markdown(f"**Who to see:** {d['doctor']}")
        if len(ranked) > 1:
            st.markdown("**Other possibilities**")
            for x in ranked[1:]:
                a, b, c = st.columns([3, 4, 1], vertical_alignment="center")
                a.write(DIS[x["id"]]["name"])
                b.progress(x["pct"] / 100)
                c.write(f"{x['pct']}%")
    st.caption("The match score shows how closely your symptoms fit a condition. It is not a probability and "
               "not a diagnosis. Only a doctor can diagnose you. If you feel very unwell, do not wait for an online result.")
    st.download_button("Download report (.txt)", report_text(r, name), file_name=f"symptom-report-{int(r['ts'])}.txt",
                       key=f"dl_{key}")


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------


def page_login() -> None:
    left, right = st.columns([1, 1], gap="large", vertical_alignment="center")
    with left:
        st.markdown(HERO_SVG, unsafe_allow_html=True)
        st.title("Disease Prediction")
        st.write("Pick your symptoms, answer a few questions and get a ranked list of likely conditions, "
                 "how urgent it is and which doctor to see.")
        st.caption("Information only. Not a medical diagnosis.")
    with right:
        tab_in, tab_up = st.tabs(["Sign in", "Create account"])
        with tab_in:
            with st.form("signin"):
                email = st.text_input("Email")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Sign in", type="primary", use_container_width=True):
                    user = verify_user(email.strip().lower(), password)
                    if user:
                        login_user(user)
                        st.rerun()
                    else:
                        st.error("Email or password is incorrect.")
        with tab_up:
            with st.form("signup"):
                name = st.text_input("Your name")
                email = st.text_input("Email", key="su_email")
                password = st.text_input("Password (at least 6 characters)", type="password", key="su_pw")
                if st.form_submit_button("Create account", type="primary", use_container_width=True):
                    email = email.strip().lower()
                    if not name.strip():
                        st.error("Enter your name.")
                    elif "@" not in email or "." not in email.split("@")[-1]:
                        st.error("Enter a valid email address.")
                    elif len(password) < 6:
                        st.error("Password must have at least 6 characters.")
                    else:
                        user, err = create_user(name.strip(), email, password)
                        if err:
                            st.error(err)
                        else:
                            login_user(user)
                            st.rerun()
        st.divider()
        if st.button("Continue as guest", use_container_width=True):
            login_user(guest_user())
            st.rerun()
        st.caption("Accounts and reports are saved in a local SQLite file next to this app.")


def page_dashboard() -> None:
    user = st.session_state.user
    history = get_history(user["id"])
    profile = get_profile(user["id"])
    bmi = bmi_calc(profile.get("height"), profile.get("weight"))
    first = user["name"].split()[0] if user["name"] else "there"

    with st.container(border=True):
        left, right = st.columns([3, 2], vertical_alignment="center")
        with left:
            st.caption("DISEASE PREDICTION DASHBOARD")
            st.title(f"Vanakkam, {first}")
            st.write("Select your symptoms and get a ranked list of likely conditions, how urgent it is and "
                     "which doctor to see.")
            b1, b2, _ = st.columns([2, 2, 3])
            b1.button("Start symptom check", type="primary", on_click=goto, args=("Symptom Check",))
            b2.button("Health tools", on_click=goto, args=("Health Tools",))
        with right:
            st.markdown(HERO_SVG, unsafe_allow_html=True)

    last_advice = {"emergency": "Emergency", "soon": "See a doctor", "home": "Home care"}
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Checks done", len(history))
    m2.metric("Your BMI", bmi["value"] if bmi else "--")
    m3.metric("Last advice", last_advice[history[0]["level"]] if history else "No checks yet")
    m4.metric("Conditions covered", len(DISEASES))

    st.subheader("Conditions we check")
    cols = st.columns(3)
    for i, (icon, title, text) in enumerate(AREAS):
        with cols[i % 3].container(border=True):
            st.markdown(
                f'<div style="display:flex;gap:14px;align-items:center">'
                f'<div style="flex:none;width:48px;height:48px;border-radius:12px;background:rgba(31,163,150,.16);'
                f'display:flex;align-items:center;justify-content:center">{icon_svg(icon)}</div>'
                f'<div><b>{title}</b><br><span style="opacity:.7;font-size:.9em">{text}</span></div></div>',
                unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1.container(border=True):
        st.markdown("**Last report**")
        if history:
            last = history[0]
            top = last["ranked"][0] if last["ranked"] else None
            st.caption(fmt_ts(last["ts"]))
            st.markdown(f"#### {DIS[top['id']]['name']}" if top else "#### No clear match")
            if top:
                st.write(f"Symptom match {top['pct']}% from {len(last['sel'])} symptoms.")
            st.button("Open history", on_click=goto, args=("History",), key="open_hist")
        else:
            st.write("No checks yet. Your first report will appear here.")
    with c2.container(border=True):
        st.markdown("**Tip for today**")
        st.info(TIPS[datetime.now().weekday() % len(TIPS)])
        if not profile.get("age"):
            st.caption("Add your age, height and weight in Profile for sharper results.")


def page_check() -> None:
    s = st.session_state
    user = s.user
    s.setdefault("step", 1)
    s.setdefault("sel", [])
    s.setdefault("details", {"dur": "1 to 3 days", "sev": "Moderate", "temp": 0.0, "ctx": []})
    s.setdefault("result", None)

    st.header("Symptom check")
    labels = {1: "Step 1 of 3: Symptoms", 2: "Step 2 of 3: Details", 3: "Step 3 of 3: Report"}
    st.progress(s.step / 3, text=labels[s.step])

    if s.step == 1:
        st.subheader("Which symptoms do you have?")
        st.caption("Select everything that applies. Pick at least two.")
        chosen = []
        cols = st.columns(2)
        for i, (group, items) in enumerate(SYMPTOM_GROUPS.items()):
            with cols[i % 2]:
                chosen += st.multiselect(group, options=list(items), format_func=items.get,
                                         default=[k for k in s.sel if k in items], key=f"ms_{group}")
        st.write(f"**{len(chosen)}** selected")
        if st.button("Next: details", type="primary", disabled=len(chosen) < 2):
            s.sel = chosen
            s.step = 2
            st.rerun()

    elif s.step == 2:
        det = s.details
        st.subheader("A few more details")
        st.caption("These change how likely each condition is and how urgent it looks.")
        dur = st.select_slider("How long have you had these symptoms?", options=list(DURATIONS), value=det["dur"])
        sev = st.radio("How severe are they?", SEVERITIES, index=SEVERITIES.index(det["sev"]), horizontal=True)
        temp = st.number_input("Body temperature in °C (optional)", min_value=0.0, max_value=115.0,
                               value=float(det["temp"]), step=0.1,
                               help="Leave at 0 if you did not measure. A value above 45 is read as °F.")
        ctx = st.multiselect("Does any of this apply?", list(CONTEXT), format_func=CONTEXT.get, default=det["ctx"])
        if not get_profile(user["id"]).get("age"):
            st.caption("Tip: add your age and health details in Profile to improve the report.")
        back, go = st.columns(2)
        if back.button("Back"):
            s.details = {"dur": dur, "sev": sev, "temp": temp, "ctx": ctx}
            s.step = 1
            st.rerun()
        if go.button("Get my report", type="primary"):
            s.details = {"dur": dur, "sev": sev, "temp": temp, "ctx": ctx}
            result = analyze(s.sel, DURATIONS[dur], sev, temp, ctx, get_profile(user["id"]))
            result["hid"] = add_history(user["id"], result)
            s.result = result
            s.step = 3
            st.rerun()

    else:
        render_result(s.result, "current", user["name"])
        if st.button("New check", type="primary"):
            for key in ("step", "sel", "details", "result"):
                s.pop(key, None)
            st.rerun()


def page_history() -> None:
    user = st.session_state.user
    st.header("Your past reports")
    history = get_history(user["id"])
    if not history:
        st.info("No reports yet. Run a symptom check and it will be saved here.")
        st.button("Start a symptom check", type="primary", on_click=goto, args=("Symptom Check",))
        return
    for r in history:
        top = r["ranked"][0] if r["ranked"] else None
        title = f"{fmt_ts(r['ts'])} - {DIS[top['id']]['name']} ({top['pct']}%)" if top else f"{fmt_ts(r['ts'])} - No clear match"
        with st.expander(title):
            render_result(r, str(r["hid"]), user["name"])
            with st.popover("Delete this report"):
                st.write("Delete this report for good?")
                if st.button("Yes, delete", key=f"del_{r['hid']}"):
                    delete_history(user["id"], r["hid"])
                    st.rerun()
    st.divider()
    with st.popover("Clear all history"):
        st.write("This removes every saved report.")
        if st.button("Yes, clear all", key="clear_all"):
            delete_history(user["id"])
            st.rerun()


def page_tools() -> None:
    st.header("Quick health calculators")
    st.caption("These show ranges, not diagnoses.")
    tab_bmi, tab_bp, tab_sugar = st.tabs(["Body mass index", "Blood pressure", "Blood sugar"])
    with tab_bmi:
        c1, c2 = st.columns(2)
        h = c1.number_input("Height (cm)", 0.0, 250.0, 0.0, step=1.0, key="t_h")
        w = c2.number_input("Weight (kg)", 0.0, 300.0, 0.0, step=0.5, key="t_w")
        b = bmi_calc(h, w)
        if b:
            msg = f"**BMI {b['value']} - {b['category']}**  \nHealthy weight for your height: {b['low']} to {b['high']} kg."
            if b["south_asian_risk"]:
                msg += "  \nFor South Asians, health risk can begin from a BMI of 23."
            TONE_BOX[b["tone"]](msg)
        else:
            st.info("Enter height and weight.")
    with tab_bp:
        c1, c2 = st.columns(2)
        sys_bp = c1.number_input("Systolic, the top number (mmHg)", 0, 300, 0, key="t_sys")
        dia_bp = c2.number_input("Diastolic, the bottom number (mmHg)", 0, 200, 0, key="t_dia")
        if sys_bp and dia_bp:
            tone, title, text = bp_category(sys_bp, dia_bp)
            TONE_BOX[tone](f"**{sys_bp}/{dia_bp} - {title}**  \n{text}")
        else:
            st.info("Enter both readings in mmHg.")
    with tab_sugar:
        c1, c2 = st.columns(2)
        kind = c1.selectbox("Reading taken", ["Fasting", "2 hours after a meal"], key="t_kind")
        value = c2.number_input("Value (mg/dL)", 0, 800, 0, key="t_sv")
        if value:
            tone, title, text = sugar_category(kind, value)
            TONE_BOX[tone](f"**{value} mg/dL - {title}**  \n{text}")
        else:
            st.info("Enter your reading.")


def page_profile() -> None:
    user = st.session_state.user
    p = get_profile(user["id"])
    st.header("Your health profile")
    st.caption("Used to adjust your symptom reports.")
    with st.form("profile"):
        c1, c2 = st.columns(2)
        age = c1.number_input("Age", 0, 120, int(p.get("age") or 0))
        sexes = ["", "female", "male", "other"]
        sex = c2.selectbox("Sex", sexes, index=sexes.index(p.get("sex", "")) if p.get("sex", "") in sexes else 0,
                           format_func=lambda x: x.capitalize() if x else "Select")
        height = c1.number_input("Height (cm)", 0.0, 250.0, float(p.get("height") or 0.0), step=1.0)
        weight = c2.number_input("Weight (kg)", 0.0, 300.0, float(p.get("weight") or 0.0), step=0.5)
        cond = st.multiselect("Health background", list(CONDITIONS), format_func=CONDITIONS.get,
                              default=[c for c in p.get("cond", []) if c in CONDITIONS])
        smoker = st.checkbox("I smoke", value=bool(p.get("smoker")))
        if st.form_submit_button("Save profile", type="primary"):
            save_profile(user["id"], {"age": age or None, "sex": sex, "height": height or None,
                                      "weight": weight or None, "cond": cond, "smoker": smoker})
            st.success("Profile saved.")
            st.rerun()
    b = bmi_calc(p.get("height"), p.get("weight"))
    if b:
        TONE_BOX[b["tone"]](f"**BMI {b['value']} - {b['category']}**")
    st.divider()
    st.caption(f"Account: {user['name']}" + ("" if user["email"] == "guest@local" else f" · {user['email']}"))


PAGES = {
    "Dashboard": page_dashboard,
    "Symptom Check": page_check,
    "History": page_history,
    "Health Tools": page_tools,
    "Profile": page_profile,
}


def main() -> None:
    st.set_page_config(page_title="Disease Prediction", page_icon="\U0001FA7A", layout="wide")
    st.markdown("<style>.block-container{max-width:1100px;padding-top:2rem}</style>", unsafe_allow_html=True)
    init_db()
    if "user" not in st.session_state:
        page_login()
        return
    st.session_state.setdefault("page", "Dashboard")
    with st.sidebar:
        st.markdown(f"### Disease Prediction")
        st.caption(f"Signed in as {st.session_state.user['name']}")
        st.radio("Menu", list(PAGES), key="page", label_visibility="collapsed")
        if st.button("Sign out", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
    PAGES[st.session_state.page]()


if __name__ == "__main__":
    main()
