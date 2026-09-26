# SPC 설명기 화면: 한 페이지 스토리형 (머리말 → 01 문제 → 02 규칙 판정 → 03 AI 설명 → 06 한계).
# 판정은 규칙 엔진, 설명은 LLM(저장된 결과 우선, 실시간 호출은 횟수 제한).
# 시리즈를 고르면 st.fragment로 감싼 그 섹션만 다시 그린다. 결과 파일 읽기는 캐시한다.
import json
import os
from datetime import date

import streamlit as st

from spc_explainer import config, explain, generator, llm_client, rules
from spc_explainer import ui_html, ui_steps
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


@st.cache_resource
def daily_counter() -> dict:
    """서버 프로세스 전체가 공유하는 오늘의 실시간 호출 수 (앱이 재시작되면 초기화)."""
    return {"date": date.today(), "n": 0}


def series_label(s: dict) -> str:
    kinds = [KOREAN[a["pattern"]] for a in s["anomalies"]]
    kind_text = "정상 (심은 이상 없음)" if not kinds else "심은 이상: " + ", ".join(kinds)
    return f"시리즈 {s['id']:02d} — {kind_text}"


def render_ai_card(sid: int, values, events) -> None:
    """AI 설명 카드: 설명(실시간 결과가 있으면 그것, 없으면 저장된 1회차) + 검증 배지 + 저장 상태·실시간 설명 버튼."""
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
    elif runs:
        text, error, shown_inp = runs[0]["text"], runs[0]["error"], cached["input"]
        created = str(runs[0].get("created", "")).replace("T", " ")[:16]
        status = f"저장된 설명 · {created} 생성 · 같은 입력 {len(runs)}회 중 1회차"
    else:
        text, error, shown_inp = None, None, None
        status = "저장된 설명 없음"

    if shown_inp is None or error:
        st.html(ui_steps.ai_head_html(None))
        with st.container(key="ai_body"):
            if error:
                st.error(f"호출 오류: {error}")
            else:
                st.info("저장된 설명이 없습니다. `python scripts/run_experiment.py`로 만들 수 있습니다.")
    else:
        data, issues = explain.validate(text, shown_inp)
        st.html(ui_steps.ai_head_html(issues))
        if issues:
            st.html(ui_steps.issues_html(issues))
        if isinstance(data, dict):
            st.html(ui_steps.ai_body_html(data, shown_inp))
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
                    st.markdown(f"**{r['run'] + 1}회차** · 호출 오류")
                    continue
                data, issues = explain.validate(r["text"], cached["input"])
                state = ", ".join(sorted({explain.ISSUE_KO[i["type"]] for i in issues})) if issues else "검증 통과"
                items = ui_steps.priority_items(data, cached["input"]) if isinstance(data, dict) else []
                order_text = " → ".join(f"{it['event_id']}:{it['cause_id']}" for it in items) or "-"
                st.markdown(f"**{r['run'] + 1}회차** · {state} · 점검 순서 {order_text}")


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
    with st.container(key="chart_card"):
        st.html(chart_header_html(values, f"관리도 · {config.PROCESS_NAME} ({config.UNIT})", show_truth))
        fig = control_chart(values, events, dataset["center"], dataset["ucl"], dataset["lcl"],
                            truth=truth, show_legend=False)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.html(chart_footer_html(show_truth))
    with st.container(key="rule_card"):
        st.html(ui_steps.rule_card_html(events, values))

    st.html(ui_html.section_html("03 AI 설명", "규칙 판정 결과를 받아 AI가 설명합니다",
                                 "AI는 새로운 판정을 만들지 않습니다 · 규칙이 넘긴 구간·규칙 번호만 해설합니다"))
    with st.container(key="ai_card"):
        if events:
            render_ai_card(sid, values, events)
        else:
            st.html(ui_steps.ai_head_html(None))
            with st.container(key="ai_body"):
                st.success("규칙 판정이 없어 LLM을 호출하지 않습니다.")


dataset = load_json(config.SERIES_PATH) or generator.generate_dataset()
metrics = load_json(config.METRICS_PATH)
st.html(ui_html.CSS)
st.html(ui_html.hero_html(dataset["center"], dataset["ucl"], dataset["lcl"], config.UNIT))
st.html(ui_html.PROBLEM_HTML)
series_sections(dataset)
st.html(ui_html.limits_html(metrics))
report_md = load_text(config.REPORT_PATH)
if report_md:
    with st.expander("전체 검증 리포트 (docs/validation_report.md)"):
        st.markdown(report_md)
