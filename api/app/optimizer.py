from __future__ import annotations

import calendar
import datetime as dt
from collections import Counter, defaultdict
from typing import Any, Callable, DefaultDict, Dict, Iterable, List, Literal, Optional, Tuple

from ortools.sat.python import cp_model

Shift = Literal["DAY", "LATE", "NIGHT", "OFF"]
WORK_SHIFTS: Tuple[Shift, ...] = ("DAY", "LATE", "NIGHT")
ALL_SHIFTS: Tuple[Shift, ...] = ("DAY", "LATE", "NIGHT", "OFF")
ValueCallback = Callable[[str, dt.date, Shift], int]


def days_in_month(year: int, month: int) -> List[dt.date]:
    _, last = calendar.monthrange(year, month)
    return [dt.date(year, month, d) for d in range(1, last + 1)]


def is_weekend(date_obj: dt.date) -> bool:
    return date_obj.weekday() >= 5


def is_weekend_or_holiday(date_obj: dt.date, holidays: set[dt.date]) -> bool:
    return is_weekend(date_obj) or date_obj in holidays


def week_key(date_obj: dt.date) -> Tuple[int, int]:
    iso = date_obj.isocalendar()
    return (iso.year, iso.week)


def _demand_for_day(rules: Dict[str, Any], date_obj: dt.date, holidays: set[dt.date]) -> Dict[str, int]:
    overrides = rules.get("demand", {})
    key = date_obj.isoformat()
    if key in overrides:
        picked = overrides[key]
    else:
        defaults = rules.get("demand_defaults", {})
        if date_obj in holidays:
            picked = defaults.get("saturday_holiday", {})
        elif date_obj.weekday() == 6:
            picked = defaults.get("sunday", {})
        elif is_weekend(date_obj):
            picked = defaults.get("saturday_holiday", {})
        else:
            picked = defaults.get("weekday", {})
    return {
        "day_min": int(picked.get("day_min", 0)),
        "day_max": int(picked.get("day_max", 9999)),
        "late": int(picked.get("late", 0)),
        "night": int(picked.get("night", 0)),
    }


