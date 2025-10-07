from __future__ import annotations

import json
import os
import pathlib
import shutil
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response

from app.optimizer import build_schedule, recheck_assignments, to_csv
from app.pdf import assignments_to_pdf
from app.shiftmd_parser import parse_shift_md
from app.validation import load_and_validate

app = FastAPI(title="Nurse Shift Optimizer", version="0.2.0")

origins_str = os.environ.get("ALLOWED_ORIGINS", "*")
if origins_str == "*":
    allowed_origins = ["*"]
else:
    # カンマ区切りで複数のオリジンを許可
    allowed_origins = [o.strip() for o in origins_str.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True if allowed_origins != ["*"] else False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _save_upload(upload: UploadFile, target_path: pathlib.Path) -> None:
    with open(target_path, "wb") as handle:
        shutil.copyfileobj(upload.file, handle)


def _load_json_form_field(raw: Optional[str]) -> Optional[Any]:
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid JSON payload: {exc}") from exc


@app.post("/optimize")
async def optimize(
    nurses: UploadFile = File(...),
    rules: UploadFile = File(...),
    alternatives: int = Form(1),
):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            npath = tmp / "nurses.csv"
            rpath = tmp / "rules.json"
            _save_upload(nurses, npath)
            _save_upload(rules, rpath)

            nurses_data, rules_data = load_and_validate(
                npath,
                rpath,
                pathlib.Path(__file__).parents[2] / "packages/schemas",
            )
            alt = max(1, int(alternatives))
            result = build_schedule(nurses_data, rules_data, alternatives=alt)
            if result.get("status") != "OK":
                raise HTTPException(status_code=422, detail=result)
            return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/optimize/md")
async def optimize_from_md(
    md: UploadFile = File(...),
    year: int = Form(2025),
    month: int = Form(10),
    alternatives: int = Form(1),
):
    try:
        text = (await md.read()).decode("utf-8")
        nurses, rules = parse_shift_md(text, year=year, month=month)
        alt = max(1, int(alternatives))
        result = build_schedule(nurses, rules, alternatives=alt)
        if result.get("status") != "OK":
            raise HTTPException(status_code=422, detail=result)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/optimize/default-md")
async def optimize_default_md(
    year: int = 2025,
    month: int = 10,
    alternatives: int = 1,
):
    try:
        md_path_env = os.environ.get("SHIFT_MD_PATH")
        md_path = pathlib.Path(md_path_env) if md_path_env else pathlib.Path(__file__).parents[2] / "shift.md"
        if not md_path.exists():
            raise HTTPException(status_code=404, detail=f"shift.md not found at {md_path}")
        text = md_path.read_text(encoding="utf-8")
        nurses, rules = parse_shift_md(text, year=year, month=month)
        alt = max(1, int(alternatives))
        result = build_schedule(nurses, rules, alternatives=alt)
        if result.get("status") != "OK":
            raise HTTPException(status_code=422, detail=result)
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/optimize/with-fixed")
async def optimize_with_fixed(
    nurses: UploadFile = File(...),
    rules: UploadFile = File(...),
    fixed_assignments: Optional[str] = Form(None),
    current_assignments: Optional[str] = Form(None),
    alternatives: int = Form(1),
):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            npath = tmp / "nurses.csv"
            rpath = tmp / "rules.json"
            _save_upload(nurses, npath)
            _save_upload(rules, rpath)

            nurses_data, rules_data = load_and_validate(
                npath,
                rpath,
                pathlib.Path(__file__).parents[2] / "packages/schemas",
            )

            fixed_payload_raw = _load_json_form_field(fixed_assignments)
            if isinstance(fixed_payload_raw, dict):
                fixed_payload = fixed_payload_raw.get("fixed") or fixed_payload_raw.get("assignments") or []
            elif isinstance(fixed_payload_raw, list):
                fixed_payload = fixed_payload_raw
            elif fixed_payload_raw is None:
                fixed_payload = None
            else:
                raise HTTPException(status_code=400, detail="fixed_assignments must be JSON list or object")

            alt = max(1, int(alternatives))
            result = build_schedule(
                nurses_data,
                rules_data,
                fixed_assignments=fixed_payload,
                alternatives=alt,
            )

            current_payload_raw = _load_json_form_field(current_assignments)
            if result.get("status") != "OK" and current_payload_raw is not None:
                if isinstance(current_payload_raw, dict):
                    assignments_payload = current_payload_raw.get("assignments")
                else:
                    assignments_payload = current_payload_raw
                if isinstance(assignments_payload, list):
                    analysis = recheck_assignments(assignments_payload, nurses_data, rules_data)
                    result["analysis"] = analysis
            return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/recheck")
async def recheck(
    nurses: UploadFile = File(...),
    rules: UploadFile = File(...),
    assignments: UploadFile = File(...),
):
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = pathlib.Path(tmpdir)
            npath = tmp / "nurses.csv"
            rpath = tmp / "rules.json"
            apath = tmp / "assignments.json"
            _save_upload(nurses, npath)
            _save_upload(rules, rpath)
            _save_upload(assignments, apath)

            nurses_data, rules_data = load_and_validate(
                npath,
                rpath,
                pathlib.Path(__file__).parents[2] / "packages/schemas",
            )
            with open(apath, "r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if not isinstance(payload, dict) or "assignments" not in payload:
                raise HTTPException(status_code=400, detail="assignments.json must contain {'assignments': [...]} ")
            return recheck_assignments(payload["assignments"], nurses_data, rules_data)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/export/csv", response_class=PlainTextResponse)
async def export_csv(body: Dict[str, Any] = Body(...)):
    try:
        if "assignments" not in body:
            raise HTTPException(status_code=400, detail="Body must contain assignments")
        csv_text = to_csv(body["assignments"])
        return PlainTextResponse(content=csv_text, media_type="text/csv")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/export/pdf")
async def export_pdf(body: Dict[str, Any] = Body(...)):
    try:
        if "assignments" not in body:
            raise HTTPException(status_code=400, detail="Body must contain assignments")
        pdf_bytes = assignments_to_pdf(
            body["assignments"],
            nurses=body.get("nurses"),
            days=body.get("days"),
            summary=body.get("summary"),
            warnings=body.get("warnings"),
        )
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=assignments.pdf"},
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/recommend")
async def recommend(body: Dict[str, Any] = Body(...)):
    try:
        assignments = body.get("assignments")
        if not isinstance(assignments, list):
            raise HTTPException(status_code=400, detail="assignments must be provided as a list")
        year = int(body.get("year") or 2025)
        month = int(body.get("month") or 10)
        md_path_env = os.environ.get("SHIFT_MD_PATH")
        md_path = pathlib.Path(md_path_env) if md_path_env else pathlib.Path(__file__).parents[2] / "shift.md"
        if not md_path.exists():
            raise HTTPException(status_code=404, detail=f"shift.md not found at {md_path}")
        text = md_path.read_text(encoding="utf-8")
        nurses, rules = parse_shift_md(text, year=year, month=month)
        return recheck_assignments(assignments, nurses, rules)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/reoptimize")
async def reoptimize(body: Dict[str, Any] = Body(...)):
    try:
        assignments = body.get("assignments")
        fixed = body.get("fixed") or body.get("locks") or []
        year = int(body.get("year") or 2025)
        month = int(body.get("month") or 10)
        alt = max(1, int(body.get("alternatives") or 1))

        md_path_env = os.environ.get("SHIFT_MD_PATH")
        md_path = pathlib.Path(md_path_env) if md_path_env else pathlib.Path(__file__).parents[2] / "shift.md"
        if not md_path.exists():
            raise HTTPException(status_code=404, detail=f"shift.md not found at {md_path}")
        text = md_path.read_text(encoding="utf-8")
        nurses, rules = parse_shift_md(text, year=year, month=month)

        if not isinstance(fixed, list):
            raise HTTPException(status_code=400, detail="fixed must be a list of assignments")

        result = build_schedule(nurses, rules, fixed_assignments=fixed, alternatives=alt)
        if result.get("status") != "OK" and isinstance(assignments, list):
            analysis = recheck_assignments(assignments, nurses, rules)
            result["analysis"] = analysis
        return result
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
