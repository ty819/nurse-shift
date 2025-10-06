from __future__ import annotations

from typing import Any, Dict, List, Tuple, DefaultDict
from collections import defaultdict, Counter
import datetime as dt
from app.optimizer import days_in_month, is_weekend

Shift = str


def recommend_greedy(
    assignments: List[Dict[str, Any]],
    nurses: List[Dict[str, Any]],
    rules: Dict[str, Any],
) -> Dict[str, Any]:
    year = int(rules["year"])
    month = int(rules["month"])
    all_days = [d.isoformat() for d in days_in_month(year, month)]

    nurse_by_id = {str(n["id"]): n for n in nurses}

    per_day_counts: DefaultDict[str, Counter] = defaultdict(Counter)
    has_assignment: DefaultDict[Tuple[str, str], bool] = defaultdict(bool)
    for a in assignments:
        nid = str(a["nurse_id"])
        date = a["date"]
        shift = a["shift"]
        per_day_counts[date][shift] += 1
        has_assignment[(nid, date)] = True

    def demand_of(date_iso: str) -> Dict[str, int]:
        d = dt.date.fromisoformat(date_iso)
        dflt = rules.get("demand_defaults", {})
        if d.weekday() == 6:
            picked = dflt.get("sunday", {})
        elif is_weekend(d):
            picked = dflt.get("saturday_holiday", {})
        else:
            picked = dflt.get("weekday", {})
        return {
            "day_min": int(picked.get("day_min", 0)),
            "day_max": int(picked.get("day_max", 9999)),
            "late": int(picked.get("late", 0)),
            "night": int(picked.get("night", 0)),
        }

    violations: List[str] = []
    suggestions: List[Dict[str, Any]] = []

    # Fill shortages first (LATE/NIGHT exact, DAY min)
    for date in all_days:
        dem = demand_of(date)
        # LATE
        diff_late = dem["late"] - per_day_counts[date]["LATE"]
        if diff_late != 0:
            if diff_late > 0:
                violations.append(f"{date} 遅番不足 {per_day_counts[date]['LATE']}/{dem['late']}")
                for nid, n in nurse_by_id.items():
                    if diff_late <= 0:
                        break
                    if has_assignment[(nid, date)]:
                        continue
                    if n.get("late_ok") is False:
                        continue
                    suggestions.append({"nurse_id": nid, "date": date, "shift": "LATE"})
                    per_day_counts[date]["LATE"] += 1
                    has_assignment[(nid, date)] = True
                    diff_late -= 1
            else:
                violations.append(f"{date} 遅番過多 {per_day_counts[date]['LATE']}/{dem['late']}")
        # NIGHT
        diff_night = dem["night"] - per_day_counts[date]["NIGHT"]
        if diff_night != 0:
            if diff_night > 0:
                violations.append(f"{date} 夜勤不足 {per_day_counts[date]['NIGHT']}/{dem['night']}")
                for nid, n in nurse_by_id.items():
                    if diff_night <= 0:
                        break
                    if has_assignment[(nid, date)]:
                        continue
                    if n.get("night_ok") is False:
                        continue
                    suggestions.append({"nurse_id": nid, "date": date, "shift": "NIGHT"})
                    per_day_counts[date]["NIGHT"] += 1
                    has_assignment[(nid, date)] = True
                    diff_night -= 1
            else:
                violations.append(f"{date} 夜勤過多 {per_day_counts[date]['NIGHT']}/{dem['night']}")
        # DAY min
        diff_day_min = dem["day_min"] - per_day_counts[date]["DAY"]
        if diff_day_min > 0:
            violations.append(f"{date} 日勤不足 {per_day_counts[date]['DAY']}/{dem['day_min']}")
            for nid, n in nurse_by_id.items():
                if diff_day_min <= 0:
                    break
                if has_assignment[(nid, date)]:
                    continue
                if n.get("day_ok") is False:
                    continue
                suggestions.append({"nurse_id": nid, "date": date, "shift": "DAY"})
                per_day_counts[date]["DAY"] += 1
                has_assignment[(nid, date)] = True
                diff_day_min -= 1
        # DAY max
        if per_day_counts[date]["DAY"] > dem["day_max"]:
            violations.append(f"{date} 日勤過多 {per_day_counts[date]['DAY']}/{dem['day_max']}")

    return {"violations": violations, "suggestions": suggestions}
