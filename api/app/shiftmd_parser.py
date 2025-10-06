from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple, Set

TEAM_HEADERS = {
    "Aチーム": "A",
    "Bチーム": "B",
    "救急チーム": "ER",
}

LEADER_WEEKEND_IDS: Set[str] = set(map(str, [2,3,4,5,6,7,15,16,17,18]))
NIGHT_FORBIDDEN_PAIRS = [("7", "26")]
CANNOT_LEAD_NIGHT = set(map(str, [9,11,19,20,27,29,30]))


def _ids_from_token(token: str) -> List[str]:
    return [s for s in token.split(".") if s.strip()]


def parse_shift_md(md_text: str, year: int, month: int) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    team: str | None = None
    nurses: Dict[str, Dict[str, Any]] = {}
    person_rules: Dict[str, Dict[str, Any]] = {}

    lines = [ln.strip() for ln in md_text.splitlines()]

    def ensure_nurse(nid: str, team_code: str):
        if nid not in nurses:
            nurses[nid] = {
                "id": nid,
                "name": f"Nurse_{nid}",
                "team": team_code,
                "leader_ok": False,
                "day_ok": True,
                "late_ok": True,
                "night_ok": True,
                "week_max_days": None,
                "weekend_cap": None,
                "notes": None,
            }
        if nid not in person_rules:
            person_rules[nid] = {}

    for raw in lines:
        if not raw:
            continue
        if raw in TEAM_HEADERS:
            team = TEAM_HEADERS[raw]
            continue
        if raw == "その他":
            team = None
            continue
        if team in {"A", "B", "ER"}:
            m = re.match(r"^([0-9.]+)[:：](.+)$", raw)
            if not m:
                continue
            ids = _ids_from_token(m.group(1))
            desc = m.group(2)
            for nid in ids:
                ensure_nurse(nid, team)
                pr = person_rules[nid]
                # rules per description
                if "管理者" in desc:
                    nurses[nid]["leader_ok"] = True
                if "日勤のみ" in desc:
                    nurses[nid]["night_ok"] = False
                    nurses[nid]["late_ok"] = False
                    pr["only_day"] = True
                if "平日日勤" in desc:
                    pr["only_day"] = True
                    pr["weekend_off"] = True
                    nurses[nid]["night_ok"] = False
                    nurses[nid]["late_ok"] = False
                if "日勤4回/週" in desc:
                    pr["only_day"] = True
                    pr["week_max_days"] = 4
                    nurses[nid]["night_ok"] = False
                    nurses[nid]["late_ok"] = False
                if "夜勤専従" in desc:
                    nurses[nid]["day_ok"] = False
                    nurses[nid]["late_ok"] = False
                    pr["only_night"] = True
                if "夜勤" in desc and "回/月" in desc:
                    rng = re.search(r"(\d+)[-～–](\d+)回/月", desc)
                    if rng:
                        pr["night_min"] = int(rng.group(1))
                        pr["night_max"] = int(rng.group(2))
                    else:
                        eq = re.search(r"(\d+)回/月", desc)
                        if eq:
                            pr["night_min"] = pr["night_max"] = int(eq.group(1))
                if "新人" in desc and "夜勤2回/月" in desc:
                    pr["night_min"] = pr["night_max"] = 2
                    pr["extra_staff"] = True
                if "2回/週" in desc:
                    pr["week_max_days"] = 2
                if "土日祝日3回/月まで" in desc or "土日祝3回/月" in desc:
                    pr["weekend_cap_per_month"] = 3
                if "土日祝日NG" in desc or "土日祝NG" in desc:
                    pr["weekend_off"] = True
                if "9:00-17:00" in desc:
                    pr["fixed_hours"] = "09:00-17:00"
                if "9:00-16:30" in desc:
                    pr["fixed_hours"] = "09:00-16:30"
                if "9:00-13:00" in desc:
                    pr["fixed_hours"] = "09:00-13:00"
                if "日勤なし" in desc:
                    nurses[nid]["day_ok"] = False
                    pr["only_night"] = True
                if "土日夜勤2回/月" in desc:
                    pr["only_night"] = True
                    pr["weekend_only_night"] = True
                    pr["night_min"] = pr.get("night_min", 2)
                    pr["night_max"] = pr.get("night_max", 2)
                if "バイト" in desc and "土日勤" in desc:
                    pr["only_day"] = True
                    pr["weekend_day_only"] = True
                    pr["month_quota_days"] = 2
                if "日勤バイト" in desc:
                    pr["only_day"] = True
                    pr["month_quota_days"] = 2
                if "公休10日" in desc:
                    pr["extra_holidays"] = 1
        else:
            # その他: global constraints are handled below by constants
            continue

    # Leader capable on weekend/holiday
    for nid in LEADER_WEEKEND_IDS:
        if nid in nurses:
            nurses[nid]["leader_ok"] = True

    # Cannot lead night map
    for nid in CANNOT_LEAD_NIGHT:
        if nid not in person_rules:
            person_rules[nid] = {}
        person_rules[nid]["cannot_lead_night"] = True

    # Default demand
    rules: Dict[str, Any] = {
        "year": year,
        "month": month,
        "holidays": [],
        "leader_requirement": {"weekend_holiday": list(LEADER_WEEKEND_IDS)},
        "forbidden_pairs": {"night": NIGHT_FORBIDDEN_PAIRS},
        "demand_defaults": {
            "weekday": {"day_min": 11, "day_max": 14, "late": 1, "night": 3},
            "saturday_holiday": {"day_min": 8, "day_max": 8, "late": 0, "night": 3},
            "sunday": {"day_min": 7, "day_max": 7, "late": 0, "night": 3},
        },
        "person_rules": person_rules,
    }

    return list(nurses.values()), rules
