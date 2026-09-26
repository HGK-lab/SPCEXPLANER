# 오프라인 실험: 가상 데이터 → 규칙 판정 → LLM 설명·단독 판정(반복, 캐시) → 지표·리포트·ai_errors
import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable

from . import config, explain, generator, llm_detect, report, rules, secom
from .llm_client import LLMReply
from .matching import classify, summarize
from .patterns import KOREAN, PATTERNS, Event

LLMFn = Callable[[dict, str, str], LLMReply]  # (모델 설정, system, user) → 응답. 실패는 예외 대신 error로

AI_ERRORS_HEADER = """# LLM 오류 기록

규칙(CLAUDE.md): LLM이 틀린 출력을 내면 지우지 않고 입력·출력·틀린 점을 여기에 남긴다.

- 입력: 시리즈 번호와 시드로 재현된다 (`data/synthetic/series.json`).
- 출력: 전체 원문은 같은 커밋의 `results/explanations.json`, `results/llm_detections.json`에 있다.
- 단독 판정의 "틀린 점"은 규칙 엔진 판정과 다른 부분이다.
- `scripts/run_experiment.py`가 실행마다 섹션을 덧붙인다. 캐시에서 꺼낸 결과는 다시 적지 않는다.
"""


@dataclass
class Paths:
    """실험이 읽고 쓰는 파일들. 기본값은 저장소 안의 실제 위치."""

    series: Path = config.SERIES_PATH
    explanations: Path = config.EXPLANATIONS_PATH
    detections: Path = config.DETECTIONS_PATH
    metrics: Path = config.METRICS_PATH
    report: Path = config.REPORT_PATH
    ai_errors: Path = config.AI_ERRORS_PATH
    secom: Path = config.SECOM_PATH

    @staticmethod
    def under(root: Path) -> "Paths":
        """테스트용: 모든 파일을 root 아래에 둔다."""
        return Paths(root / "series.json", root / "explanations.json", root / "llm_detections.json",
                     root / "metrics.json", root / "report.md", root / "ai_errors.md", root / "secom.csv")


@dataclass
class Job:
    key: tuple  # (모델 이름, 시리즈 번호 문자열, 반복 번호)
    model: dict
    system: str
    user: str


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _hash(model: dict, system: str, user: str) -> str:
    """캐시 키: 모델·temperature·프롬프트 전체가 같아야 같은 입력으로 본다."""
    raw = "\n\n".join([model["name"], str(model.get("temperature")), system, user])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def _write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def _run_jobs(jobs: list[Job], llm: LLMFn) -> list[tuple[Job, LLMReply]]:
    """작업들을 동시에 호출한다 (MAX_WORKERS개씩)."""
    if not jobs:
        return []
    with ThreadPoolExecutor(max_workers=config.MAX_WORKERS) as pool:
        replies = list(pool.map(lambda j: llm(j.model, j.system, j.user), jobs))
    return list(zip(jobs, replies))


def _record(run: int, reply: LLMReply, issues: list[dict]) -> dict:
    return {"run": run, "text": reply.text, "error": reply.error, "latency_s": round(reply.latency_s, 2),
            "usage": reply.usage, "issues": issues, "created": _now()}


def _reusable(prev: dict, h: str, force: bool) -> dict:
    """캐시에서 다시 쓸 반복 {반복 번호: 기록}. 입력이 달라졌거나 호출 오류였던 반복은 버린다."""
    if force or prev.get("input_hash") != h:
        return {}
    return {r["run"]: r for r in prev.get("runs", []) if r["error"] is None}


def _error_row(kind: str, model: str, sid: str, run: int, types: str, detail: str, text: str | None) -> dict:
    excerpt = (text or "").replace("\n", " ").replace("`", "'")[:160]
    return {"kind": kind, "model": model, "series": sid, "run": run, "types": types,
            "detail": detail[:300], "excerpt": excerpt}


