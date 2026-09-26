# SPC 설명기 화면: 한 페이지 스토리형 (머리말 → 01 문제 → 02 규칙 판정 → 03 AI 설명 → 04 검증 → 05 실데이터 → 06 한계).
# 판정은 규칙 엔진, 설명은 LLM(저장된 결과 우선, 실시간 호출은 횟수 제한).
# 시리즈·센서를 고르면 st.fragment로 감싼 그 섹션만 다시 그린다. 결과 파일 읽기와 SECOM 계산은 캐시한다.
import json
import os
from datetime import date, datetime

import streamlit as st

from spc_explainer import checklist, config, explain, feedback, generator, llm_client, rules, secom
from spc_explainer import ui_dashboard, ui_html, ui_steps
from spc_explainer.charts import chart_footer_html, chart_header_html, control_chart
from spc_explainer.patterns import KOREAN

st.set_page_config(page_title="SPC 설명기", layout="wide")

# 배포 환경: Streamlit Secrets의 키를 환경변수로 옮긴다 (로컬은 llm_client가 .env를 읽는다)
try:
    if "OPENAI_API_KEY" in st.secrets and not os.environ.get("OPENAI_API_KEY"):
        os.environ["OPENAI_API_KEY"] = st.secrets["OPENAI_API_KEY"]
except Exception:  # secrets.toml이 없는 로컬 실행
    pass


@st.cache_data
def load_json(path):
    """JSON 파일을 읽는다. 없으면 None."""
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


@st.cache_data
def load_text(path):
    return path.read_text(encoding="utf-8") if path.exists() else None


@st.cache_data
def secom_sensors(path) -> list[str]:
    """SECOM CSV의 센서 열 이름. 파일이 없으면 빈 목록."""
    df = secom.load(path)
    return [] if df is None else [c for c in df.columns if c.startswith("sensor_")]


@st.cache_data
def secom_view(path, sensor: str):
    """센서 하나의 값·라벨·Phase I 한계·Phase II 알람·불량 겹침. 같은 파일·센서면 다시 계산하지 않는다."""
    df = secom.load(path)
    values, labels = df[sensor].tolist(), df["label"].tolist()
    limits, alarms = secom.monitor(values)
    return values, labels, limits, alarms, secom.overlap_summary(alarms, labels)


@st.cache_resource
def daily_counter() -> dict:
    """서버 프로세스 전체가 공유하는 오늘의 실시간 호출 수 (앱이 재시작되면 초기화)."""
    return {"date": date.today(), "n": 0}


def series_label(s: dict) -> str:
    kinds = [KOREAN[a["pattern"]] for a in s["anomalies"]]
    kind_text = "정상 (심은 이상 없음)" if not kinds else "심은 이상: " + ", ".join(kinds)
    return f"시리즈 {s['id']:02d} — {kind_text}"


