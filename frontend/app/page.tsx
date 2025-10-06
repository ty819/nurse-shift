"use client";

import { useMemo, useState } from "react";
import styles from "./page.module.css";

type Shift = "DAY" | "LATE" | "NIGHT" | "OFF";

type Assignment = { nurse_id: string; date: string; shift: Shift };

type NurseMeta = { id: string; name?: string; team?: string; leader_ok?: boolean };

type ViolationCell = { date: string; shift: Shift; kind: "shortage" | "excess" };

type Violation = {
  date: string;
  shift: Shift;
  kind: "shortage" | "excess";
  difference?: number;
  actual?: number;
  required_min?: number;
  required_max?: number;
  required?: number;
  message?: string;
};

type Recommendation = {
  date: string;
  shift: Shift;
  kind: string;
  difference?: number;
  suggestions?: Array<{
    nurse_id: string;
    current_shift: Shift;
    suggested_shift: Shift;
    locked?: boolean;
    reason?: string;
  }>;
};

type ApiSolution = {
  plan_id: string;
  label: string;
  assignments: Assignment[];
  summary: {
    per_day: Array<{
      date: string;
      weekday: string;
      is_weekend: boolean;
      is_holiday: boolean;
      requirements: Record<string, number>;
      filled: Record<string, number>;
    }>;
    per_nurse: Array<{
      nurse_id: string;
      name?: string;
      team?: string;
      counts: Record<Shift, number>;
      weekend_work?: number;
      total_work_days?: number;
      rule?: Record<string, any>;
    }>;
  };
  warnings?: string[];
  violations?: Violation[];
  violation_cells?: ViolationCell[];
  recommendations?: Recommendation[];
};

type ApiOptimizeResponse = {
  status: string;
  year: number;
  month: number;
  days: string[];
  nurses: NurseMeta[];
  assignments: Assignment[];
  summary: ApiSolution["summary"];
  warnings?: string[];
  violations?: Violation[];
  violation_cells?: ViolationCell[];
  recommendations?: Recommendation[];
  solutions?: ApiSolution[];
  alternatives_returned?: number;
};

type Grid = Record<string, Record<string, Shift>>;

const SHIFT_LABELS: Record<Shift, string> = {
  DAY: "日勤",
  LATE: "遅番",
  NIGHT: "夜勤",
  OFF: "休",
};

const SHIFT_OPTIONS: Shift[] = ["DAY", "LATE", "NIGHT", "OFF"];

const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "";

function buildGridFromAssignments(assignments: Assignment[], days: string[], nurses: NurseMeta[]): Grid {
  const base: Grid = {};
  for (const nurse of nurses) {
    base[nurse.id] = Object.fromEntries(days.map(day => [day, "OFF" as Shift]));
  }
  for (const assignment of assignments) {
    if (!base[assignment.nurse_id]) {
      base[assignment.nurse_id] = Object.fromEntries(days.map(day => [day, "OFF" as Shift]));
    }
    base[assignment.nurse_id][assignment.date] = assignment.shift;
  }
  return base;
}

function gridToAssignments(grid: Grid, days: string[], nurses: NurseMeta[]): Assignment[] {
  const rows: Assignment[] = [];
  for (const nurse of nurses) {
    const nid = nurse.id;
    for (const day of days) {
      rows.push({ nurse_id: nid, date: day, shift: grid[nid]?.[day] ?? "OFF" });
    }
  }
  return rows;
}