def run_explanations(dataset: dict, llm: LLMFn, cache: dict, force: bool = False) -> tuple[dict, list[dict]]:
    """사건이 있는 시리즈마다 설명을 repeats번 받는다. (저장할 결과, 새로 받은 출력의 오류 목록)."""
    model = config.EXPLAIN_MODEL
    old = cache.get("series", {}) if cache.get("prompt_version") == explain.PROMPT_VERSION else {}
    out = {"prompt_version": explain.PROMPT_VERSION, "model": model, "series": {}}
    jobs = []
    for s in dataset["series"]:
        events = rules.detect(s["values"])
        if not events:
            continue  # 이상 없음 → LLM을 부르지 않는다
        sid = str(s["id"])
        inp = explain.build_input(s["values"], events)
        system, user = explain.build_messages(inp)
        h = _hash(model, system, user)
        runs = _reusable(old.get(sid, {}), h, force)
        out["series"][sid] = {"input": inp, "input_hash": h, "runs": runs}
        jobs += [Job((model["name"], sid, k), model, system, user) for k in range(model["repeats"]) if k not in runs]
    errors = []
    for job, reply in _run_jobs(jobs, llm):
        _, sid, k = job.key
        entry = out["series"][sid]
        issues = explain.validate(reply.text, entry["input"])[1] if reply.error is None else []
        entry["runs"][k] = _record(k, reply, issues)
        if issues:
            types = ", ".join(sorted({explain.ISSUE_KO[i["type"]] for i in issues}))
            detail = "; ".join(i["detail"] for i in issues)
            errors.append(_error_row("설명", model["name"], sid, k, types, detail, reply.text))
    for entry in out["series"].values():
        entry["runs"] = [entry["runs"][k] for k in sorted(entry["runs"])]
    return out, errors


def _detect_mistakes(reference: list[Event], found: list[Event]) -> str:
    """단독 판정 출력이 규칙 엔진 판정과 다른 점. 같으면 빈 문자열."""
    detected, kinds = classify(reference, found)
    parts = [f"놓침 {KOREAN[r.pattern]} {r.start}~{r.end}번" for r, hit in zip(reference, detected) if not hit]
    label = {"confusion": "패턴 다름", "false": "없는 사건"}
    parts += [f"{label[k]} {KOREAN[f.pattern]} {f.start}~{f.end}번" for f, k in zip(found, kinds) if k != "hit"]
    return "; ".join(parts)


def run_detections(dataset: dict, llm: LLMFn, cache: dict, force: bool = False) -> tuple[dict, list[dict]]:
    """켜진 모델마다 모든 시리즈를 repeats번 단독 판정한다. (저장할 결과, 새로 받은 출력의 오류 목록)."""
    same_version = cache.get("prompt_version") == llm_detect.PROMPT_VERSION
    out = {"prompt_version": llm_detect.PROMPT_VERSION, "models": {}}
    reference = {str(s["id"]): rules.detect(s["values"]) for s in dataset["series"]}
    jobs = []
    for model in [m for m in config.DETECT_MODELS if m["enabled"]]:
        old = cache.get("models", {}).get(model["name"], {}).get("series", {}) if same_version else {}
        entry = {"config": model, "series": {}}
        for s in dataset["series"]:
            sid = str(s["id"])
            system, user = llm_detect.build_messages(s["values"])
            h = _hash(model, system, user)
            runs = _reusable(old.get(sid, {}), h, force)
            entry["series"][sid] = {"input_hash": h, "runs": runs}
            jobs += [Job((model["name"], sid, k), model, system, user) for k in range(model["repeats"]) if k not in runs]
        out["models"][model["name"]] = entry
    errors = []
    for job, reply in _run_jobs(jobs, llm):
        name, sid, k = job.key
        events, issues = llm_detect.parse(reply.text) if reply.error is None else ([], [])
        rec = _record(k, reply, issues)
        rec["events"] = [e.to_dict() for e in events]
        out["models"][name]["series"][sid]["runs"][k] = rec
        if reply.error is not None:
            continue  # 호출 오류는 LLM 출력 오류가 아니므로 ai_errors에 적지 않는다
        if issues:
            errors.append(_error_row("단독 판정", name, sid, k, "JSON 형식 위반", issues[0]["detail"], reply.text))
        else:
            detail = _detect_mistakes(reference[sid], events)
            if detail:
                errors.append(_error_row("단독 판정", name, sid, k, "판정 오류", detail, reply.text))
    for entry in out["models"].values():
        for s in entry["series"].values():
            s["runs"] = [s["runs"][k] for k in sorted(s["runs"])]
    return out, errors


