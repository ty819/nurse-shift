import csv
import json
import pathlib
from typing import Any, Dict, List

from jsonschema import Draft202012Validator


def load_json(path: str | pathlib.Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_schema(schema_path: str | pathlib.Path) -> Draft202012Validator:
    schema = load_json(schema_path)
    return Draft202012Validator(schema)


def parse_bool(value: str) -> bool | None:
    if value is None:
        return None
    v = str(value).strip().lower()
    if v in {"true", "1", "yes", "y"}:
        return True
    if v in {"false", "0", "no", "n"}:
        return False
    return None


def parse_nurses_csv(csv_path: str | pathlib.Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parsed: Dict[str, Any] = {
                "id": str(row.get("id", "")).strip(),
                "name": (row.get("name") or "").strip(),
                "team": (row.get("team") or "").strip(),
                "leader_ok": parse_bool(row.get("leader_ok")),
                "day_ok": parse_bool(row.get("day_ok")),
                "late_ok": parse_bool(row.get("late_ok")),
                "night_ok": parse_bool(row.get("night_ok")),
                "week_max_days": int(row["week_max_days"]) if (row.get("week_max_days") or "").isdigit() else None,
                "weekend_cap": int(row["weekend_cap"]) if (row.get("weekend_cap") or "").isdigit() else None,
                "notes": row.get("notes"),
            }
            rows.append(parsed)
    return rows


def validate_nurses(nurses: List[Dict[str, Any]], schema_path: str | pathlib.Path) -> List[str]:
    validator = load_schema(schema_path)
    errors: List[str] = []
    # Validate as an array schema by wrapping in a fake root if needed
    # Here we validate item-by-item to produce clearer messages
    for idx, nurse in enumerate(nurses):
        for err in validator.iter_errors([nurse]):  # schema expects array
            errors.append(f"nurses[{idx}]: {err.message}")
    return errors


def validate_rules(rules: Dict[str, Any], schema_path: str | pathlib.Path) -> List[str]:
    validator = load_schema(schema_path)
    errors: List[str] = []
    for err in validator.iter_errors(rules):
        errors.append(err.message)
    return errors


def load_and_validate(
    nurses_csv: str | pathlib.Path,
    rules_json: str | pathlib.Path,
    schemas_dir: str | pathlib.Path,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    schemas_dir = pathlib.Path(schemas_dir)
    nurses_schema = schemas_dir / "nurses.schema.json"
    rules_schema = schemas_dir / "rules.schema.json"

    nurses = parse_nurses_csv(nurses_csv)
    rules = load_json(rules_json)

    nerrs = validate_nurses(nurses, nurses_schema)
    rerrs = validate_rules(rules, rules_schema)
    if nerrs or rerrs:
        msg = "\n".join(["NURSES ERRORS:"] + nerrs + ["", "RULES ERRORS:"] + rerrs)
        raise ValueError(msg)

    return nurses, rules

