# 지표(metrics.json) → 검증 리포트 마크다운. 앱 맨 아래 "전체 검증 리포트" 펼치기도 이 파일을 그대로 보여준다.
from pathlib import Path

from . import config
from .patterns import KOREAN, PATTERNS


def pct(x, digits: int = 0) -> str:
    return "-" if x is None else f"{x * 100:.{digits}f}%"


def num(x) -> str:
    """7.0 → "7", 6.333 → "6.3"."""
    return f"{x:.1f}".rstrip("0").rstrip(".")


def _mean(xs: list) -> float | None:
    return sum(xs) / len(xs) if xs else None


def _counts(d: dict) -> str:
    return ", ".join(f"{KOREAN[p]} {d[p]}" for p in PATTERNS)


def _temp(t) -> str:
    return "기본값" if t is None else str(t)


def rules_section(r: dict) -> list[str]:
    lines = ["## 2. 규칙 판정", "", "| 패턴 | 탐지 / 심은 수 | 탐지율 |", "|---|---|---|"]
    for p in PATTERNS:
        d = r["per_pattern"][p]
        rate = d["detected"] / d["injected"] if d["injected"] else None
        lines.append(f"| {KOREAN[p]} | {d['detected']} / {d['injected']} | {pct(rate)} |")
    lines.append(f"| 전체 | {r['detected']} / {r['injected']} | {pct(r['rate'])} |")
    n, a = r["normal"], r["anomalous"]
    lines += [
        "",
        "오탐 (심은 이상과 겹치지 않는 경보):",
        f"- 정상 시리즈: {n['series']}개 중 {n['alarmed_series']}개에서 경보. 오탐 사건: {_counts(n['false_events'])}",
        f"- 이상 시리즈: 오탐 사건 {_counts(a['false_events'])}. 패턴 혼동 {a['confusions']}건",
    ]
    if r["false_list"]:
        items = "; ".join(f"시리즈 {f['series']} {KOREAN[f['pattern']]} {f['start']}~{f['end']}번" for f in r["false_list"])
        lines.append(f"- 오탐 목록: {items}")
    lines += [
        "- 정상 점을 N(100, 1²)로 만들었으므로 정상 구간에서도 규칙 정의를 실제로 만족하는 경보가 생길 수 있다. "
        "규칙 판정에도 오탐이 있다는 뜻이다.",
        "- 교차 검증: 독립 구현(shewhart)과 점 단위 판정이 같은지 `tests/test_crosscheck.py`에서 확인한다.",
        "",
    ]
    return lines


def _detect_row(name: str, runs: list[dict], llm: bool) -> str:
    rates = [r["rate"] for r in runs if r["rate"] is not None]
    if len(rates) > 1:
        rate = f"{pct(_mean(rates))} ({pct(min(rates))}~{pct(max(rates))})"
    else:
        rate = pct(rates[0]) if rates else "-"
    per = " | ".join(
        f"{num(_mean([r['per_pattern'][p]['detected'] for r in runs]))}/{runs[0]['per_pattern'][p]['injected']}"
        for p in PATTERNS
    )
    alarmed = f"{num(_mean([r['normal']['alarmed_series'] for r in runs]))}/{runs[0]['normal']['series']}"
    false = num(_mean([sum(r["normal"]["false_events"].values()) + sum(r["anomalous"]["false_events"].values())
                       for r in runs]))
    conf = num(_mean([r["anomalous"]["confusions"] for r in runs]))
    fmt = str(sum(r["format_violations"] for r in runs)) if llm else "-"
    err = str(sum(r["call_errors"] for r in runs)) if llm else "-"
    return f"| {name} | {len(runs)} | {rate} | {per} | {alarmed} | {false} | {conf} | {fmt} | {err} |"


def detect_section(rules: dict, detect: list[dict]) -> list[str]:
    lines = [
        "## 3. LLM 단독 판정 비교",
        "",
        "LLM에게 규칙 정의와 원시 데이터(번호: 값)만 주고 직접 판정하게 했다. 채점 기준은 규칙 엔진과 같다. "
        "패턴별 탐지 수·경보·오탐·혼동은 반복 평균, 형식 위반·호출 오류는 반복 합계다.",
        "",
        "| 판정 방식 | 반복 | 탐지율 평균 (최소~최대) | 급변 | 추세 | 치우침 | 정상 시리즈 경보 | 오탐 사건 | 패턴 혼동 | 형식 위반 | 호출 오류 |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
        _detect_row("규칙 엔진", [rules], llm=False),
    ]
    for d in detect:
        lines.append(_detect_row(f"{d['model']} (temperature {_temp(d['temperature'])})", d["runs"], llm=True))
    if not detect:
        lines += ["", "LLM 단독 판정은 아직 실행하지 않았다."]
    lines += ["", "- 형식 위반 출력과 호출 오류는 탐지 0개로 채점했다. 호출 오류가 있으면 실험을 다시 돌려 채운다.", ""]
    return lines