def append_ai_errors(errors: list[dict], path: Path, label: str) -> None:
    """새 오류를 실행 단위 섹션으로 덧붙인다. 기존 내용은 지우지 않는다."""
    if not errors:
        return
    text = path.read_text(encoding="utf-8") if path.exists() else AI_ERRORS_HEADER
    rows = ["", f"## 실행 {label}", "",
            "| 구분 | 모델 | 시리즈 | 반복 | 유형 | 틀린 점 | 출력 발췌 |", "|---|---|---|---|---|---|---|"]
    for e in errors:
        cells = [e["kind"], e["model"], e["series"], str(e["run"] + 1), e["types"], e["detail"], "`" + e["excerpt"] + "`"]
        rows.append("| " + " | ".join(c.replace("|", "\\|") for c in cells) + " |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip("\n") + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def _explain_metrics(explanations: dict) -> dict | None:
    series = explanations.get("series") or {}
    if not series:
        return None
    model = explanations["model"]
    outputs = passed = call_errors = changed = 0
    issue_outputs = {"format": 0, "cause": 0, "mismatch": 0}
    for entry in series.values():
        signatures = set()
        for r in entry["runs"]:
            outputs += 1
            if r["error"] is not None:
                call_errors += 1
                continue
            types = {i["type"] for i in r["issues"]}
            for t in types:
                issue_outputs[t] += 1
            passed += int(not types)
            signatures.add(explain.signature(explain.validate(r["text"], entry["input"])[0]))
        changed += int(len(signatures) > 1)
    return {"model": model["name"], "temperature": model.get("temperature"), "repeats": model["repeats"],
            "prompt_version": explanations.get("prompt_version"), "series_called": len(series),
            "outputs": outputs, "passed": passed, "issue_outputs": issue_outputs,
            "call_errors": call_errors, "repeat_changed_series": changed}


def _detect_metrics(detections: dict, series: list[dict], truths: list[list[Event]]) -> list[dict]:
    result = []
    for name, entry in (detections.get("models") or {}).items():
        cfg = entry["config"]
        runs = []
        for k in range(cfg["repeats"]):
            founds, fmt, err = [], 0, 0
            for s in series:
                recs = entry["series"].get(str(s["id"]), {}).get("runs", [])
                rec = next((r for r in recs if r["run"] == k), None)
                if rec is None or rec["error"] is not None:
                    err += 1  # 결과가 없거나 호출 오류 → 탐지 0개로 채점
                    founds.append([])
                    continue
                fmt += int(bool(rec["issues"]))
                founds.append([Event.from_dict(e) for e in rec["events"]])
            runs.append(dict(summarize(truths, founds), format_violations=fmt, call_errors=err))
        result.append({"model": name, "temperature": cfg.get("temperature"), "repeats": cfg["repeats"],
                       "prompt_version": detections.get("prompt_version"), "runs": runs})
    return result


def compute_metrics(dataset: dict, explanations: dict, detections: dict, secom_df=None) -> dict:
    """저장된 결과로 리포트용 지표를 계산한다 (LLM을 부르지 않는다)."""
    series = dataset["series"]
    truths = [generator.truth_events(s) for s in series]
    return {
        "generated_at": _now(),
        "dataset": {
            "seed": dataset["seed"],
            "n_series": len(series),
            "n_normal": sum(1 for t in truths if not t),
            "n_points": len(series[0]["values"]),
            "injected": {p: sum(1 for t in truths for e in t if e.pattern == p) for p in PATTERNS},
        },
        "rules": summarize(truths, [rules.detect(s["values"]) for s in series]),
        "detect": _detect_metrics(detections, series, truths),
        "explain": _explain_metrics(explanations),
        "secom": secom.summarize(secom_df) if secom_df is not None else None,
    }


def run_all(llm: LLMFn | None, paths: Paths | None = None, force: bool = False) -> dict:
    """전체 실험. llm이 None이면 LLM을 부르지 않고 저장된 결과로 지표·리포트만 다시 만든다."""
    paths = paths or Paths()
    dataset = generator.generate_dataset()
    generator.save_dataset(dataset, paths.series)
    explanations = _read_json(paths.explanations)
    detections = _read_json(paths.detections)
    if llm is not None:
        explanations, explain_errors = run_explanations(dataset, llm, explanations, force)
        detections, detect_errors = run_detections(dataset, llm, detections, force)
        _write_json(paths.explanations, explanations)
        _write_json(paths.detections, detections)
        label = f"{_now()} (설명 {explain.PROMPT_VERSION}, 단독 판정 {llm_detect.PROMPT_VERSION})"
        append_ai_errors(explain_errors + detect_errors, paths.ai_errors, label)
    metrics = compute_metrics(dataset, explanations, detections, secom.load(paths.secom))
    _write_json(paths.metrics, metrics)
    report.write(metrics, paths.report)
    return metrics
