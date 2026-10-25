import json
import os

DATA_FILE = "rental_records.json"

def _load_data():
    """Helper to load all saved records from local JSON storage."""
    if not os.path.exists(DATA_FILE):
        return {"baselines": [], "submissions": []}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"baselines": [], "submissions": []}

def _save_data(data):
    """Helper to write records back to local JSON storage."""
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def save_move_in_baseline(name, unit, room, photo_path, date_str, jurisdiction):
    """Saves a move-in baseline photo profile for a tenant/unit."""
    data = _load_data()
    baseline = {
        "name": name,
        "unit": unit,
        "room": room,
        "photo_path": photo_path,
        "date": date_str,
        "jurisdiction": jurisdiction
    }
    data["baselines"].append(baseline)
    _save_data(data)

def get_move_in_baselines(unit_filter=None):
    """Retrieves saved move-in baselines, optionally filtered by unit number."""
    data = _load_data()
    baselines = data.get("baselines", [])
    if unit_filter:
        return [b for b in baselines if b["unit"].strip().lower() == unit_filter.strip().lower()]
    return baselines

def save_submission(name, unit, room, before_path, after_path, jurisdiction, confirmed_items):
    """Saves the final move-out audit/dispute submission for the leasing office dashboard."""
    data = _load_data()
    sub = {
        "name": name,
        "unit": unit,
        "room": room,
        "before_path": before_path,
        "after_path": after_path,
        "jurisdiction": jurisdiction,
        "items": confirmed_items
    }
    data["submissions"].append(sub)
    _save_data(data)

def get_all_submissions():
    """Retrieves all final submissions for the leasing office dashboard."""
    data = _load_data()
    return data.get("submissions", [])
