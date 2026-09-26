# 04 검증 섹션(규칙 판정 vs LLM 단독 판정)의 지표 가공과 HTML.
# 스타일 출처: docs/design/ref/detection-bars.png, Claude Design 2A. 모든 숫자는 metrics.json·explanations.json에서만 읽는다.
from .explain import ISSUE_KO
from .patterns import FROM_KOREAN, KOREAN, PATTERNS
from .ui_html import PATTERN_COLORS, RULE_ID, SYMBOL, esc, span_text, term

RULE_BAR = "#2a2f35"  # 규칙 판정 막대 (검정)
MODEL_BARS = ["#8cbde6", "#0068a7", "#1d5f94"]  # LLM 모델 순서대로 (소형은 옅은 파랑, 상위는 진한 파랑)
MODEL_TIER = {"gpt-4.1-mini": "AI · 소형", "gpt-6-sol": "AI · 상위", "gpt-6-astra": "AI · 추가"}  # 화면 표기용
PRINCIPLE = "이 앱은 판정을 규칙이 맡고, AI는 판정 결과를 받아 해석과 점검 순서만 만든다."


def fmt_pct(x) -> str:
    """0.6333 → "63.3%", 1.0 → "100%", None → "-"."""
    if x is None:
        return "-"
    return f"{x * 100:.1f}".rstrip("0").rstrip(".") + "%"


def fmt_num(x) -> str:
    """3.0 → "3", 1.5 → "1.5"."""
    return f"{x:.1f}".rstrip("0").rstrip(".")


def tier(name: str) -> str:
    return MODEL_TIER.get(name, "AI")


def _pair(summary: dict, p: str) -> tuple[int, int]:
    """matching.summarize 결과에서 (탐지 수, 심은 수). p="all"이면 전체."""
    if p == "all":
        return summary["detected"], summary["injected"]
    d = summary["per_pattern"][p]
    return d["detected"], d["injected"]


def _false_events(summary: dict) -> int:
    return sum(summary["normal"]["false_events"].values()) + sum(summary["anomalous"]["false_events"].values())


def _stats(pairs: list[tuple[int, int]]) -> dict:
    """반복별 (탐지 수, 심은 수) → 평균·최소·최대 탐지율과 평균 탐지 수."""
    rates = [d / n for d, n in pairs if n]
    if not rates:
        return {"mean": None, "min": None, "max": None, "mean_detected": 0.0}
    return {"mean": sum(rates) / len(rates), "min": min(rates), "max": max(rates),
            "mean_detected": sum(d for d, _ in pairs) / len(pairs)}


def _mean(xs: list) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def detection_groups(metrics: dict) -> list[dict]:
    """패턴별(+전체) 규칙 판정 vs 모델별 LLM 단독 판정 탐지율. 막대 그림의 입력."""
    groups = []
    for p in list(PATTERNS) + ["all"]:
        detected, injected = _pair(metrics["rules"], p)
        models = [dict(name=d["model"], repeats=len(d["runs"]), **_stats([_pair(r, p) for r in d["runs"]]))
                  for d in metrics["detect"]]
        groups.append({
            "key": p,
            "label": "전체" if p == "all" else KOREAN[p],
            "symbol": SYMBOL.get(p, ""),
            "rule_id": RULE_ID.get(p, ""),
            "injected": injected,
            "rule": {"rate": detected / injected if injected else None, "detected": detected},
            "models": models,
        })
    return groups


def kpi_summary(metrics: dict) -> dict:
    """KPI 카드 숫자: 규칙 판정, 모델별 LLM 단독 판정(반복 평균·범위·오탐), 설명 검증."""
    r = metrics["rules"]
    rule = {"rate": r["rate"], "detected": r["detected"], "injected": r["injected"], "false_events": _false_events(r),
            "normal_alarmed": r["normal"]["alarmed_series"], "normal_series": r["normal"]["series"]}
    models = []
    for d in metrics["detect"]:
        runs = d["runs"]
        stats = _stats([_pair(x, "all") for x in runs])
        models.append(dict(
            name=d["model"], repeats=len(runs), temperature=d["temperature"],
            false_mean=_mean([_false_events(x) for x in runs]),
            missed_total=sum(x["injected"] - x["detected"] for x in runs),
            false_total=sum(_false_events(x) for x in runs),
            confusions_total=sum(x["anomalous"]["confusions"] for x in runs),
            format_violations=sum(x["format_violations"] for x in runs),
            call_errors=sum(x["call_errors"] for x in runs),
            **stats,
        ))
    return {"rule": rule, "models": models, "explain": metrics.get("explain")}