async function downloadBlob(res: Response, filename: string) {
  if (!res.ok) {
    const detail = await res.json().catch(() => undefined);
    const message = detail?.detail ? JSON.stringify(detail.detail) : res.statusText;
    throw new Error(message || "リクエストに失敗しました");
  }
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function Page() {
  const [alternatives, setAlternatives] = useState<number>(3);
  const [resultMeta, setResultMeta] = useState<{ year: number; month: number; days: string[]; nurses: NurseMeta[] } | null>(null);
  const [solutions, setSolutions] = useState<ApiSolution[]>([]);
  const [selectedSolutionIndex, setSelectedSolutionIndex] = useState<number>(0);
  const [grid, setGrid] = useState<Grid>({});
  const [baseGrid, setBaseGrid] = useState<Grid>({});
  const [lockedCells, setLockedCells] = useState<Record<string, Shift>>({});
  const [violations, setViolations] = useState<Violation[]>([]);
  const [violationCells, setViolationCells] = useState<ViolationCell[]>([]);
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [warnings, setWarnings] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(false);

  const monthInputDefault = useMemo(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, "0")}`;
  }, []);
  const [selectedMonth, setSelectedMonth] = useState<string>(monthInputDefault);

  const hasManualLocks = useMemo(() => Object.keys(lockedCells).length > 0, [lockedCells]);

  const manualPayload = useMemo(() => {
    if (!resultMeta) return "";
    return JSON.stringify({ assignments: gridToAssignments(grid, resultMeta.days, resultMeta.nurses) }, null, 2);
  }, [grid, resultMeta]);

  const violationMap = useMemo(() => {
    const map = new Map<string, ViolationCell>();
    violationCells?.forEach(cell => {
      map.set(`${cell.date}|${cell.shift}`, cell);
    });
    return map;
  }, [violationCells]);

  const recommendationSet = useMemo(() => {
    const set = new Set<string>();
    recommendations?.forEach(rec => {
      rec.suggestions?.forEach(s => {
        set.add(`${s.nurse_id}|${rec.date}`);
      });
    });
    return set;
  }, [recommendations]);

  const currentSolution = solutions[selectedSolutionIndex];

  function getDayHeaderClass(dayIso: string): string {
    const summaryDay = currentSolution?.summary.per_day.find(d => d.date === dayIso);
    const dateObj = new Date(dayIso);
    const weekday = dateObj.getDay();
    if (summaryDay?.is_holiday || weekday === 0) return styles.dayHeaderSunday;
    if (weekday === 6) return styles.dayHeaderSaturday;
    return "";
  }

  function getShiftCellClass(shift: Shift): string {
    switch (shift) {
      case "DAY": return styles.shiftDay;
      case "LATE": return styles.shiftLate;
      case "NIGHT": return styles.shiftNight;
      case "OFF": return styles.shiftOff;
      default: return "";
    }
  }

  async function runOptimize() {
    try {
      setError(null);
      setStatusMessage(null);
      if (!apiBase) {
        setError("NEXT_PUBLIC_API_BASE が設定されていません");
        return;
      }
      setLoading(true);
      const [yy, mm] = selectedMonth.split("-");
      const qs = new URLSearchParams({ year: String(Number(yy)), month: String(Number(mm)), alternatives: String(alternatives || 1) });
      const res = await fetch(`${apiBase}/optimize/default-md?${qs.toString()}`, { method: "POST" });
      const data: ApiOptimizeResponse = await res.json();
      if (!res.ok) {
        setError(data?.status ? JSON.stringify(data) : res.statusText);
        return;
      }
      const meta = { year: data.year, month: data.month, days: data.days, nurses: data.nurses };
      setSelectedMonth(`${meta.year}-${String(meta.month).padStart(2, "0")}`);
      const sols = data.solutions && data.solutions.length > 0 ? data.solutions : [
        {
          plan_id: "plan-1",
          label: "案1",
          assignments: data.assignments,
          summary: data.summary,
          warnings: data.warnings ?? [],
          violations: data.violations ?? [],
          violation_cells: data.violation_cells ?? [],
          recommendations: data.recommendations ?? [],
        },
      ];
      const primary = sols[0];
      const nextGrid = buildGridFromAssignments(primary.assignments, meta.days, meta.nurses);
      setResultMeta(meta);
      setSolutions(sols);
      setSelectedSolutionIndex(0);
      setGrid(nextGrid);
      setBaseGrid(nextGrid);
      setLockedCells({});
      setViolations(primary.violations ?? []);
      setViolationCells(primary.violation_cells ?? []);
      setRecommendations(primary.recommendations ?? []);
      setWarnings(primary.warnings ?? []);
      setStatusMessage(`最適化完了: ${sols.length}案`);
    } catch (err: any) {
      setError(err?.message ?? String(err));
    } finally {
      setLoading(false);
    }
  }

  function handleSelectSolution(index: number) {
    if (!resultMeta) return;
    const sol = solutions[index];
    if (!sol) return;
    const nextGrid = buildGridFromAssignments(sol.assignments, resultMeta.days, resultMeta.nurses);
    setSelectedSolutionIndex(index);
    setGrid(nextGrid);
    setBaseGrid(nextGrid);
    setLockedCells({});
    setViolations(sol.violations ?? []);
    setViolationCells(sol.violation_cells ?? []);
    setRecommendations(sol.recommendations ?? []);
    setWarnings(sol.warnings ?? []);
    setStatusMessage(`${sol.label} を表示しています`);
  }

  async function reoptimizeWithLocks(nextGridState: Grid, lockMap: Record<string, Shift>) {
    if (!apiBase || !resultMeta) return;
    try {
      setLoading(true);
      setStatusMessage("再最適化を実行中...");
      setError(null);
      const fixedList = Object.entries(lockMap).map(([key, shift]) => {
        const [nurse_id, date] = key.split("|");
        return { nurse_id, date, shift };
      });
      const [yy, mm] = selectedMonth.split("-");
      const payload = {
        assignments: gridToAssignments(nextGridState, resultMeta.days, resultMeta.nurses),
        fixed: fixedList,
        year: Number(yy),
        month: Number(mm),
        alternatives: 1,
      };
      const res = await fetch(`${apiBase}/reoptimize`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data?.detail ? JSON.stringify(data.detail) : res.statusText);
        return;
      }
      if (data.status === "OK") {
        const meta = { year: data.year, month: data.month, days: data.days, nurses: data.nurses };
        const sols = data.solutions && data.solutions.length > 0 ? data.solutions : [
          {
            plan_id: "plan-1",
            label: "案1",
            assignments: data.assignments,
            summary: data.summary,
            warnings: data.warnings ?? [],
            violations: data.violations ?? [],
            violation_cells: data.violation_cells ?? [],
            recommendations: data.recommendations ?? [],
          },
        ];
        const primary = sols[0];
        const nextGrid = buildGridFromAssignments(primary.assignments, meta.days, meta.nurses);
        setResultMeta(meta);
        setSolutions(sols);
        setSelectedSolutionIndex(0);
        setGrid(nextGrid);
        setBaseGrid(nextGrid);
        setViolations(primary.violations ?? []);
        setViolationCells(primary.violation_cells ?? []);
        setRecommendations(primary.recommendations ?? []);
        setWarnings(primary.warnings ?? []);
        setStatusMessage("固定条件付き再最適化が完了しました");
      } else {
        setStatusMessage("再最適化できませんでした。違反内容を確認してください。");
        if (data.analysis) {
          setViolations(data.analysis.violations_detail ?? []);
          setViolationCells(data.analysis.violation_cells ?? []);
          setRecommendations(data.analysis.recommendations ?? []);
          setWarnings(data.analysis.warnings ?? []);
        } else {
          setViolations(data.violations ?? []);
          setViolationCells(data.violation_cells ?? []);
          setRecommendations(data.recommendations ?? []);
          setWarnings(data.warnings ?? []);
        }
      }
    } catch (err: any) {
      setError(err?.message ?? String(err));
    } finally {
      setLoading(false);
    }
  }

  function handleShiftChange(nurseId: string, date: string, shift: Shift) {
    if (!resultMeta) return;
    setStatusMessage(null);
    const current = grid[nurseId]?.[date];
    if (current === shift) return;

    const nextGrid: Grid = { ...grid, [nurseId]: { ...(grid[nurseId] ?? {}), [date]: shift } };
    const key = `${nurseId}|${date}`;
    const baselineShift = baseGrid[nurseId]?.[date];
    const nextLocks: Record<string, Shift> = { ...lockedCells };
    if (shift === baselineShift) {
      delete nextLocks[key];
    } else {
      nextLocks[key] = shift;
    }
    setGrid(nextGrid);
    setLockedCells(nextLocks);
    void reoptimizeWithLocks(nextGrid, nextLocks);
  }

  async function exportCsv() {
    if (!apiBase || !resultMeta) return;
    try {
      const payload = { assignments: gridToAssignments(grid, resultMeta.days, resultMeta.nurses) };
      const res = await fetch(`${apiBase}/export/csv`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      await downloadBlob(res, "assignments.csv");
    } catch (err: any) {
      setError(err?.message ?? String(err));
    }
  }

  async function exportPdf() {
    if (!apiBase || !resultMeta) return;
    try {
      const currentSolution = solutions[selectedSolutionIndex];
      const payload = {
        assignments: gridToAssignments(grid, resultMeta.days, resultMeta.nurses),
        nurses: resultMeta.nurses,
        days: resultMeta.days,
        summary: currentSolution?.summary,
        warnings,
      };
      const res = await fetch(`${apiBase}/export/pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      await downloadBlob(res, "assignments.pdf");
    } catch (err: any) {
      setError(err?.message ?? String(err));
    }
  }

  async function runRecheck() {
    if (!apiBase || !resultMeta) return;
    try {
      setLoading(true);
      setStatusMessage("再チェック中...");
      setError(null);
      const [yy, mm] = selectedMonth.split("-");
      const payload = {
        assignments: gridToAssignments(grid, resultMeta.days, resultMeta.nurses),
        year: Number(yy),
        month: Number(mm),
      };
      const res = await fetch(`${apiBase}/recommend`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data?.detail ? JSON.stringify(data.detail) : res.statusText);
        return;
      }
      setViolations(data.violations_detail ?? []);
      setViolationCells(data.violation_cells ?? []);
      setRecommendations(data.recommendations ?? []);
      setWarnings(data.warnings ?? []);
      setStatusMessage(data.ok ? "再チェックOK" : "再チェックで違反があります");
    } catch (err: any) {
      setError(err?.message ?? String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className={styles.container}>
      <header className={styles.header}>
        <h1>看護師シフト自動割当</h1>
        <p>
          対象月を選び「既存条件で最適化」を押すと、shift.md の既存条件で最大 {alternatives} 案まで取得します。
          セル編集後はロックを保持したまま再最適化し、不足セルは赤破線、補充候補は緑破線で提示します。
        </p>
        <div className={styles.controls}>
          <div className={styles.controlGroup}>
            <label>対象月</label>
            <input type="month" value={selectedMonth} onChange={e => setSelectedMonth(e.target.value)} />
          </div>
          <div className={styles.controlGroup}>
            <label>案数 (alternatives)</label>
            <input
              type="number"
              min={1}
              max={10}
              value={alternatives}
              onChange={e => setAlternatives(Math.max(1, Number(e.target.value) || 1))}
            />
          </div>
          <div className={styles.buttonGroup}>
            <button onClick={runOptimize} disabled={loading} className={`${styles.button} ${styles.buttonPrimary}`}>
              {loading ? "処理中..." : "既存条件で最適化"}
            </button>
            <button onClick={runRecheck} disabled={loading || !resultMeta} className={`${styles.button} ${styles.buttonSecondary}`}>
              再チェック
            </button>
            <button onClick={exportCsv} disabled={!resultMeta} className={`${styles.button} ${styles.buttonSuccess}`}>
              CSV出力
            </button>
            <button onClick={exportPdf} disabled={!resultMeta} className={`${styles.button} ${styles.buttonSuccess}`}>
              PDF出力
            </button>
          </div>
        </div>
        {hasManualLocks && (
          <div className={`${styles.statusMessage} ${styles.statusWarning}`}>
            ※ 手動ロックあり：再最適化後も再チェックを実施してください
          </div>
        )}
        {statusMessage && <div className={`${styles.statusMessage} ${styles.statusSuccess}`}>{statusMessage}</div>}
        {error && <div className={`${styles.statusMessage} ${styles.statusError}`}>{error}</div>}
      </header>

      {resultMeta && (
        <>
          <section className={styles.section}>
            <div className={styles.sectionHeader}>
              <h2>{`${resultMeta.year}年${String(resultMeta.month).padStart(2, "0")}月 シフト案`}</h2>
              {solutions.length > 1 && (
                <div className={styles.solutionButtons}>
                  {solutions.map((sol, idx) => (
                    <button
                      key={sol.plan_id ?? idx}
                      onClick={() => handleSelectSolution(idx)}
                      className={`${styles.solutionButton} ${idx === selectedSolutionIndex ? styles.active : ''}`}
                    >
                      {sol.label || `案${idx + 1}`}
                    </button>
                  ))}
                </div>
              )}
            </div>

            <div className={styles.tableContainer}>
              <table className={styles.shiftTable}>
                <thead>
                  <tr>
                    <th>チーム / Ns</th>
                    {resultMeta.days.map(day => (
                      <th key={day} className={getDayHeaderClass(day)}>
                        {day.slice(-2)}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {resultMeta.nurses.map(nurse => (
                    <tr key={nurse.id}>
                      <th>
                        {nurse.team ? `[${nurse.team}] ` : ""}
                        {nurse.name ?? nurse.id} ({nurse.id})
                      </th>
                      {resultMeta.days.map(day => {
                        const value = grid[nurse.id]?.[day] ?? "OFF";
                        const cellKey = `${nurse.id}|${day}`;
                        const locked = lockedCells[cellKey] !== undefined;
                        const recommended = recommendationSet.has(cellKey);
                        const cellClasses = [
                          styles.shiftCell,
                          getShiftCellClass(value),
                          recommended ? styles.recommended : '',
                          locked ? styles.locked : ''
                        ].filter(Boolean).join(' ');

                        return (
                          <td key={`${nurse.id}-${day}`} className={cellClasses}>
                            <select
                              value={value}
                              onChange={e => handleShiftChange(nurse.id, day, e.target.value as Shift)}
                              className={styles.shiftSelect}
                            >
                              {SHIFT_OPTIONS.map(opt => (
                                <option key={opt} value={opt}>
                                  {SHIFT_LABELS[opt]}
                                </option>
                              ))}
                            </select>
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className={styles.section}>
            <h3>個人サマリ</h3>
            <div className={styles.tableContainer}>
              <table className={styles.summaryTable}>
                <thead>
                  <tr>
                    <th>Ns</th>
                    <th>日勤</th>
                    <th>遅番</th>
                    <th>夜勤</th>
                    <th>公休</th>
                    <th>土日祝</th>
                    <th>勤務日数</th>
                  </tr>
                </thead>
                <tbody>
                  {currentSolution?.summary.per_nurse.map(info => (
                    <tr key={info.nurse_id}>
                      <td>
                        {info.team ? `[${info.team}] ` : ""}
                        {info.name ?? info.nurse_id}
                      </td>
                      <td>{info.counts.DAY ?? 0}</td>
                      <td>{info.counts.LATE ?? 0}</td>
                      <td>{info.counts.NIGHT ?? 0}</td>
                      <td>{info.counts.OFF ?? 0}</td>
                      <td>{info.weekend_work ?? 0}</td>
                      <td>{info.total_work_days ?? 0}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          <section className={styles.section}>
            <h3>日別充足状況</h3>
            <div className={styles.tableContainer}>
              <table className={styles.demandTable}>
                <thead>
                  <tr>
                    <th>日付</th>
                    <th>日勤</th>
                    <th>遅番</th>
                    <th>夜勤</th>
                  </tr>
                </thead>
                <tbody>
                  {currentSolution?.summary.per_day.map(day => {
                    const dayKey = `${day.date}|DAY`;
                    const lateKey = `${day.date}|LATE`;
                    const nightKey = `${day.date}|NIGHT`;
                    const dayViolation = violationMap.get(dayKey);
                    const lateViolation = violationMap.get(lateKey);
                    const nightViolation = violationMap.get(nightKey);

                    return (
                      <tr key={day.date}>
                        <td>
                          {day.date} ({day.weekday})
                        </td>
                        <td className={`${styles.demandCell} ${dayViolation ? styles.violation : ''} ${dayViolation?.kind === 'excess' ? styles.excess : ''}`}>
                          {day.filled.DAY} / {day.requirements.day_min}-{day.requirements.day_max}
                        </td>
                        <td className={`${styles.demandCell} ${lateViolation ? styles.violation : ''} ${lateViolation?.kind === 'excess' ? styles.excess : ''}`}>
                          {day.filled.LATE} / {day.requirements.late}
                        </td>
                        <td className={`${styles.demandCell} ${nightViolation ? styles.violation : ''} ${nightViolation?.kind === 'excess' ? styles.excess : ''}`}>
                          {day.filled.NIGHT} / {day.requirements.night}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </section>

          <section className={styles.section}>
            <div className={styles.violations}>
              <h3>違反・警告</h3>
              {violations && violations.length > 0 ? (
                <ul className={styles.violationList}>
                  {violations.map((v, idx) => (
                    <li key={`${v.date}-${v.shift}-${idx}`} className={`${styles.violationItem} ${v.kind === "shortage" ? styles.shortage : styles.excess}`}>
                      {v.message || `${v.date} ${SHIFT_LABELS[v.shift]} ${v.kind === "shortage" ? "不足" : "過多"}`}
                    </li>
                  ))}
                </ul>
              ) : (
                <span className={styles.noViolations}>違反はありません</span>
              )}
              {warnings && warnings.length > 0 && (
                <details className={styles.details}>
                  <summary className={styles.detailsSummary}>警告を見る</summary>
                  <div className={styles.detailsContent}>
                    <ul className={styles.violationList}>
                      {warnings.map((w, idx) => (
                        <li key={`${w}-${idx}`}>{w}</li>
                      ))}
                    </ul>
                  </div>
                </details>
              )}
            </div>
          </section>

          <section className={styles.section}>
            <h3>補充レコメンド</h3>
            {recommendations && recommendations.length > 0 ? (
              <ul className={styles.recommendationList}>
                {recommendations.map((rec, idx) => (
                  <li key={`${rec.date}-${rec.shift}-${idx}`} className={styles.recommendationItem}>
                    <div>
                      {rec.date} {SHIFT_LABELS[rec.shift]} {rec.kind === "shortage" ? "不足" : "過多"}
                    </div>
                    <ul className={styles.suggestionList}>
                      {rec.suggestions?.map((sug, sidx) => (
                        <li key={`${sug.nurse_id}-${sidx}`} className={sug.locked ? styles.locked : styles.available}>
                          {`Ns ${sug.nurse_id}: ${sug.current_shift} → ${SHIFT_LABELS[sug.suggested_shift]} (${sug.reason ?? "候補"})`}
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            ) : (
              <span className={styles.noViolations}>補充レコメンドはありません</span>
            )}
          </section>

          <section className={styles.section}>
            <details className={styles.details}>
              <summary className={styles.detailsSummary}>現在の割当（JSON）</summary>
              <div className={styles.detailsContent}>
                <textarea value={manualPayload} readOnly className={styles.jsonTextarea} />
              </div>
            </details>
          </section>
        </>
      )}
    </main>
  );
}
