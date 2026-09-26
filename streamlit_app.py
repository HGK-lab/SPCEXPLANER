# SPC 설명기 화면: 한 페이지 스토리형
# (머리말·가이드 → 01 문제 → 02 규칙 판정 → 03 AI 설명 → 04 검증 → 05 실데이터 → 06 내 데이터 판정 → 07 한계).
# 판정은 규칙 엔진, 설명은 LLM(저장된 결과 우선, 실시간 호출은 횟수 제한).
# 시리즈·센서·올린 데이터를 바꾸면 st.fragment로 감싼 그 섹션만 다시 그린다. 결과 파일 읽기와 SECOM 계산은 캐시한다.
import hashlib
import json
import os
from datetime import date, datetime

import streamlit as st

from spc_explainer import checklist, config, explain, feedback, generator, llm_client, rules, secom, upload
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


def live_quota() -> tuple[bool, int, str]:
    """실시간 설명을 부를 수 있는지: (키 있음, 남은 횟수, 안내 글자). 세션당·하루 한도는 03과 06이 같이 쓴다."""
    counter = daily_counter()
    if counter["date"] != date.today():
        counter.update(date=date.today(), n=0)
    used = st.session_state.get("live_used", 0)
    left = max(0, min(config.LIVE_CALLS_PER_SESSION - used, config.LIVE_CALLS_PER_DAY - counter["n"]))
    has_key = bool(llm_client.get_api_key())
    if not has_key:
        return has_key, left, "API 키 없음 — 실시간 설명 꺼짐"
    if left == 0:
        return has_key, left, "실시간 호출 한도 소진"
    return has_key, left, f"남은 횟수 {left}/{config.LIVE_CALLS_PER_SESSION}"


def spend_live_call() -> None:
    st.session_state["live_used"] = st.session_state.get("live_used", 0) + 1
    daily_counter()["n"] += 1


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
    has_key, left, limit_text = live_quota()
    with st.container(key="ai_foot"):
        info_col, button_col = st.columns([3, 1.3], vertical_alignment="center")
        with info_col:
            st.html(ui_steps.status_html(f"{status} · {limit_text}"))
        with button_col:
            can_call = has_key and left > 0
            clicked = st.button("실시간 설명 받기" if can_call else "실시간 설명 불가", key="live_button",
                                disabled=not can_call, width="stretch")
    if clicked:
        spend_live_call()
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


def toggle_feedback(series: str, event_id: str, pattern: str, span: str, rule: str, refresh_all: bool = False) -> None:
    """'오탐이에요' 버튼: 누르면 세션 목록에 넣고, 다시 누르면 뺀다.
    refresh_all: 목록이 다른 fragment(03)에 있을 때 앱 전체를 다시 그리라고 표시한다 (06에서 누른 경우)."""
    st.session_state["feedback_refresh"] = refresh_all
    entry = {"series": series, "event_id": event_id, "pattern": pattern, "span": span, "rule": rule,
             "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    st.session_state["feedback"] = feedback.toggle(st.session_state.get("feedback", []), entry)


def render_checklist(scope: str, title: str, events, values, limits: dict | None, ai: dict | None,
                     picked: int | None = None, feedback_series: str | None = None, feedback_refresh_all: bool = False) -> None:
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
                          args=(feedback_series, card["event_id"], pattern, span, card["rule"], feedback_refresh_all))
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