def subtitle_text(metrics: dict | None) -> str:
    if not metrics:
        return "검증 결과 파일이 아직 없습니다."
    d = metrics["dataset"]
    counts = " · ".join(f"{KOREAN[p]} {d['injected'][p]}" for p in PATTERNS)
    return (f"검증 세트 · 규칙 정의대로 이상을 심은 가상 시리즈 {d['n_series']}개 × {d['n_points']}점, "
            f"심은 이상 {sum(d['injected'].values())}건({counts}) · 심은 위치를 정답으로 사용 · 지표 생성 {metrics['generated_at']}")


def kpi_rule_html(rule: dict) -> str:
    return ('<div class="spc-kpi"><div class="spc-kpi-top"><span class="b-rule">규칙</span>규칙 판정 탐지율</div>'
            f'<div class="spc-kpi-num">{fmt_pct(rule["rate"])}</div>'
            f'<div class="spc-kpi-sub">{rule["detected"]}/{rule["injected"]} 탐지 · {term("오탐")} {rule["false_events"]}건 '
            f'(정상 시리즈 {rule["normal_alarmed"]}/{rule["normal_series"]}개 경보) · 매번 같은 결과</div></div>')


def kpi_model_html(m: dict, rule_rate) -> str:
    """모델 하나의 KPI 카드: 등급 표기 + 실제 모델명 + 반복 평균 탐지율(규칙 대비 차이)."""
    delta = ""
    if m["mean"] is not None and rule_rate is not None and m["mean"] != rule_rate:
        diff = f"{(m['mean'] - rule_rate) * 100:+.1f}".replace("-", "−")
        delta = f'<span class="spc-kpi-delta">{diff}%p</span>'
    spread = (f'반복 {m["repeats"]}회 {fmt_pct(m["min"])}~{fmt_pct(m["max"])}' if m["repeats"] > 1
              else f'{m["repeats"]}회 실행')
    return ('<div class="spc-kpi">'
            f'<div class="spc-kpi-top"><span class="b-ai">{esc(tier(m["name"]))}</span>AI 단독 판정 탐지율</div>'
            f'<div class="spc-kpi-num">{fmt_pct(m["mean"])}{delta}</div>'
            f'<div class="spc-kpi-sub"><span class="spc-kpi-name">{esc(m["name"])}</span> · {spread} · '
            f'{term("오탐")} 평균 {fmt_num(m["false_mean"])}건 · 형식 위반 {m["format_violations"]} · 호출 오류 {m["call_errors"]}</div></div>')


def _bar_row(who: str, color: str, rate, lo, hi, value_text: str, frac_text: str) -> str:
    """막대 한 줄: [누구] [회색 바탕 위 채운 막대 (+ 최소~최대 선)] [%·분수]."""
    width = 0.0 if rate is None else max(0.0, min(1.0, rate)) * 100
    whisker = ""
    if lo is not None and hi is not None and hi > lo:
        whisker = f'<span class="spc-range" style="left:{lo * 100:.1f}%;width:{(hi - lo) * 100:.1f}%"></span>'
    return (f'<div class="spc-bar-row"><span class="spc-bar-who">{esc(who)}</span>'
            f'<div class="spc-track"><div class="spc-fill" style="width:{width:.1f}%;background:{color}"></div>{whisker}</div>'
            f'<div class="spc-bar-val"><b>{esc(value_text)}</b> <span>{esc(frac_text)}</span></div></div>')


