# gamification.py
import json
from pathlib import Path
from datetime import datetime, timedelta
import tempfile
import os

DATA_FILE = Path("data/progress_db.json")
DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

# thresholds for badges (XP)
BADGE_THRESHOLDS = {
    50: "Getting Serious",
    100: "Consistency Champ",
    200: "Wellness Warrior",
    400: "Health Hero"
}

DEFAULT_USER_TEMPLATE = {
    "user_id": "",
    "name": "",
    "xp": 0,
    "streak": 0,
    "last_completed": None,  # "YYYY-MM-DD"
    "badges": [],
    "history": []  # list of events: {date, type, xp, note}
}

# -------------------------
# Utility: load + save (atomic write)
# -------------------------
def _load_db():
    if not DATA_FILE.exists():
        initial = {"users": []}
        _atomic_write(initial)
        return initial
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # if corrupted, recreate
        initial = {"users": []}
        _atomic_write(initial)
        return initial

def _atomic_write(obj):
    tmpfd, tmppath = tempfile.mkstemp(prefix="pg_", suffix=".json", dir=str(DATA_FILE.parent))
    with os.fdopen(tmpfd, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmppath, DATA_FILE)

def _save_db(db):
    _atomic_write(db)

def _find_user(db, user_id):
    for u in db["users"]:
        if u.get("user_id") == user_id:
            return u
    return None

# -------------------------
# API: create or get user
# -------------------------
def get_or_create_user(user_id, name=""):
    db = _load_db()
    user = _find_user(db, user_id)
    if user:
        return user
    # create
    new = DEFAULT_USER_TEMPLATE.copy()
    new["user_id"] = user_id
    new["name"] = name or user_id.split("@")[0]
    db["users"].append(new)
    _save_db(db)
    return new

# -------------------------
# Award XP, add badge
# -------------------------
def _award_xp_to_user(user, amount, note=None, event_type="custom"):
    user["xp"] = int(user.get("xp", 0)) + int(amount)
    # append history
    user.setdefault("history", []).append({
        "date": datetime.now().strftime("%Y-%m-%d"),
        "type": event_type,
        "xp": int(amount),
        "note": note or ""
    })
    # check badges
    for thresh, name in sorted(BADGE_THRESHOLDS.items()):
        if user["xp"] >= thresh and name not in user.get("badges", []):
            user.setdefault("badges", []).append(name)

# -------------------------
# Mark daily completion (returns (ok, msg))
# -------------------------
def mark_daily_completion(user_id, note="", daily_xp=10):
    db = _load_db()
    user = _find_user(db, user_id)
    if not user:
        user = get_or_create_user(user_id)

    today = datetime.now().date()
    last = user.get("last_completed")
    if last:
        last_date = datetime.strptime(last, "%Y-%m-%d").date()
    else:
        last_date = None

    if last_date == today:
        _save_db(db)
        return False, "Already marked today."

    # update streak
    if last_date:
        if (today - last_date).days == 1:
            user["streak"] = int(user.get("streak", 0)) + 1
        else:
            user["streak"] = 1
    else:
        user["streak"] = 1

    user["last_completed"] = today.strftime("%Y-%m-%d")
    _award_xp_to_user(user, daily_xp, note=note, event_type="completion")
    _save_db(db)
    return True, f"Awarded {daily_xp} XP. Current streak: {user['streak']}"

# -------------------------
# Mark upload (giving XP for uploading/analysis)
# -------------------------
def mark_upload(user_id, note="", upload_xp=20):
    db = _load_db()
    user = _find_user(db, user_id)
    if not user:
        user = get_or_create_user(user_id)
    _award_xp_to_user(user, upload_xp, note=note, event_type="upload")
    _save_db(db)
    return True, f"Awarded {upload_xp} XP for upload."

# -------------------------
# Manual award (for quests etc.)
# -------------------------
def award_xp(user_id, amount, note="", event_type="manual"):
    db = _load_db()
    user = _find_user(db, user_id)
    if not user:
        user = get_or_create_user(user_id)
    _award_xp_to_user(user, amount, note=note, event_type=event_type)
    _save_db(db)
    return True, f"Awarded {amount} XP."

# -------------------------
# Get user progress
# -------------------------
def get_user(user_id):
    db = _load_db()
    user = _find_user(db, user_id)
    if not user:
        return None
    return user

# -------------------------
# Leaderboard (top N)
# -------------------------
def get_leaderboard(top_n=10):
    db = _load_db()
    users = db.get("users", [])
    users_sorted = sorted(users, key=lambda u: u.get("xp", 0), reverse=True)
    return users_sorted[:top_n]

# -------------------------
# Reset user streak (utility)
# -------------------------
def reset_streak(user_id):
    db = _load_db()
    user = _find_user(db, user_id)
    if not user:
        return False, "User not found"
    user["streak"] = 0
    user["last_completed"] = None
    _save_db(db)
    return True, "Streak reset."

# -------------------------
# Export DB (for debugging)
# -------------------------
def export_db():
    return _load_db()