def render_ai_card(sid: int, values, events, selected: str | None = None) -> dict | None:
    """AI 설명 카드: 설명(실시간 결과가 있으면 그것, 없으면 저장된 1회차) + 검증 배지 + 저장 상태·실시간 설명 버튼.
    보여준 설명을 체크리스트용으로 돌려준다 (없으면 None)."""
    model = config.EXPLAIN_MODEL
    inp = explain.build_input(values, events)
    saved = load_json(config.EXPLANATIONS_PATH) or {}
    cached = (saved.get("series") or {}).get(str(sid))
    runs = cached.get("runs", []) if cached else []
    live = st.session_state.get("live")
    reply = live[1] if live and live[0] == sid else None

    if reply is not None:
        text, error, shown_inp = reply.text, reply.error, inp
        status = f"실시간 결과 · {model['name']} · {reply.latency_s:.1f}초"
        source = "실시간 설명"
    elif runs:
        text, error, shown_inp = runs[0]["text"], runs[0]["error"], cached["input"]
        created = str(runs[0].get("created", "")).replace("T", " ")[:16]
        status = f"저장된 설명 · {created} 생성 · 같은 입력 {len(runs)}회 중 1회차"
        source = "저장된 설명 1회차"
    else:
        text, error, shown_inp = None, None, None
        status = "저장된 설명 없음"

    ai = None
    if shown_inp is None or error:
        st.html(ui_steps.ai_head_html(None))
        with st.container(key="ai_body"):
            if error:
                st.error(f"호출 오류: {error}")
            else:
                st.info("저장된 설명이 없습니다. `python scripts/run_experiment.py`로 만들 수 있습니다.")
    else:
        data, issues = explain.validate(text, shown_inp)
        names = ", ".join(sorted({explain.ISSUE_KO[i["type"]] for i in issues}))
        ai = {"data": data if isinstance(data, dict) else None, "inp": shown_inp, "model": model["name"],
              "ok": not issues and shown_inp == inp,  # 저장된 입력이 지금 판정과 다르면 순서를 쓰지 않는다
              "status": ("검증 통과" if not issues else f"검증 문제: {names}") + f" · {source}"}
        st.html(ui_steps.ai_head_html(issues))
        if issues:
            st.html(ui_steps.issues_html(issues))
        if isinstance(data, dict):
            st.html(ui_steps.ai_body_html(data, shown_inp, selected))
        else:
            with st.container(key="ai_body"):
                st.code(text or "", language="json")
    if cached and cached.get("input") != inp:
        with st.container(key="ai_warn"):
            st.warning("저장된 설명의 입력이 현재 규칙 판정과 다릅니다. 실험을 다시 돌려야 합니다.")

    # 실시간 설명: 세션당·하루 호출 수를 제한하고, 키가 없으면 끈다
    counter = daily_counter()
    if counter["date"] != date.today():
        counter.update(date=date.today(), n=0)
    used = st.session_state.get("live_used", 0)
    left = max(0, min(config.LIVE_CALLS_PER_SESSION - used, config.LIVE_CALLS_PER_DAY - counter["n"]))
    has_key = bool(llm_client.get_api_key())
    if not has_key:
        limit_text = "API 키 없음 — 실시간 설명 꺼짐"
    elif left == 0:
        limit_text = "실시간 호출 한도 소진"
    else:
        limit_text = f"남은 횟수 {left}/{config.LIVE_CALLS_PER_SESSION}"
    with st.container(key="ai_foot"):
        info_col, button_col = st.columns([3, 1.3], vertical_alignment="center")
        with info_col:
            st.html(ui_steps.status_html(f"{status} · {limit_text}"))
        with button_col:
            can_call = has_key and left > 0
            clicked = st.button("실시간 설명 받기" if can_call else "실시간 설명 불가", key="live_button",
                                disabled=not can_call, width="stretch")
    if clicked:
        st.session_state["live_used"] = used + 1
        counter["n"] += 1
        with st.spinner("LLM 호출 중…"):
            st.session_state["live"] = (sid, llm_client.call_json(model, *explain.build_messages(inp)))
        # 앱 전체를 다시 그려 위 카드에 결과를 띄운다. scope="fragment"는 클릭이 전체 재실행으로 들어오면 예외가 난다
        st.rerun()
    if runs:
        with st.container(key="ai_runs"), st.expander(f"같은 입력 {len(runs)}회 반복 결과 (저장된 설명)"):
            for r in runs:
                if r["error"]:
                    st.html(ui_steps.run_line_html(r["run"] + 1, "호출 오류", None))
                    continue
                data, issues = explain.validate(r["text"], cached["input"])
                state = ", ".join(sorted({explain.ISSUE_KO[i["type"]] for i in issues})) if issues else "검증 통과"
                items = ui_steps.priority_items(data, cached["input"]) if isinstance(data, dict) else []
                st.html(ui_steps.run_line_html(r["run"] + 1, state, items))
    return ai