def detection_bars_html(groups: list[dict]) -> str:
    """패턴별 탐지율: 규칙 판정(검정) vs LLM 단독(모델별 파랑, 반복 평균 + 최소~최대 선)."""
    names = [m["name"] for m in groups[0]["models"]] if groups else []
    legend = f'<span class="spc-lg"><i style="background:{RULE_BAR}"></i>규칙 판정</span>'
    for i, name in enumerate(names):
        legend += f'<span class="spc-lg"><i style="background:{MODEL_BARS[i % len(MODEL_BARS)]}"></i>{esc(name)}</span>'
    parts = [f'<div class="spc-bars-head"><b>패턴별 탐지율</b><span>{legend}</span></div>']
    for g in groups:
        color = PATTERN_COLORS[g["key"]]["text"] if g["key"] in PATTERN_COLORS else "#16191d"
        title = f'{g["symbol"]} {term(g["label"])}' if g["key"] in PATTERN_COLORS else esc(g["label"])
        sub = f'{g["rule_id"]} · {g["injected"]}건' if g["rule_id"] else f'{g["injected"]}건'
        rows = [_bar_row("규칙 판정", RULE_BAR, g["rule"]["rate"], None, None,
                         fmt_pct(g["rule"]["rate"]), f'{g["rule"]["detected"]}/{g["injected"]}')]
        for i, m in enumerate(g["models"]):
            many = m["repeats"] > 1
            value = fmt_pct(m["mean"]) + (f' ({fmt_pct(m["min"])}~{fmt_pct(m["max"])})' if many else "")
            rows.append(_bar_row(m["name"], MODEL_BARS[i % len(MODEL_BARS)], m["mean"],
                                 m["min"] if many else None, m["max"] if many else None,
                                 value, f'{fmt_num(m["mean_detected"])}/{g["injected"]}'))
        cls = "spc-bar-group total" if g["key"] == "all" else "spc-bar-group"
        rows_html = "".join(rows)
        parts.append(f'<div class="{cls}"><div class="spc-bar-name"><b style="color:{color}">{title}</b>'
                     f'<small>{esc(sub)}</small></div><div class="spc-bar-rows">{rows_html}</div></div>')
    return "".join(parts)


def fact_lines(metrics: dict) -> list[str]:
    """수치에서 바로 읽히는 사실만 문장으로 만든다 (결론·추측은 쓰지 않는다)."""
    groups = detection_groups(metrics)
    total = groups[-1]
    lines = [f"규칙 판정: 심은 이상 {total['injected']}개 중 {total['rule']['detected']}개 탐지."]
    for i, model in enumerate(total["models"]):
        per = [(g["models"][i]["mean"], g) for g in groups[:-1] if g["models"][i]["mean"] is not None]
        if not per:
            continue
        low, g = min(per, key=lambda t: t[0])
        if low >= 1:
            lines.append(f"{model['name']}: 모든 패턴에서 반복 평균 100%.")
        else:
            m = g["models"][i]
            lines.append(f"{model['name']}: 반복 평균 탐지율이 가장 낮은 패턴은 {g['label']} "
                         f"({fmt_pct(low)}, 평균 {fmt_num(m['mean_detected'])}/{g['injected']}).")
    lines.append(PRINCIPLE)
    return lines


def facts_html(lines: list[str]) -> str:
    items = "".join(f"<p>{esc(t)}</p>" for t in lines)
    return f'<div class="spc-facts"><div class="spc-label">수치로 본 사실</div>{items}</div>'