def render_upload_ai(values, events, limits: dict) -> dict | None:
    """06의 AI 설명: 저장된 설명이 없어 실시간으로만 부른다 (호출 한도는 03과 같이 쓴다). 체크리스트용 설명을 돌려준다."""
    model = config.EXPLAIN_MODEL
    inp = explain.build_input(values, events, limits)
    sig = hashlib.sha256(json.dumps(inp, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    with st.container(key="up_ai_foot"):
        has_key, left, _ = live_quota()
        if st.button("AI 설명 받기 (실시간)" if has_key and left > 0 else "AI 설명 불가", key="up_live_button",
                     disabled=not (has_key and left > 0)):
            spend_live_call()
            with st.spinner("LLM 호출 중…"):
                st.session_state["up_live"] = (sig, llm_client.call_json(model, *explain.build_messages(inp)))
            st.rerun()  # 03과 06의 남은 횟수·버튼을 함께 갱신한다 (이 fragment만 다시 그리면 03이 옛 숫자로 남는다)
        st.html(ui_steps.status_html(f"누르면 판정 요약(사건 구간·값)만 {model['name']}에 보냅니다 · {live_quota()[2]}"))
    live = st.session_state.get("up_live")
    reply = live[1] if live and live[0] == sig else None  # 데이터·한계를 바꾸면 이전 설명은 쓰지 않는다
    if reply is None:
        return None
    if reply.error:
        with st.container(key="up_ai_msg"):
            st.error(f"호출 오류: {reply.error}")
        return None
    data, issues = explain.validate(reply.text, inp)
    st.html(ui_steps.ai_head_html(issues))
    if issues:
        st.html(ui_steps.issues_html(issues))
    if not isinstance(data, dict):
        with st.container(key="up_ai_msg"):
            st.code(reply.text or "", language="json")
        return None
    st.html(ui_steps.ai_body_html(data, inp))
    names = ", ".join(sorted({explain.ISSUE_KO[i["type"]] for i in issues}))
    return {"data": data, "inp": inp, "model": model["name"], "ok": not issues,
            "status": ("검증 통과" if not issues else f"검증 문제: {names}") + " · 실시간 설명"}


@st.fragment
def upload_section(dataset: dict) -> None:
    """06 내 데이터 판정: CSV 올리기·붙여넣기 → 같은 규칙 엔진. 파일은 저장하지 않고, 결과는 04 검증 수치에 섞지 않는다."""
    st.html(ui_html.section_html(
        "06 내 데이터로 판정", "내 관리도 데이터에 같은 규칙을 돌려 봅니다",
        f"숫자 열 1개(막 두께, 앞에 시점 열은 선택) · 최대 {upload.MAX_ROWS:,}행 · 결과는 04 검증 수치에 섞지 않습니다"))
    with st.container(key="upload_card"):
        st.html(ui_html.UPLOAD_NOTE_HTML)
        file_col, paste_col = st.columns(2)
        with file_col:
            file = st.file_uploader("CSV 파일 올리기", type=["csv", "txt"], max_upload_size=1, key="up_file")
            st.download_button("예시 CSV 내려받기 (가상 시리즈 11)", upload.example_csv(dataset["series"][11]["values"]),
                               file_name="spc_example.csv", mime="text/csv", on_click="ignore", key="up_example")
        with paste_col:
            pasted = st.text_area("또는 붙여넣기 (엑셀에서 열을 복사해도 됩니다)", key="up_text", height=150, max_chars=200_000,
                                  placeholder="시점,막두께_nm\n2026-09-01 08:00,100.21\n2026-09-01 08:30,99.87")
        try:
            text = upload.read_input(file.getvalue() if file is not None else None, pasted)
            if text is None:
                st.caption("CSV를 올리거나 붙여넣으면 여기서 판정합니다. 예시 CSV를 내려받아 그대로 올려 봐도 됩니다.")
                return
            parsed = upload.parse(text)
            values = parsed["values"]
            n = len(values)
            mode = st.radio("관리한계 정하기", ["앞 N점으로 추정 (Phase I)", "직접 입력"], horizontal=True, key="up_mode")
            if mode == "직접 입력":
                cl_col, ucl_col, lcl_col = st.columns(3)
                center = cl_col.number_input("중심선 (CL)", value=config.CENTER, key="up_cl")
                ucl = ucl_col.number_input("UCL", value=config.UCL, key="up_ucl")
                lcl = lcl_col.number_input("LCL", value=config.LCL, key="up_lcl")
                result = upload.judge_fixed(values, center, ucl, lcl)
            elif n < upload.MIN_PHASE1 + upload.MIN_ROWS:
                result = upload.judge_estimated(values, upload.MIN_PHASE1)  # 행이 모자라다는 오류를 낸다
            else:
                phase1_n = st.number_input("추정에 쓸 앞 N점", min_value=upload.MIN_PHASE1, max_value=n - upload.MIN_ROWS,
                                           value=upload.default_phase1(n), step=10, key=f"up_n_{n}")
                result = upload.judge_estimated(values, int(phase1_n))
        except upload.UploadError as e:
            st.html(ui_html.error_html(str(e)))
            return
        limits, events = result["limits"], result["events"]
        times = parsed["times"]
        span = f" · 시점 {times[0]} ~ {times[-1]}" if times and times[0] and times[-1] else ""
        st.html(chart_header_html(values, f"관리도 · 내 데이터 ({parsed['name']}, {n:,}점{span})"))
        fig = control_chart(values, events, limits["center"], limits["ucl"], limits["lcl"],
                            phase_boundary=result["phase1_n"], y_title=parsed["name"], show_legend=False)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.html(ui_steps.upload_limits_html(result))
    with st.container(key="up_rule_card"):
        st.html(ui_steps.rule_card_html(events, values, limits))
    if events:
        with st.container(key="up_ai_card"):
            ai = render_upload_ai(values, events, limits)
        with st.container(key="up_check_card"):
            render_checklist("up", "내 데이터", events, values, limits, ai,
                             feedback_series=f"내 데이터 ({len(values):,}점)", feedback_refresh_all=True)
        if st.session_state.pop("feedback_refresh", False):
            st.rerun()  # 피드백 목록은 03(다른 fragment)에 있으므로 앱 전체를 다시 그린다


dataset = load_json(config.SERIES_PATH) or generator.generate_dataset()
metrics = load_json(config.METRICS_PATH)
st.html(ui_html.CSS)
st.html(ui_html.hero_html(dataset["center"], dataset["ucl"], dataset["lcl"], config.UNIT))
guide(dataset)
st.html(ui_html.PROBLEM_HTML)
series_sections(dataset)
verification_section(metrics)
secom_section()
upload_section(dataset)
st.html(ui_html.limits_html(metrics))
report_md = load_text(config.REPORT_PATH)
if report_md:
    with st.expander("전체 검증 리포트 (docs/validation_report.md)"):
        st.markdown(report_md)