def explain_section(e: dict | None) -> list[str]:
    title = "## 4. LLM 설명 검증"
    if not e:
        return [title, "", "아직 실행하지 않았다.", ""]
    return [
        f"{title} ({e['model']}, temperature {_temp(e['temperature'])}, 같은 입력 {e['repeats']}회)",
        "",
        f"사건이 있는 시리즈 {e['series_called']}개 × {e['repeats']}회 = 출력 {e['outputs']}개. "
        "한 출력에 여러 유형의 문제가 있으면 유형마다 센다.",
        "",
        "| 항목 | 출력 수 |",
        "|---|---|",
        f"| 검증 통과 | {e['passed']} |",
        f"| JSON 형식 위반 | {e['issue_outputs']['format']} |",
        f"| 원인표 밖 원인 | {e['issue_outputs']['cause']} |",
        f"| 판정 불일치 | {e['issue_outputs']['mismatch']} |",
        f"| 호출 오류 | {e['call_errors']} |",
        "",
        f"- 반복 간 차이: {e['series_called']}개 시리즈 중 {e['repeat_changed_series']}개에서 "
        "사건별 1순위 원인이나 점검 순서가 반복마다 달랐다.",
        "- 틀린 출력의 원문 발췌는 `docs/ai_errors.md`에 있다.",
        "- 이번 실험은 JSON 모드 + 자체 검증기를 썼다. 운영에서는 strict 스키마와 원인 id enum으로 "
        "형식 위반·원인표 밖 원인을 원천 차단할 수 있다.",
        "- 원인표는 교과서 수준의 도메인 가정이며 실제 설비 데이터로 검증하지 않았다.",
        "",
    ]


def secom_section(s: dict | None) -> list[str]:
    lines = ["## 5. 실데이터 확인 (UCI SECOM)", ""]
    if not s:
        return lines + ["선택 항목 — 데이터가 없어 건너뜀 (`python scripts/fetch_secom.py`).", ""]
    lines += [
        f"시간순 앞 {s['phase1_n']}점(Phase I)으로 한계를 추정하고 나머지 {s['n'] - s['phase1_n']}점(Phase II)을 "
        "같은 규칙으로 감시했다. 정답이 없어 탐지율은 계산하지 않는다.",
        "",
        "| 센서 | 중심선 | σ | 알람 사건 (급변/추세/치우침) | 불량 포함 사건 | 알람 점 중 불량 비율 | Phase II 전체 불량 비율 |",
        "|---|---|---|---|---|---|---|",
    ]
    for name, d in s["sensors"].items():
        bp, lim = d["by_pattern"], d["limits"]
        lines.append(
            f"| {name} | {lim['center']:.4g} | {lim['sigma']:.4g} | {d['events']} ({bp['spike']}/{bp['trend']}/{bp['shift']}) "
            f"| {d['events_with_fail']} | {pct(d['fail_rate_flagged'], 1)} | {pct(d['fail_rate_phase2'], 1)} |"
        )
    lines += [
        "",
        "- 겹침은 관찰일 뿐이다. 인과관계나 탐지 성능으로 해석하지 않는다.",
        "- 출처: UCI SECOM (McCann & Johnston, 2008), CC BY 4.0, DOI 10.24432/C54305.",
        "",
    ]
    return lines


def caution_section(m: dict) -> list[str]:
    d = m["dataset"]
    lines = [
        "## 6. 해석 시 주의",
        "",
        "- 합성 데이터라 실제 공정의 잡음 구조(자기상관, 비정규성 등)를 반영하지 않는다.",
        f"- 시리즈 {d['n_series']}개, 심은 이상 {sum(d['injected'].values())}개로 표본이 작다. 비율은 참고치다.",
    ]
    fixed = [x["model"] for x in m["detect"] if x["temperature"] is None]
    if fixed:
        lines.append(f"- {', '.join(fixed)}은(는) temperature를 바꿀 수 없어 기본값으로 실행했다.")
    return lines + [""]


def render(m: dict) -> str:
    d = m["dataset"]
    injected = ", ".join(f"{KOREAN[p]} {d['injected'][p]}" for p in PATTERNS)
    u = config.UNIT
    limits = f"중심 {config.CENTER:g}{u}, UCL {config.UCL:g}{u}, LCL {config.LCL:g}{u}"
    lines = [
        "# 검증 리포트",
        "",
        f"> 자동 생성: `python scripts/run_experiment.py` · {m['generated_at']}  ",
        f"> 관리한계 고정값({limits}) 사용 = 이미 안정화된 공정을 감시하는 상황을 가정한다.",
        "",
        "## 1. 실험 조건",
        "",
        f"- 가상 데이터: {d['n_series']}개 시리즈 × {d['n_points']}점, 시드 {d['seed']}. "
        f"정상 시리즈 {d['n_normal']}개, 심은 이상 {sum(d['injected'].values())}개 ({injected}).",
        f"- 심은 이상은 규칙 정의를 만족하도록 만들었다: 급변 = 한계 밖 1점, 추세 = {config.TREND_LEN}점 연속 단조, "
        f"치우침 = {config.SHIFT_LEN}점 연속 중심선 한쪽.",
        "- 채점: 같은 패턴의 탐지 구간이 정답 구간과 한 점이라도 겹치면 탐지. "
        "어떤 정답과도 겹치지 않으면 오탐, 다른 패턴의 정답과만 겹치면 패턴 혼동.",
        "",
    ]
    lines += rules_section(m["rules"])
    lines += detect_section(m["rules"], m["detect"])
    lines += explain_section(m["explain"])
    lines += secom_section(m["secom"])
    lines += caution_section(m)
    return "\n".join(lines)


def write(m: dict, path: Path = config.REPORT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(m), encoding="utf-8")