def error_counts_html(kpi: dict) -> str:
    """AI 오류 유형별 개수 (자동 집계): 검증기·채점기가 센 값만. 사람이 붙인 분류는 쓰지 않는다."""
    parts = ['<div class="spc-box-head"><b>AI 오류 유형별 개수</b><span class="b-auto">자동 집계</span>'
             '<span class="spc-note">검증기(설명)와 채점기(단독 판정)가 센 값</span></div>']
    e = kpi["explain"]
    if e:
        io = e["issue_outputs"]
        parts.append(f'<div class="spc-count-group">설명 LLM · {esc(e["model"])} · 출력 {e["outputs"]}개</div>')
        for label, n in (("JSON 형식 위반", io["format"]), ("원인표 밖 원인", io["cause"]),
                         ("판정 불일치", io["mismatch"]), ("호출 오류", e["call_errors"]),
                         ("반복 간 1순위·순서 차이 (시리즈)", e["repeat_changed_series"])):
            parts.append(f'<div class="spc-count"><span>{label}</span><b>{n}</b></div>')
    for m in kpi["models"]:
        parts.append(f'<div class="spc-count-group">단독 판정 · {esc(m["name"])} · {m["repeats"]}회 합계</div>')
        for label, n in (("놓친 심은 이상", m["missed_total"]), (f'{term("오탐")} 사건 (정답과 겹치지 않음)', m["false_total"]),
                         ("패턴 혼동", m["confusions_total"]), ("JSON 형식 위반", m["format_violations"]),
                         ("호출 오류", m["call_errors"])):
            parts.append(f'<div class="spc-count"><span>{label}</span><b>{n}</b></div>')
    parts.append(f'<div class="spc-note">오탐은 심은 이상(정답)과 겹치지 않는 경보다. 규칙 정의를 실제로 만족하는 자연 발생 경보도 '
                 f'포함하며, 같은 기준으로 규칙 엔진은 {kpi["rule"]["false_events"]}건이다.</div>')
    return "".join(parts)


NOTES_HEAD_HTML = ('<div class="spc-box-head"><b>사례 해설</b><span class="b-manual">수동 분석</span>'
                   '<span class="spc-note">자동 집계가 아닙니다. docs/ai_errors.md의 오답 원문을 읽고 대표 사례를 골라 쓴 해설입니다.</span></div>')


def explain_error_cases(explanations: dict, limit: int = 8) -> list[dict]:
    """저장된 설명 출력 중 검증에서 문제가 나온 것 (실제 결과 파일만 쓴다)."""
    cases = []
    for sid, entry in (explanations.get("series") or {}).items():
        events = entry.get("input", {}).get("events", [])
        described = " · ".join(
            f'{SYMBOL.get(FROM_KOREAN.get(e["pattern"]), "")} {e["pattern"]} {span_text(e["start"], e["end"])}'
            for e in events)
        for r in entry.get("runs", []):
            if r.get("error") is None and r.get("issues"):
                cases.append({
                    "series": str(sid),
                    "run": r["run"] + 1,
                    "input": described,
                    "excerpt": (r.get("text") or "").replace("\n", " ")[:140],
                    "types": ", ".join(sorted({ISSUE_KO[i["type"]] for i in r["issues"]})),
                    "detail": "; ".join(i["detail"] for i in r["issues"])[:220],
                })
    cases.sort(key=lambda c: (int(c["series"]), c["run"]))
    return cases[:limit]


def cases_html(cases: list[dict], e: dict | None) -> str:
    """설명 LLM 오답 목록 (자동 추출). '수정 후' 열은 두지 않는다 (수정 이력은 docs/ai_errors.md)."""
    total = e["outputs"] if e else 0
    bad = e["outputs"] - e["passed"] - e["call_errors"] if e else 0
    head = ('<div class="spc-cases-head">'
            f'<span>검증에서 문제가 나온 설명 출력 {bad}개 / 전체 {total}개 · 최대 8개 표시 · 전체 기록은 docs/ai_errors.md</span></div>')
    if not cases:
        return head + '<div class="spc-cases-empty">검증에서 문제가 나온 설명 출력이 없습니다.</div>'
    rows = ['<div class="spc-case-row th"><span>#</span><span>입력 사건 (규칙 판정)</span><span>AI 출력 발췌</span><span>무엇이 틀렸나</span></div>']
    for n, c in enumerate(cases, start=1):
        rows.append(f'<div class="spc-case-row"><span class="spc-mono">{n:02d}</span>'
                    f'<span>시리즈 {esc(c["series"])} · {c["run"]}회차<small>{esc(c["input"])}</small></span>'
                    f'<span class="spc-quote">{esc(c["excerpt"])}</span>'
                    f'<span><b>{esc(c["types"])}</b><small>{esc(c["detail"])}</small></span></div>')
    return head + "".join(rows)