def toggle_feedback(series: str, event_id: str, pattern: str, span: str, rule: str) -> None:
    """'오탐이에요' 버튼: 누르면 세션 목록에 넣고, 다시 누르면 뺀다."""
    entry = {"series": series, "event_id": event_id, "pattern": pattern, "span": span, "rule": rule,
             "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    st.session_state["feedback"] = feedback.toggle(st.session_state.get("feedback", []), entry)


def render_checklist(scope: str, title: str, events, values, limits: dict | None, ai: dict | None,
                     picked: int | None = None, feedback_series: str | None = None) -> None:
    """지금 확인할 것: 사건마다 원인표 항목 체크박스 + 교대 인수인계 메모(.md 내려받기·복사).
    항목은 원인표에서만 온다. 검증을 통과한 AI 설명이 있으면 그 점검 순서를 앞에 둔다.
    feedback_series를 주면 사건마다 '오탐이에요' 버튼을 붙인다."""
    order = checklist.ai_order(ai["data"], ai["inp"]) if ai and ai["ok"] else {}
    cards = checklist.build(events, values, limits, order)
    st.html(ui_steps.check_head_html(ai is not None, bool(order)))
    checked = set()
    for i, card in enumerate(cards):
        with st.expander(f"{card['title']} — {card['rule']}", expanded=i == picked):
            for it in card["items"]:
                if st.checkbox(checklist.item_label(it), key=f"chk_{scope}_{card['event_id']}_{it['cause_id']}"):
                    checked.add((card["event_id"], it["cause_id"]))
            if feedback_series:
                pattern, span = KOREAN[card["pattern"]], card["title"].rsplit(" ", 1)[-1]
                flagged = feedback.is_flagged(st.session_state.get("feedback", []), feedback_series, pattern, span)
                if flagged:
                    st.html('<div class="spc-flag">✓ 오탐으로 표시했습니다 (이번 세션에만 저장)</div>')
                st.button("오탐 표시 취소" if flagged else "오탐이에요", key=f"fb_{scope}_{card['event_id']}",
                          help=feedback.DEMO_NOTE, on_click=toggle_feedback,
                          args=(feedback_series, card["event_id"], pattern, span, card["rule"]))
    ai_meta = None
    if ai and ai["data"]:
        ai_meta = {"model": ai["model"], "status": ai["status"], "summary": ai["data"].get("summary", "")}
    memo = checklist.handover_md(title, datetime.now().strftime("%Y-%m-%d %H:%M"), cards, checked, ai_meta)
    st.download_button("인수인계 메모 내려받기 (.md)", memo, file_name=f"spc_handover_{scope}.md",
                       mime="text/markdown", on_click="ignore", key=f"memo_{scope}")
    with st.expander("메모를 텍스트로 보기·복사 (오른쪽 위 복사 버튼)"):
        st.code(memo, language="markdown")


def render_feedback_list() -> None:
    """이번 세션에 모은 '오탐이에요' 피드백 목록과 CSV 내려받기. 외부에 저장하지 않는다."""
    entries = st.session_state.get("feedback", [])
    st.html(f'<div class="spc-box-head"><b>오탐 피드백</b><span class="b-manual">시연용</span>'
            f'<span class="spc-note">{ui_html.esc(feedback.DEMO_NOTE)} · 이번 세션에만 모으고 저장하지 않습니다.</span></div>')
    if not entries:
        st.caption("아직 없습니다. 위 사건 항목을 펼쳐 '오탐이에요'를 누르면 여기에 모입니다.")
        return
    st.dataframe(feedback.table(entries), hide_index=True, width="stretch")
    st.download_button(f"피드백 {len(entries)}건 CSV 내려받기", feedback.to_csv(entries).encode("utf-8-sig"),
                       file_name="spc_feedback.csv", mime="text/csv", on_click="ignore", key="feedback_csv")


def close_guide() -> None:
    st.session_state["guide_closed"] = True


def guide(dataset: dict) -> None:
    """첫 방문 30초 가이드. 닫으면 이 세션 동안 다시 보이지 않는다 (콜백이 먼저 돌아 닫은 실행에서 바로 사라진다)."""
    if st.session_state.get("guide_closed"):
        return
    n_normal = sum(1 for s in dataset["series"] if not s["anomalies"])
    with st.container(key="guide_card"):
        st.html(ui_html.guide_html(n_normal, len(dataset["series"]) - n_normal))
        st.button("가이드 닫기", key="guide_close", on_click=close_guide)


@st.fragment
def series_sections(dataset: dict) -> None:
    """02 규칙 판정 + 03 AI 설명. 시리즈를 바꾸면 이 두 섹션만 다시 그린다."""
    series = dataset["series"]
    st.html(ui_html.section_html("02 규칙 판정", "통계 규칙이 이상 구간을 확정합니다",
                                 "Nelson Rules 기반 · 결정적 계산 — 동일 입력이면 항상 동일 결과"))
    pick_col, truth_col = st.columns([3, 1], vertical_alignment="bottom")
    with pick_col:
        sid = st.selectbox("시리즈 선택", range(len(series)), format_func=lambda i: series_label(series[i]))
    with truth_col:
        show_truth = st.toggle("정답(심은 이상) 구간 표시", value=False)
    s = series[sid]
    values = s["values"]
    events = rules.detect(values)
    truth = generator.truth_events(s) if show_truth else None
    pick_key, seen_key, out_key = f"pick_{sid:02d}", f"seen_{sid:02d}", f"outside_{sid:02d}"
    with st.container(key="chart_card"):
        st.html(chart_header_html(values, f"관리도 · {config.PROCESS_NAME} ({config.UNIT})", show_truth))
        fig = control_chart(values, events, dataset["center"], dataset["ucl"], dataset["lcl"],
                            truth=truth, show_legend=False)
        state = st.plotly_chart(fig, width="stretch", config={"displayModeBar": False}, key=f"chart_{sid:02d}",
                                on_select="rerun", selection_mode="points")
        st.html(chart_footer_html(show_truth))
        # 점을 누르면 그 점이 속한 사건을 고른다. 새로 누른 점일 때만 반영해서, 드롭다운으로 바꾼 선택을 덮지 않는다
        x = ui_steps.selected_x(state)
        if x != st.session_state.get(seen_key):
            st.session_state[seen_key] = x
            if x is not None:
                idx = ui_steps.event_index_at(events, x)
                st.session_state[pick_key] = ui_steps.NO_PICK if idx is None else idx
                st.session_state[out_key] = x if idx is None else None
        picked = None
        if events:  # 터치 화면에서 점 누르기가 안 될 때를 위한 대체 수단
            choice = st.selectbox("사건 선택 — 관리도의 점을 눌러도 됩니다 (휴대폰은 여기서 고르세요)",
                                  [ui_steps.NO_PICK] + list(range(len(events))), key=pick_key,
                                  format_func=lambda i: ui_steps.event_option(events, i),
                                  on_change=lambda: st.session_state.update({out_key: None}))
            picked = None if choice == ui_steps.NO_PICK else choice
        note = ui_steps.pick_note_html(events, picked, st.session_state.get(out_key))
        if note:
            st.html(note)
    with st.container(key="rule_card"):
        st.html(ui_steps.rule_card_html(events, values, selected=picked))

    st.html(ui_html.section_html("03 AI 설명", "규칙 판정 결과를 받아 AI가 설명합니다",
                                 "AI는 새로운 판정을 만들지 않습니다 · 규칙이 넘긴 구간·규칙 번호만 해설합니다", anchor="spc-ai"))
    with st.container(key="ai_card"):
        if events:
            ai = render_ai_card(sid, values, events, None if picked is None else f"E{picked + 1}")
        else:
            st.html(ui_steps.ai_head_html(None))
            with st.container(key="ai_body"):
                st.success("규칙 판정이 없어 LLM을 호출하지 않습니다.")
    if events:
        with st.container(key="check_card"):
            render_checklist(f"s{sid:02d}", series_label(s), events, values, None, ai, picked,
                             feedback_series=f"시리즈 {sid:02d}")
    with st.container(key="feedback_card"):
        render_feedback_list()


def verification_section(metrics: dict | None) -> None:
    """04 검증: 규칙 vs 모델별 LLM 단독 판정 KPI, 패턴별 탐지율, 오류 유형 자동 집계, 사례 해설(수동 분석)."""
    st.html(ui_html.section_html("04 검증", "AI가 판정까지 직접 하면 어떻게 될까", ui_dashboard.subtitle_text(metrics)))
    if not metrics:
        st.info("검증 결과가 아직 없습니다. `python scripts/run_experiment.py`로 만들 수 있습니다.")
        return
    kpi = ui_dashboard.kpi_summary(metrics)
    cols = st.columns(1 + len(kpi["models"]))
    with cols[0], st.container(key="kpi_rule"):
        st.html(ui_dashboard.kpi_rule_html(kpi["rule"]))
    for i, m in enumerate(kpi["models"]):
        with cols[i + 1], st.container(key=f"kpi_model_{i}"):
            st.html(ui_dashboard.kpi_model_html(m, kpi["rule"]["rate"]))
    with st.container(key="bars_card"):
        bars_col, facts_col = st.columns([2.6, 1])
        with bars_col:
            st.html(ui_dashboard.detection_bars_html(ui_dashboard.detection_groups(metrics)))
        with facts_col:
            st.html(ui_dashboard.facts_html(ui_dashboard.fact_lines(metrics)))
    counts_col, notes_col = st.columns([1, 1.5])
    with counts_col, st.container(key="counts_card"):
        st.html(ui_dashboard.error_counts_html(kpi))
    with notes_col, st.container(key="notes_card"):
        st.html(ui_dashboard.NOTES_HEAD_HTML)
        notes = load_text(config.CASE_NOTES_PATH)
        if notes:
            st.markdown(notes)
        else:
            st.caption("사례 해설이 아직 없습니다 (docs/case_notes.md).")
    explanations = load_json(config.EXPLANATIONS_PATH) or {}
    with st.expander("설명 LLM 오답 목록 (자동 추출)"):
        st.html(ui_dashboard.cases_html(ui_dashboard.explain_error_cases(explanations), kpi["explain"]))


@st.fragment
def secom_section() -> None:
    """05 실데이터 확인. 센서를 바꾸면 이 섹션만 다시 그린다."""
    st.html(ui_html.section_html(
        "05 실데이터 확인", "가상 데이터만으로 만든 건 아닙니다",
        f"공개 반도체 공정 데이터(UCI SECOM) 센서에 같은 규칙 엔진을 적용했습니다. 시간순 앞 {config.SECOM_PHASE1_N}점으로 "
        "한계를 추정하고 나머지를 감시합니다. 정답이 없어 탐지율은 계산하지 않습니다."))
    sensors = secom_sensors(config.SECOM_PATH)
    if not sensors:
        st.info("SECOM 데이터가 없습니다. `python scripts/fetch_secom.py`로 받을 수 있습니다.")
        return
    with st.container(key="secom_card"):
        sensor = st.selectbox("센서", sensors)
        values, labels, limits, alarms, overlap = secom_view(config.SECOM_PATH, sensor)
        fail_idx = [i for i, v in enumerate(labels) if v == 1]
        fig = control_chart(values, alarms, limits["center"], limits["ucl"], limits["lcl"],
                            phase_boundary=config.SECOM_PHASE1_N, fail_idx=fail_idx, y_title=sensor)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        c1, c2, c3 = st.columns(3)
        c1.metric("Phase II 알람 사건", overlap["events"])
        c2.metric("불량이 포함된 알람 사건", overlap["events_with_fail"])
        c3.metric("알람 점 중 불량 비율", ui_dashboard.fmt_pct(overlap["fail_rate_flagged"]),
                  help=f"Phase II 전체 불량 비율 {ui_dashboard.fmt_pct(overlap['fail_rate_phase2'])}")
        st.caption("불량 라벨과의 겹침은 관찰일 뿐 인과나 성능이 아닙니다. 데이터: UCI SECOM (McCann & Johnston, 2008), CC BY 4.0.")


dataset = load_json(config.SERIES_PATH) or generator.generate_dataset()
metrics = load_json(config.METRICS_PATH)
st.html(ui_html.CSS)
st.html(ui_html.hero_html(dataset["center"], dataset["ucl"], dataset["lcl"], config.UNIT))
guide(dataset)
st.html(ui_html.PROBLEM_HTML)
series_sections(dataset)
verification_section(metrics)
secom_section()
st.html(ui_html.limits_html(metrics))
report_md = load_text(config.REPORT_PATH)
if report_md:
    with st.expander("전체 검증 리포트 (docs/validation_report.md)"):
        st.markdown(report_md)