def _prepare_merged_rules(
    nurse_ids: Iterable[str],
    nurse_by_id: Dict[str, Dict[str, Any]],
    person_rules: Dict[str, Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}
    for nid in nurse_ids:
        base = nurse_by_id[nid]
        pr = person_rules.get(nid, {})
        merged[nid] = {
            "night_min": pr.get("night_min"),
            "night_max": pr.get("night_max"),
            "week_max_days": pr.get("week_max_days", base.get("week_max_days")),
            "weekend_cap": pr.get("weekend_cap_per_month", base.get("weekend_cap")),
            "weekend_off": bool(pr.get("weekend_off")),
            "holiday_off": bool(pr.get("holiday_off")),
            "only_night": bool(pr.get("only_night")),
            "only_day": bool(pr.get("only_day")),
            "extra_holidays": int(pr.get("extra_holidays", 0) or 0),
            "month_quota_days": pr.get("month_quota_days"),
            "weekend_day_only": bool(pr.get("weekend_day_only")),
            "weekend_only_night": bool(pr.get("weekend_only_night")),
            "cannot_lead_night": bool(pr.get("cannot_lead_night")),
        }
        if merged[nid]["week_max_days"] is None and base.get("week_max_days") is not None:
            merged[nid]["week_max_days"] = base.get("week_max_days")
        if merged[nid]["weekend_cap"] is None and base.get("weekend_cap") is not None:
            merged[nid]["weekend_cap"] = base.get("weekend_cap")
        if merged[nid]["only_day"]:
            base["night_ok"] = False
            base["late_ok"] = False
        if merged[nid]["only_night"]:
            base["day_ok"] = False
            base["late_ok"] = False
    return merged


def _apply_fixed_assignments(
    model: cp_model.CpModel,
    x: Dict[Tuple[str, dt.date, Shift], cp_model.IntVar],
    fixed_assignments: Optional[List[Dict[str, Any]]],
    nurse_ids: Iterable[str],
    all_days: List[dt.date],
) -> Dict[Tuple[str, str], Shift]:
    locked_map: Dict[Tuple[str, str], Shift] = {}
    if not fixed_assignments:
        return locked_map
    day_lookup = {d.isoformat(): d for d in all_days}
    valid_nids = set(nurse_ids)
    for item in fixed_assignments:
        nid = str(item.get("nurse_id"))
        date_str = str(item.get("date"))
        shift = str(item.get("shift", "")).upper()
        if nid not in valid_nids or date_str not in day_lookup or shift not in ALL_SHIFTS:
            continue
        day = day_lookup[date_str]
        locked_map[(nid, date_str)] = shift  # type: ignore[assignment]
        model.Add(x[(nid, day, shift)] == 1)
        for other in ALL_SHIFTS:
            if other != shift:
                model.Add(x[(nid, day, other)] == 0)
    return locked_map


def _extract_schedule(nurse_ids: Iterable[str], all_days: List[dt.date], shifts: Iterable[Shift], value_cb: ValueCallback) -> List[Dict[str, Any]]:
    schedule: List[Dict[str, Any]] = []
    for nid in nurse_ids:
        for day in all_days:
            for shift in shifts:
                if value_cb(nid, day, shift):
                    schedule.append({
                        "nurse_id": nid,
                        "date": day.isoformat(),
                        "shift": shift,
                    })
                    break
    return schedule


def _candidate_pool_for_shortage(
    date_key: str,
    shift: Shift,
    assign_lookup: DefaultDict[str, Dict[str, Shift]],
    nurse_by_id: Dict[str, Dict[str, Any]],
    locked_map: Dict[Tuple[str, str], Shift],
    missing_team: Optional[str] = None,
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for nid, day_assignments in assign_lookup.items():
        current_shift = day_assignments.get(date_key, "OFF")
        nurse = nurse_by_id[nid]
        locked = (nid, date_key) in locked_map
        score = 0
        if shift == "DAY":
            if nurse.get("day_ok") is False:
                continue
            if current_shift == "OFF":
                score = 0
            elif current_shift == "LATE":
                score = 1
            elif current_shift == "DAY":
                continue
            else:
                score = 2
        elif shift == "LATE":
            if nurse.get("late_ok") is False:
                continue
            if current_shift == "OFF":
                score = 0
            elif current_shift == "DAY":
                score = 1
            elif current_shift == "LATE":
                continue
            else:
                score = 2
        else:  # NIGHT
            if nurse.get("night_ok") is False:
                continue
            if missing_team and nurse.get("team") != missing_team:
                continue
            if current_shift == "OFF":
                score = 0
            elif current_shift == "DAY":
                score = 1
            elif current_shift == "LATE":
                score = 2
            elif current_shift == "NIGHT":
                continue
            else:
                score = 3
        candidates.append({
            "nurse_id": nid,
            "current_shift": current_shift,
            "suggested_shift": shift,
            "locked": locked,
            "reason": f"{date_key} {shift} 不足補充候補",
            "score": (score, locked, nid),
        })
    candidates.sort(key=lambda c: c["score"])
    return candidates


def _candidate_pool_for_excess(
    date_key: str,
    shift: Shift,
    assign_lookup: DefaultDict[str, Dict[str, Shift]],
    nurse_by_id: Dict[str, Dict[str, Any]],
    locked_map: Dict[Tuple[str, str], Shift],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for nid, day_assignments in assign_lookup.items():
        current_shift = day_assignments.get(date_key)
        if current_shift != shift:
            continue
        locked = (nid, date_key) in locked_map
        candidates.append({
            "nurse_id": nid,
            "current_shift": current_shift,
            "suggested_shift": "OFF" if shift != "OFF" else "DAY",
            "locked": locked,
            "reason": f"{date_key} {shift} 過多調整候補",
            "score": (locked, nid),
        })
    candidates.sort(key=lambda c: c["score"])
    return candidates


def _analyze_schedule(
    schedule: List[Dict[str, Any]],
    nurses: List[Dict[str, Any]],
    rules: Dict[str, Any],
    merged_rules: Dict[str, Dict[str, Any]],
    all_days: List[dt.date],
    holidays: set[dt.date],
    nurse_by_id: Dict[str, Dict[str, Any]],
    locked_map: Dict[Tuple[str, str], Shift],
) -> Dict[str, Any]:
    per_day_assignments: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    assign_lookup: DefaultDict[str, Dict[str, Shift]] = defaultdict(dict)
    for entry in schedule:
        per_day_assignments[entry["date"]].append(entry)
        assign_lookup[entry["nurse_id"]][entry["date"]] = entry["shift"]  # type: ignore[index]

    per_day_summary: List[Dict[str, Any]] = []
    warnings: List[str] = []
    violations: List[Dict[str, Any]] = []
    violation_cells: List[Dict[str, Any]] = []
    recommendations: List[Dict[str, Any]] = []

    for day in all_days:
        key = day.isoformat()
        day_items = per_day_assignments[key]
        counts = Counter(item["shift"] for item in day_items)
        dem = _demand_for_day(rules, day, holidays)
        per_day_summary.append(
            {
                "date": key,
                "weekday": day.strftime("%a"),
                "is_weekend": is_weekend(day),
                "is_holiday": day in holidays,
                "requirements": dem,
                "filled": {
                    "DAY": counts.get("DAY", 0),
                    "LATE": counts.get("LATE", 0),
                    "NIGHT": counts.get("NIGHT", 0),
                },
            }
        )

        if counts.get("DAY", 0) < dem["day_min"]:
            deficit = dem["day_min"] - counts.get("DAY", 0)
            violation = {
                "date": key,
                "shift": "DAY",
                "kind": "shortage",
                "difference": -deficit,
                "actual": counts.get("DAY", 0),
                "required_min": dem["day_min"],
                "required_max": dem["day_max"],
                "message": f"{key} 日勤不足 {deficit}名 ({counts.get('DAY',0)} / {dem['day_min']})",
            }
            violations.append(violation)
            violation_cells.append({"date": key, "shift": "DAY", "kind": "shortage"})
            candidates = _candidate_pool_for_shortage(key, "DAY", assign_lookup, nurse_by_id, locked_map)
            if candidates:
                recommendations.append({
                    "date": key,
                    "shift": "DAY",
                    "kind": "shortage",
                    "difference": -deficit,
                    "suggestions": [
                        {k: v for k, v in cand.items() if k != "score"} for cand in candidates[: max(3, deficit)]
                    ],
                })
        if counts.get("DAY", 0) > dem["day_max"]:
            excess = counts.get("DAY", 0) - dem["day_max"]
            violation = {
                "date": key,
                "shift": "DAY",
                "kind": "excess",
                "difference": excess,
                "actual": counts.get("DAY", 0),
                "required_min": dem["day_min"],
                "required_max": dem["day_max"],
                "message": f"{key} 日勤過多 {excess}名 ({counts.get('DAY',0)} / {dem['day_max']})",
            }
            violations.append(violation)
            violation_cells.append({"date": key, "shift": "DAY", "kind": "excess"})
            candidates = _candidate_pool_for_excess(key, "DAY", assign_lookup, nurse_by_id, locked_map)
            if candidates:
                recommendations.append({
                    "date": key,
                    "shift": "DAY",
                    "kind": "excess",
                    "difference": excess,
                    "suggestions": [
                        {k: v for k, v in cand.items() if k != "score"} for cand in candidates[: max(3, excess)]
                    ],
                })
        if counts.get("LATE", 0) != dem["late"]:
            diff = counts.get("LATE", 0) - dem["late"]
            violation = {
                "date": key,
                "shift": "LATE",
                "kind": "shortage" if diff < 0 else "excess",
                "difference": diff,
                "actual": counts.get("LATE", 0),
                "required": dem["late"],
                "message": f"{key} 遅番が想定と異なります ({counts.get('LATE',0)} / {dem['late']})",
            }
            violations.append(violation)
            violation_cells.append({"date": key, "shift": "LATE", "kind": violation["kind"]})
            if diff < 0:
                candidates = _candidate_pool_for_shortage(key, "LATE", assign_lookup, nurse_by_id, locked_map)
            else:
                candidates = _candidate_pool_for_excess(key, "LATE", assign_lookup, nurse_by_id, locked_map)
            if candidates:
                recommendations.append({
                    "date": key,
                    "shift": "LATE",
                    "kind": violation["kind"],
                    "difference": diff,
                    "suggestions": [
                        {k: v for k, v in cand.items() if k != "score"} for cand in candidates[:3]
                    ],
                })
        if counts.get("NIGHT", 0) != dem["night"]:
            diff = counts.get("NIGHT", 0) - dem["night"]
            violation = {
                "date": key,
                "shift": "NIGHT",
                "kind": "shortage" if diff < 0 else "excess",
                "difference": diff,
                "actual": counts.get("NIGHT", 0),
                "required": dem["night"],
                "message": f"{key} 夜勤が想定と異なります ({counts.get('NIGHT',0)} / {dem['night']})",
            }
            violations.append(violation)
            violation_cells.append({"date": key, "shift": "NIGHT", "kind": violation["kind"]})
            missing_teams: List[str] = []
            if diff < 0:
                team_counts = Counter(
                    nurse_by_id[item["nurse_id"]]["team"] for item in day_items if item["shift"] == "NIGHT"
                )
                expected = {"A": 1, "B": 1, "ER": 1}
                for team, need in expected.items():
                    if team_counts.get(team, 0) < need:
                        missing_teams.extend([team] * (need - team_counts.get(team, 0)))
                if missing_teams:
                    violation["missing_teams"] = missing_teams
                cand_list: List[Dict[str, Any]] = []
                for miss_team in missing_teams or [None]:
                    cand_list.extend(
                        _candidate_pool_for_shortage(key, "NIGHT", assign_lookup, nurse_by_id, locked_map, miss_team)
                    )
                if cand_list:
                    recommendations.append({
                        "date": key,
                        "shift": "NIGHT",
                        "kind": violation["kind"],
                        "difference": diff,
                        "suggestions": [
                            {k: v for k, v in cand.items() if k != "score"}
                            for cand in cand_list[: max(3, abs(diff))]
                        ],
                    })
            else:
                candidates = _candidate_pool_for_excess(key, "NIGHT", assign_lookup, nurse_by_id, locked_map)
                if candidates:
                    recommendations.append({
                        "date": key,
                        "shift": "NIGHT",
                        "kind": violation["kind"],
                        "difference": diff,
                        "suggestions": [
                            {k: v for k, v in cand.items() if k != "score"} for cand in candidates[:3]
                        ],
                    })

    nurse_ids = [str(n["id"]) for n in nurses]
    per_nurse_summary: List[Dict[str, Any]] = []
    for nid in nurse_ids:
        meta = nurse_by_id[nid]
        rule = merged_rules[nid]
        counts = Counter(assign_lookup[nid].values())
        weekend_days = sum(
            1
            for day in all_days
            if assign_lookup[nid].get(day.isoformat()) in WORK_SHIFTS
            and is_weekend_or_holiday(day, holidays)
        )
        night_count = counts.get("NIGHT", 0)
        work_days = sum(counts.get(shift, 0) for shift in WORK_SHIFTS)
        per_nurse_summary.append(
            {
                "nurse_id": nid,
                "name": meta.get("name"),
                "team": meta.get("team"),
                "counts": {
                    "DAY": counts.get("DAY", 0),
                    "LATE": counts.get("LATE", 0),
                    "NIGHT": night_count,
                    "OFF": counts.get("OFF", 0),
                },
                "weekend_work": weekend_days,
                "total_work_days": work_days,
                "rule": {
                    "night_min": rule.get("night_min"),
                    "night_max": rule.get("night_max"),
                    "week_max_days": rule.get("week_max_days"),
                    "weekend_cap": rule.get("weekend_cap"),
                    "month_quota_days": rule.get("month_quota_days"),
                },
            }
        )
        if rule.get("night_min") is not None and night_count == rule.get("night_min"):
            warnings.append(f"看護師 {nid} の夜勤回数が下限ぴったりです")
        if rule.get("night_max") is not None and night_count == rule.get("night_max"):
            warnings.append(f"看護師 {nid} の夜勤回数が上限ぴったりです")
        if rule.get("weekend_cap") is not None and weekend_days == rule.get("weekend_cap"):
            warnings.append(f"看護師 {nid} の土日祝勤務が上限に達しています")

    return {
        "per_day": per_day_summary,
        "per_nurse": per_nurse_summary,
        "warnings": warnings,
        "violations": violations,
        "violation_cells": violation_cells,
        "recommendations": recommendations,
    }


def build_schedule(
    nurses: List[Dict[str, Any]],
    rules: Dict[str, Any],
    *,
    fixed_assignments: Optional[List[Dict[str, Any]]] = None,
    alternatives: int = 1,
) -> Dict[str, Any]:
    year = int(rules["year"])
    month = int(rules["month"])
    holidays = {dt.date.fromisoformat(x) for x in rules.get("holidays", [])}
    leader_weekend_candidates = set(rules.get("leader_requirement", {}).get("weekend_holiday", []))
    forbidden_night_pairs = [tuple(pair) for pair in rules.get("forbidden_pairs", {}).get("night", [])]

    all_days = days_in_month(year, month)
    nurse_ids = [str(n["id"]) for n in nurses]
    nurses_mutable = [{**n} for n in nurses]
    nurse_by_id = {str(n["id"]): nurses_mutable[idx] for idx, n in enumerate(nurses_mutable)}
    person_rules = {str(k): v for k, v in rules.get("person_rules", {}).items()}
    merged_rules = _prepare_merged_rules(nurse_ids, nurse_by_id, person_rules)

    model = cp_model.CpModel()
    x: Dict[Tuple[str, dt.date, Shift], cp_model.IntVar] = {}
    for nid in nurse_ids:
        for day in all_days:
            for shift in ALL_SHIFTS:
                x[(nid, day, shift)] = model.NewBoolVar(f"x_{nid}_{day.isoformat()}_{shift}")

    for nid in nurse_ids:
        for day in all_days:
            model.Add(sum(x[(nid, day, shift)] for shift in ALL_SHIFTS) == 1)

    locked_map = _apply_fixed_assignments(model, x, fixed_assignments, nurse_ids, all_days)

    week_to_days: DefaultDict[Tuple[int, int], List[dt.date]] = defaultdict(list)
    for day in all_days:
        week_to_days[week_key(day)].append(day)
    weekend_dates = [day for day in all_days if is_weekend_or_holiday(day, holidays)]
    holiday_dates = [day for day in all_days if day in holidays]

    for day in all_days:
        dem = _demand_for_day(rules, day, holidays)
        model.Add(sum(x[(nid, day, "DAY")] for nid in nurse_ids) >= dem["day_min"])
        model.Add(sum(x[(nid, day, "DAY")] for nid in nurse_ids) <= dem["day_max"])
        model.Add(sum(x[(nid, day, "LATE")] for nid in nurse_ids) == dem["late"])
        model.Add(sum(x[(nid, day, "NIGHT")] for nid in nurse_ids) == dem["night"])

        night_A = [x[(nid, day, "NIGHT")] for nid in nurse_ids if nurse_by_id[nid]["team"] == "A"]
        night_B = [x[(nid, day, "NIGHT")] for nid in nurse_ids if nurse_by_id[nid]["team"] == "B"]
        night_ER = [x[(nid, day, "NIGHT")] for nid in nurse_ids if nurse_by_id[nid]["team"] == "ER"]
        if night_A:
            model.Add(sum(night_A) == 1)
        if night_B:
            model.Add(sum(night_B) == 1)
        if night_ER:
            model.Add(sum(night_ER) == 1)

        if is_weekend(day) or (day in holidays):
            model.Add(
                sum(x[(nid, day, "DAY")] for nid in nurse_ids if nid in leader_weekend_candidates) >= 1
            )

        for a, b in forbidden_night_pairs:
            if a in nurse_ids and b in nurse_ids:
                model.Add(x[(a, day, "NIGHT")] + x[(b, day, "NIGHT")] <= 1)

        model.Add(
            sum(
                x[(nid, day, "NIGHT")] for nid in nurse_ids
                if nurse_by_id[nid].get("leader_ok") and not merged_rules[nid].get("cannot_lead_night")
            )
            >= 1
        )

    for nid in nurse_ids:
        for idx in range(len(all_days) - 1):
            current_day = all_days[idx]
            next_day = all_days[idx + 1]
            model.Add(x[(nid, current_day, "NIGHT")] + x[(nid, next_day, "DAY")] <= 1)
            model.Add(x[(nid, current_day, "NIGHT")] + x[(nid, next_day, "LATE")] <= 1)

    for nid in nurse_ids:
        rule = merged_rules[nid]
        off_target = 9 + int(rule.get("extra_holidays", 0))
        model.Add(sum(x[(nid, day, "OFF")] for day in all_days) >= off_target)

    for nid in nurse_ids:
        base = nurse_by_id[nid]
        if base.get("day_ok") is False:
            for day in all_days:
                model.Add(x[(nid, day, "DAY")] == 0)
        if base.get("late_ok") is False:
            for day in all_days:
                model.Add(x[(nid, day, "LATE")] == 0)
        if base.get("night_ok") is False:
            for day in all_days:
                model.Add(x[(nid, day, "NIGHT")] == 0)

    for nid in nurse_ids:
        pr = person_rules.get(nid, {})
        rule_state = merged_rules[nid]
        night_min = pr.get("night_min")
        night_max = pr.get("night_max")
        if night_min is not None:
            model.Add(sum(x[(nid, day, "NIGHT")] for day in all_days) >= int(night_min))
        if night_max is not None:
            model.Add(sum(x[(nid, day, "NIGHT")] for day in all_days) <= int(night_max))
        if pr.get("exclude_day_on_weekend"):
            for day in all_days:
                if is_weekend(day) or (day in holidays):
                    model.Add(x[(nid, day, "DAY")] == 0)
        if pr.get("only_night"):
            for day in all_days:
                model.Add(x[(nid, day, "DAY")] == 0)
                model.Add(x[(nid, day, "LATE")] == 0)
                model.Add(x[(nid, day, "OFF")] + x[(nid, day, "NIGHT")] == 1)
        if pr.get("only_day"):
            for day in all_days:
                model.Add(x[(nid, day, "NIGHT")] == 0)
        if pr.get("month_quota_days") is not None:
            quota = int(pr["month_quota_days"])
            model.Add(sum(x[(nid, day, "DAY")] for day in all_days) == quota)
        week_cap = pr.get("week_max_days") or rule_state.get("week_max_days")
        if week_cap is not None:
            cap = int(week_cap)
            for day_list in week_to_days.values():
                model.Add(sum(x[(nid, d, s)] for d in day_list for s in WORK_SHIFTS) <= cap)
        weekend_cap = rule_state.get("weekend_cap")
        if weekend_cap is not None:
            cap = int(weekend_cap)
            model.Add(sum(x[(nid, d, s)] for d in weekend_dates for s in WORK_SHIFTS) <= cap)
        if pr.get("weekend_off"):
            for day in weekend_dates:
                model.Add(x[(nid, day, "OFF")] == 1)
        if pr.get("holiday_off"):
            for day in holiday_dates:
                model.Add(x[(nid, day, "OFF")] == 1)
        if pr.get("weekend_day_only"):
            for day in all_days:
                if is_weekend_or_holiday(day, holidays):
                    model.Add(x[(nid, day, "LATE")] == 0)
                    model.Add(x[(nid, day, "NIGHT")] == 0)
                else:
                    model.Add(x[(nid, day, "OFF")] == 1)
        if pr.get("weekend_only_night"):
            for day in all_days:
                if not is_weekend_or_holiday(day, holidays):
                    model.Add(x[(nid, day, "NIGHT")] == 0)
                    model.Add(x[(nid, day, "OFF")] == 1)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 30.0

    nurses_meta = [
        {
            "id": nid,
            "name": nurse_by_id[nid].get("name"),
            "team": nurse_by_id[nid].get("team"),
            "leader_ok": bool(nurse_by_id[nid].get("leader_ok")),
        }
        for nid in nurse_ids
    ]

    def assemble_solution(schedule: List[Dict[str, Any]], index: int) -> Dict[str, Any]:
        analysis = _analyze_schedule(schedule, nurses_mutable, rules, merged_rules, all_days, holidays, nurse_by_id, locked_map)
        plan_label = f"案{index + 1}"
        return {
            "plan_id": f"plan-{index + 1}",
            "label": plan_label,
            "assignments": schedule,
            "summary": {
                "per_day": analysis["per_day"],
                "per_nurse": analysis["per_nurse"],
            },
            "warnings": analysis["warnings"],
            "violations": analysis["violations"],
            "violation_cells": analysis["violation_cells"],
            "recommendations": analysis["recommendations"],
        }

    solutions: List[Dict[str, Any]] = []

    if alternatives <= 1:
        status = solver.Solve(model)
        if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            return {
                "status": "INFEASIBLE",
                "message": "No feasible solution found",
                "suggestions": suggest_relaxations(nurses, rules),
            }
        schedule = _extract_schedule(
            nurse_ids,
            all_days,
            ALL_SHIFTS,
            lambda nid, day, shift: solver.Value(x[(nid, day, shift)]) == 1,
        )
        solutions.append(assemble_solution(schedule, 0))
    else:
        limit = max(1, alternatives)

        class Collector(cp_model.CpSolverSolutionCallback):
            def __init__(self) -> None:
                super().__init__()
                self.collected: List[Dict[str, Any]] = []

            def OnSolutionCallback(self) -> None:  # type: ignore[override]
                schedule = _extract_schedule(
                    nurse_ids,
                    all_days,
                    ALL_SHIFTS,
                    lambda nid, day, shift: self.Value(x[(nid, day, shift)]) == 1,
                )
                self.collected.append(assemble_solution(schedule, len(self.collected)))
                if len(self.collected) >= limit:
                    self.StopSearch()

        collector = Collector()
        solver.parameters.enumerate_all_solutions = True
        status = solver.SearchForAllSolutions(model, collector)
        if not collector.collected:
            return {
                "status": "INFEASIBLE",
                "message": "No feasible solution found",
                "suggestions": suggest_relaxations(nurses, rules),
            }
        solutions.extend(collector.collected)

    primary = solutions[0]
    result = {
        "status": "OK",
        "year": year,
        "month": month,
        "days": [day.isoformat() for day in all_days],
        "nurses": nurses_meta,
        "assignments": primary["assignments"],
        "summary": primary["summary"],
        "warnings": primary["warnings"],
        "violations": primary["violations"],
        "violation_cells": primary["violation_cells"],
        "recommendations": primary["recommendations"],
        "solutions": solutions,
        "alternatives_returned": len(solutions),
    }
    if fixed_assignments:
        result["locked_assignments"] = fixed_assignments
    return result


def suggest_relaxations(nurses: List[Dict[str, Any]], rules: Dict[str, Any]) -> List[Dict[str, Any]]:
    year = int(rules["year"])
    month = int(rules["month"])
    holidays = {dt.date.fromisoformat(x) for x in rules.get("holidays", [])}
    all_days = days_in_month(year, month)

    def demand_of(date_obj: dt.date) -> Dict[str, int]:
        defaults = rules.get("demand_defaults", {})
        if date_obj in holidays:
            target = defaults.get("saturday_holiday", {})
        elif date_obj.weekday() == 6:
            target = defaults.get("sunday", {})
        elif is_weekend(date_obj):
            target = defaults.get("saturday_holiday", {})
        else:
            target = defaults.get("weekday", {})
        return {
            "day_min": int(target.get("day_min", 0)),
            "day_max": int(target.get("day_max", 9999)),
            "late": int(target.get("late", 0)),
            "night": int(target.get("night", 0)),
        }

    day_capable_counts: Dict[str, int] = {}
    for day in all_days:
        count = 0
        for nurse in nurses:
            if nurse.get("day_ok") is not False:
                count += 1
        day_capable_counts[day.isoformat()] = count

    lower_days: List[str] = []
    for day in all_days:
        dem = demand_of(day)
        if day_capable_counts[day.isoformat()] < dem["day_min"]:
            lower_days.append(day.isoformat())

    suggestions: List[Dict[str, Any]] = []
    if lower_days:
        suggestions.append({
            "type": "relax_day_min",
            "amount": 1,
            "dates": lower_days[:7],
            "reason": "日勤の必要最小人数が供給可能人数を上回っています",
        })

    suggestions.append({
        "type": "allow_weekend_day_without_leader",
        "scope": "weekend_holiday",
        "reason": "土日祝で日勤のリーダー確保が困難な場合の暫定緩和",
    })

    suggestions.append({
        "type": "increase_off_quota_for_noncritical",
        "reason": "連勤・夜勤制約のトレードオフ調整の候補",
    })

    fpairs = rules.get("forbidden_pairs", {}).get("night", [])
    if fpairs:
        suggestions.append({
            "type": "exception_forbidden_pair_on_specific_day",
            "pair": fpairs[0],
            "dates": [],
            "reason": "夜勤構成が成立しない日に限定した例外候補",
        })

    return suggestions


def recheck_assignments(
    assignments: List[Dict[str, Any]],
    nurses: List[Dict[str, Any]],
    rules: Dict[str, Any],
) -> Dict[str, Any]:
    year = int(rules["year"])
    month = int(rules["month"])
    holidays = {dt.date.fromisoformat(x) for x in rules.get("holidays", [])}
    all_days = {day.isoformat(): day for day in days_in_month(year, month)}

    nurses_mutable = [{**n} for n in nurses]
    nurse_by_id = {str(n["id"]): nurses_mutable[idx] for idx, n in enumerate(nurses_mutable)}
    nurse_ids = set(nurse_by_id.keys())
    person_rules = {str(k): v for k, v in rules.get("person_rules", {}).items()}
    merged_rules = _prepare_merged_rules(nurse_ids, nurse_by_id, person_rules)

    violations_strings: List[str] = []
    seen: DefaultDict[Tuple[str, str], int] = defaultdict(int)
    for entry in assignments:
        nid = str(entry.get("nurse_id"))
        date_key = str(entry.get("date"))
        shift = entry.get("shift")
        if nid not in nurse_by_id:
            violations_strings.append(f"unknown nurse_id {nid}")
            continue
        if date_key not in all_days:
            violations_strings.append(f"date out of month {date_key}")
            continue
        key = (nid, date_key)
        seen[key] += 1
        if seen[key] > 1:
            violations_strings.append(f"multiple shifts in a day for nurse {nid} at {date_key}")
        nurse = nurse_by_id[nid]
        if shift == "DAY" and nurse.get("day_ok") is False:
            violations_strings.append(f"nurse {nid} cannot take DAY {date_key}")
        if shift == "LATE" and nurse.get("late_ok") is False:
            violations_strings.append(f"nurse {nid} cannot take LATE {date_key}")
        if shift == "NIGHT" and nurse.get("night_ok") is False:
            violations_strings.append(f"nurse {nid} cannot take NIGHT {date_key}")

    for nid in nurse_by_id:
        for date_key in all_days:
            if (nid, date_key) not in seen:
                violations_strings.append(f"nurse {nid} missing assignment at {date_key}")

    analysis = _analyze_schedule(
        assignments,
        nurses_mutable,
        rules,
        merged_rules,
        list(all_days.values()),
        holidays,
        nurse_by_id,
        locked_map={},
    )

    ok = len(violations_strings) == 0 and not analysis["violations"]
    return {
        "ok": ok,
        "violations": violations_strings,
        "summary": {
            "per_day": analysis["per_day"],
            "per_nurse": analysis["per_nurse"],
        },
        "warnings": analysis["warnings"],
        "violations_detail": analysis["violations"],
        "violation_cells": analysis["violation_cells"],
        "recommendations": analysis["recommendations"],
    }


def to_csv(assignments: List[Dict[str, Any]]) -> str:
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["nurse_id", "date", "shift"])
    for entry in assignments:
        writer.writerow([entry.get("nurse_id"), entry.get("date"), entry.get("shift")])
    return output.getvalue()
