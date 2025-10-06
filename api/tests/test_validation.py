import pathlib
import json
from app.validation import load_and_validate
from app.optimizer import to_csv, recheck_assignments, build_schedule

ROOT = pathlib.Path(__file__).parents[2]


def test_load_and_validate_samples():
    nurses_csv = ROOT / "samples/nurses.csv"
    rules_json = ROOT / "samples/rules.json"
    schemas = ROOT / "packages/schemas"
    nurses, rules = load_and_validate(nurses_csv, rules_json, schemas)
    assert isinstance(nurses, list) and len(nurses) > 0
    assert isinstance(rules, dict) and rules.get("year")


def test_to_csv_roundtrip():
    assignments = [
        {"nurse_id": "1", "date": "2025-10-01", "shift": "OFF"},
        {"nurse_id": "2", "date": "2025-10-01", "shift": "DAY"},
    ]
    csv_text = to_csv(assignments)
    assert "nurse_id,date,shift" in csv_text


def test_recheck_basic():
    nurses_csv = ROOT / "samples/nurses.csv"
    rules_json = ROOT / "samples/rules.json"
    schemas = ROOT / "packages/schemas"
    nurses, rules = load_and_validate(nurses_csv, rules_json, schemas)
    # deliberately wrong demand (no nights), expect violations
    assignments = [
        {"nurse_id": "1", "date": f"{rules['year']}-{rules['month']:02d}-01", "shift": "DAY"},
    ]
    res = recheck_assignments(assignments, nurses, rules)
    assert res["ok"] is False
    assert res["violations"]


def test_build_schedule_alternatives():
    nurses_csv = ROOT / "samples/nurses.csv"
    rules_json = ROOT / "samples/rules.json"
    schemas = ROOT / "packages/schemas"
    nurses, rules = load_and_validate(nurses_csv, rules_json, schemas)
    res = build_schedule(nurses, rules, alternatives=2)
    assert res["status"] == "OK"
    assert "solutions" in res
    assert isinstance(res["solutions"], list)
    assert len(res["solutions"]) >= 1

