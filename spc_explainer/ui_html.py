# 화면 공통 조각: 패턴 색·기호·규칙 번호, 전역 CSS, 스토리형 페이지의 머리말·섹션 제목·01 문제·06 한계.
# 스타일 출처: Claude Design 2A(데스크톱 스토리형)·2B(모바일) 시안. LLM이 만든 문자열은 반드시 esc()를 거쳐 넣는다
# (st.html은 iframe 없이 페이지에 바로 들어간다).
import html

PATTERN_COLORS = {
    "spike": {"fill": "#d02c2a", "text": "#b7191c"},
    "trend": {"fill": "#c5770f", "text": "#915200"},
    "shift": {"fill": "#8048b6", "text": "#703ba1"},
}
SYMBOL = {"spike": "◆", "trend": "▲", "shift": "■"}
RULE_ID = {"spike": "R1", "shift": "R2", "trend": "R3"}  # Nelson 규칙 번호


def esc(text) -> str:
    """HTML 특수문자를 이스케이프한다."""
    return html.escape(str(text), quote=True)


def span_text(start: int, end: int) -> str:
    """구간 표기: #14 또는 #45–52 (점 번호는 0부터)."""
    return f"#{start}" if start == end else f"#{start}–{end}"


def hero_html(center: float, ucl: float, lcl: float, unit: str) -> str:
    """머리말: 한 문장 원칙 + ① 규칙 판정 → ② AI 설명 → ③ 검증 흐름 + 관리 기준과 고정 한계 가정."""
    return (
        '<div class="spc-hero">'
        '<div class="spc-brand"><span class="spc-mark"><i></i></span>SPC 설명기</div>'
        "<h1>관리도 이상, 판정은 규칙이 하고 설명은 AI가 합니다</h1>"
        '<p class="spc-lead">관리도 시계열이 주어지면 통계 규칙이 이상 구간을 판정하고, AI는 그 판정 결과만 받아 '
        "“어떤 패턴인지 · 무엇부터 점검할지”를 한국어로 설명합니다.</p>"
        '<div class="spc-flow3">'
        '<div class="spc-f rule"><b>① 규칙 판정</b><span>통계 규칙이 이상 여부 확정</span></div>'
        '<span class="spc-arr">→</span>'
        '<div class="spc-f ai"><b>② AI 설명</b><span>판정 결과를 한국어로 해설</span></div>'
        '<span class="spc-arr">→</span>'
        '<div class="spc-f ver"><b>③ 검증</b><span>AI 단독 판정과 같은 기준으로 비교</span></div>'
        "</div>"
        f'<div class="spc-top"><span>관리 기준 <b>CL {center:.1f}</b> · <b>UCL {ucl:.1f}</b> · <b>LCL {lcl:.1f}</b> {esc(unit)}</span>'
        '<span class="spc-note">관리한계 고정값 사용 = 이미 안정화된 공정을 감시하는 상황을 가정</span></div>'
        "</div>"
    )


def section_html(kicker: str, title: str, sub: str = "") -> str:
    """섹션 머리: 번호·이름(작게) + 제목 + 한 줄 설명."""
    sub_html = f'<p class="spc-sec-sub">{esc(sub)}</p>' if sub else ""
    return f'<div class="spc-sec"><span class="spc-kicker">{esc(kicker)}</span><h2>{esc(title)}</h2>{sub_html}</div>'


PROBLEM_HTML = section_html("01 문제 상황", "엔지니어는 관리도를 보고, 경험으로 우선순위를 정한다") + (
    '<p class="spc-para">관리도에서 이상 신호가 뜨면 엔지니어는 눈으로 패턴을 읽고 레시피 이력을 볼지 · 챔버 로그를 볼지 · '
    "계측기부터 의심할지를 그 자리에서 판단해야 합니다. 판정 기준은 문서로 정해져 있지만, 무엇부터 점검할지는 "
    "개인의 경험에 기대는 경우가 많습니다.</p>"
)


def limits_html(metrics: dict | None) -> str:
    """06 한계: 가상 데이터·원인표 가정·작은 표본·SECOM 관찰. 숫자는 지표 파일에서 읽는다."""
    if metrics:
        d = metrics["dataset"]
        sample = (f"검증 수치는 가상 시리즈 {d['n_series']}개 · 심은 이상 {sum(d['injected'].values())}건에서 잰 값이라 "
                  f"<b>표본이 작습니다</b> (지표 생성 {esc(metrics['generated_at'])}).")
    else:
        sample = "검증 결과 파일이 아직 없습니다."
    items = [
        "관리도 데이터는 규칙 정의대로 패턴을 심은 <b>가상 데이터</b>입니다. 실제 공정 데이터가 아닙니다.",
        "AI가 고르는 점검 원인표는 <b>교과서 수준의 일반 지식</b>에 기반한 가정이며, 실제 설비·레시피와 다를 수 있습니다.",
        sample,
        "SECOM은 정답이 없어 탐지율을 계산하지 않았고, 불량 라벨과의 겹침은 <b>관찰</b>일 뿐 인과나 성능이 아닙니다.",
    ]
    rows = "".join(f'<div class="spc-limit"><span>—</span><span>{t}</span></div>' for t in items)
    return section_html("06 한계", "정직하게 밝혀둘 것") + f'<div class="spc-limits">{rows}</div>'


CSS = """<style>
/* ── 카드: 키 달린 st.container에 Streamlit이 붙이는 st-key-* 클래스를 꾸민다 ── */
.st-key-chart_card, .st-key-bars_card, .st-key-counts_card, .st-key-secom_card, [class*="st-key-kpi_"] {
  background: #ffffff !important; border: 1px solid #d9dcdf !important; border-radius: 4px !important;
  padding: 16px 20px !important; gap: 8px !important;
}
.st-key-rule_card {
  background: #ffffff !important; border: 1px solid #16191d !important; border-radius: 4px !important;
  padding: 0 !important; gap: 0 !important; overflow: hidden;
}
.st-key-ai_card {
  background: #f7fbfe !important; border: 1px dashed #6da4d3 !important; border-radius: 4px !important;
  padding: 0 !important; gap: 0 !important; overflow: hidden;
}
.st-key-notes_card {
  background: #fffdf6 !important; border: 1px solid #e3d9bd !important; border-left: 4px solid #c5770f !important;
  border-radius: 4px !important; padding: 16px 20px !important; gap: 6px !important;
}
.st-key-notes_card h4 { font-size: 15px !important; font-weight: 700 !important; margin: 12px 0 4px !important;
  padding: 0 !important; line-height: 1.4 !important; }
.st-key-notes_card li, .st-key-notes_card p { font-size: 13.5px !important; line-height: 1.6 !important; }
.st-key-ai_body, .st-key-ai_warn, .st-key-ai_runs { padding: 10px 18px !important; }
.st-key-ai_foot { padding: 8px 18px !important; border-top: 1px solid #e3e5e8 !important; }

/* ── 머리말·섹션 ── */
.spc-hero { display: flex; flex-direction: column; gap: 14px; padding: 8px 0 4px; }
.spc-brand { display: flex; align-items: center; gap: 10px; font-size: 15px; font-weight: 700; color: #5b626b; }
.spc-mark { width: 26px; height: 26px; background: #16191d; border-radius: 4px; display: inline-grid; place-items: center; }
.spc-mark i { width: 10px; height: 10px; border: 2px solid #6da4d3; border-radius: 2px; display: block; }
.spc-hero h1 { font-size: 34px; line-height: 1.25; font-weight: 700; margin: 0; padding: 0; }
.spc-lead { font-size: 16px; color: #3b424a; margin: 0; max-width: 860px; line-height: 1.6; }
.spc-flow3 { display: flex; align-items: stretch; gap: 10px; flex-wrap: wrap; }
.spc-f { display: flex; flex-direction: column; gap: 2px; padding: 10px 14px; border-radius: 4px; min-width: 190px; }
.spc-f b { font-size: 14px; }
.spc-f span { font-size: 12px; color: #5b626b; }
.spc-f.rule { border: 1.5px solid #16191d; background: #fff; }
.spc-f.ai { border: 1.5px dashed #6da4d3; background: #f7fbfe; }
.spc-f.ai b { color: #004072; }
.spc-f.ver { border: 1.5px solid #9aa0a7; background: #fff; }
.spc-arr { align-self: center; font-size: 18px; color: #9aa0a7; }
.spc-top { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 28px; font-size: 13px; color: #4d545c; }
.spc-top b { color: #16191d; font-weight: 600; }
.spc-note { font-size: 12px; color: #6b727b; }
.spc-sec { display: flex; flex-direction: column; gap: 4px; padding-top: 22px; border-top: 1px solid #d9dcdf; }
.spc-kicker { font-size: 12px; font-weight: 600; color: #8a9098; }
.spc-sec h2 { font-size: 22px; font-weight: 700; margin: 0; padding: 0; }
.spc-sec-sub { font-size: 13.5px; color: #4d545c; margin: 0; }
.spc-para { font-size: 15px; line-height: 1.7; color: #3b424a; margin: 0; max-width: 900px; }
.spc-limits { display: flex; flex-direction: column; gap: 8px; background: #fafafa; border: 1px solid #d9dcdf;
  border-radius: 4px; padding: 14px 18px; }
.spc-limit { display: flex; gap: 10px; font-size: 14px; color: #3b424a; line-height: 1.55; }
.spc-limit > span:first-child { color: #9aa0a7; }
.b-rule { font-size: 11px; font-weight: 600; background: #16191d; color: #fff; padding: 2px 7px; border-radius: 3px; }
.b-ai { font-size: 11px; font-weight: 600; background: #dff1ff; color: #00508e; border: 1px solid #92c4ee;
  padding: 1px 7px; border-radius: 3px; }
.b-ai-solid { font-size: 11px; font-weight: 600; background: #0068a7; color: #fff; padding: 2px 7px; border-radius: 3px; }
.b-auto { font-size: 11px; font-weight: 600; border: 1px solid #6b727b; color: #3b424a; padding: 1px 7px; border-radius: 3px; }
.b-manual { font-size: 11px; font-weight: 600; background: #c5770f; color: #fff; padding: 2px 7px; border-radius: 3px; }
.spc-mono { font-family: 'IBM Plex Mono', monospace; }

/* ── 관리도 머리말·꼬리말 ── */
.spc-chart-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 16px; }
.spc-chart-title { font-size: 16px; font-weight: 600; }
.spc-chart-stats { display: inline-flex; gap: 14px; font-family: 'IBM Plex Mono', monospace; font-size: 12.5px; color: #4d545c; }
.spc-chart-legend { margin-left: auto; display: inline-flex; flex-wrap: wrap; align-items: center; gap: 16px; font-size: 13px; }
.spc-lg-line { display: inline-block; width: 18px; border-top: 1.5px dashed #5b626b; margin-right: 5px; vertical-align: middle; }
.spc-lg-truth { display: inline-block; width: 12px; height: 12px; border: 1.5px dotted #16191d; margin-right: 5px;
  vertical-align: middle; }
.spc-chart-foot { display: flex; justify-content: space-between; gap: 8px; font-size: 12px; color: #5b626b; }

/* ── 규칙 판정 카드·AI 설명 카드 ── */
.spc-step-head { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 10px; padding: 12px 18px; }
.spc-step-head b { font-size: 16px; font-weight: 600; }
.spc-step-head.rule { background: #16191d; color: #fff; }
.spc-step-head.ai { color: #004072; }
.spc-muted { font-size: 12px; }
.spc-step-head.rule .spc-muted { color: #c9cdd2; }
.spc-step-head.ai .spc-muted { color: #4d545c; }
.spc-tag-fixed { font-size: 11px; font-weight: 600; border: 1px solid #6b727b; padding: 1px 7px; border-radius: 3px; }
.spc-tag-ai { font-size: 11px; font-weight: 600; background: #0068a7; color: #fff; padding: 2px 7px; border-radius: 3px; }
.spc-tag-pass { font-size: 11px; font-weight: 600; border: 1px solid #16191d; color: #16191d; padding: 1px 7px; border-radius: 3px; }
.spc-tag-fail { font-size: 11px; font-weight: 600; border: 1px solid #b7191c; color: #b7191c; padding: 1px 7px; border-radius: 3px; }
.spc-rule-row { display: grid; grid-template-columns: 92px 96px minmax(0, 1fr) 40px; gap: 10px; padding: 12px 18px;
  border-top: 1px solid #eceef0; font-size: 13.5px; align-items: start; }
.spc-rule-th { background: #f6f7f8; color: #5b626b; font-size: 12px; padding: 8px 18px; border-top: none; }
.spc-rule-row small { display: block; font-size: 12px; color: #5b626b; }
.spc-pat { font-weight: 600; }
.spc-rid { font-size: 12px; font-weight: 600; border: 1px solid #16191d; border-radius: 3px; text-align: center; }
.spc-rule-empty { padding: 14px 18px; font-size: 13.5px; color: #3b424a; }
.spc-foot { display: flex; justify-content: space-between; gap: 8px; background: #f6f7f8; padding: 9px 18px;
  font-size: 12px; color: #4d545c; border-top: 1px solid #eceef0; }
.spc-ai-body { display: flex; flex-direction: column; gap: 8px; padding: 12px 18px 14px; }
.spc-label { font-size: 12px; font-weight: 600; color: #5b626b; }
.spc-summary { font-size: 14.5px; line-height: 1.65; }
.spc-prio { display: flex; flex-direction: column; gap: 10px; }
.spc-prio-row { display: grid; grid-template-columns: 24px minmax(0, 1fr) auto; gap: 10px; align-items: start; }
.spc-prio-row.unknown .spc-prio-title { color: #b7191c; }
.spc-rank { width: 24px; height: 24px; background: #0068a7; color: #fff; border-radius: 3px; display: inline-grid;
  place-items: center; font-size: 12px; font-weight: 600; }
.spc-prio-title { font-size: 14px; font-weight: 600; }
.spc-prio-sub { font-size: 12.5px; color: #4d545c; line-height: 1.5; }
.spc-chips { display: inline-flex; gap: 4px; }
.spc-chip { font-family: 'IBM Plex Mono', monospace; font-size: 11px; border: 1px solid #9aa0a7; border-radius: 3px; padding: 0 5px; }
.spc-issues { margin: 10px 18px 0; padding: 10px 12px; background: #fdecea; border: 1px solid #f1a9a5; border-radius: 4px;
  font-size: 12.5px; color: #7a1512; }
.spc-issues ul { margin: 6px 0 0; padding-left: 18px; }
.spc-status { display: flex; align-items: center; gap: 6px; font-size: 12px; color: #4d545c; }
.spc-run { font-size: 14px; line-height: 1.6; color: #3b424a; word-break: break-all; }
.spc-dot { width: 7px; height: 7px; border-radius: 50%; background: #6b727b; display: inline-block; flex: none; }

/* ── 04 검증 ── */
.spc-kpi { display: flex; flex-direction: column; gap: 6px; }
.spc-kpi-top { display: flex; align-items: center; gap: 8px; font-size: 13.5px; color: #3b424a; }
.spc-kpi-num { font-size: 36px; font-weight: 600; line-height: 1.1; }
.spc-kpi-num small { font-size: 20px; color: #5b626b; font-weight: 500; }
.spc-kpi-delta { font-size: 14px; font-weight: 600; color: #b7191c; margin-left: 8px; }
.spc-kpi-sub { font-size: 12px; color: #4d545c; line-height: 1.5; }
.spc-kpi-name { font-family: 'IBM Plex Mono', monospace; font-size: 12px; color: #3b424a; }
.spc-bars-head { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 8px;
  padding-bottom: 10px; border-bottom: 1px solid #eceef0; }
.spc-bars-head b { font-size: 15px; }
.spc-lg { display: inline-flex; align-items: center; gap: 6px; margin-left: 14px; font-size: 12.5px; }
.spc-lg i { width: 12px; height: 12px; display: inline-block; }
.spc-bar-group { display: grid; grid-template-columns: 120px minmax(0, 1fr); gap: 16px; padding: 12px 0;
  border-bottom: 1px solid #eceef0; }
.spc-bar-group.total { border-bottom: none; border-top: 1px solid #c9cdd2; }
.spc-bar-name b { display: block; font-size: 14px; }
.spc-bar-name small { font-family: 'IBM Plex Mono', monospace; font-size: 11.5px; color: #5b626b; }
.spc-bar-rows { display: flex; flex-direction: column; gap: 6px; }
.spc-bar-row { display: grid; grid-template-columns: 96px minmax(0, 1fr) 190px; gap: 10px; align-items: center; }
.spc-bar-who { font-size: 11.5px; color: #5b626b; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.spc-track { position: relative; height: 14px; background: #f0f1f3; }
.spc-fill { height: 100%; }
.spc-range { position: absolute; top: 50%; height: 2px; margin-top: -1px; background: #0b2e4f; }
.spc-range::before, .spc-range::after { content: ""; position: absolute; top: -4px; width: 2px; height: 10px; background: #0b2e4f; }
.spc-range::before { left: 0; }
.spc-range::after { right: 0; }
.spc-bar-val { font-family: 'IBM Plex Mono', monospace; font-size: 12.5px; white-space: nowrap; }
.spc-bar-val span { color: #5b626b; }
.spc-facts { border-left: 1px solid #eceef0; padding-left: 16px; display: flex; flex-direction: column; gap: 8px; }
.spc-facts p { font-size: 14px; line-height: 1.55; margin: 0; }
.spc-box-head { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; }
.spc-box-head b { font-size: 15px; }
.spc-box-head span.spc-note { width: 100%; }
.spc-count-group { font-size: 12px; font-weight: 600; color: #5b626b; padding-top: 8px; }
.spc-count { display: grid; grid-template-columns: minmax(0, 1fr) 70px; font-size: 13.5px; padding: 4px 0;
  border-bottom: 1px solid #f0f1f3; }
.spc-count b { text-align: right; font-family: 'IBM Plex Mono', monospace; font-weight: 600; }
.spc-cases-head { display: flex; flex-wrap: wrap; align-items: baseline; gap: 6px 14px; padding-bottom: 8px; }
.spc-cases-head span { font-size: 12.5px; color: #4d545c; }
.spc-case-row { display: grid; grid-template-columns: 36px 220px minmax(0, 1fr) minmax(0, 1fr); gap: 16px;
  padding: 12px 0; border-top: 1px solid #eceef0; font-size: 13.5px; }
.spc-case-row.th { font-size: 12px; font-weight: 600; color: #4d545c; background: #f6f7f8; padding: 8px 0; }
.spc-case-row small { display: block; font-size: 12px; color: #4d545c; }
.spc-quote { color: #3b424a; font-size: 12.5px; word-break: break-all; }  /* 모노 글꼴엔 한글이 없어 산세리프 */
.spc-cases-empty { font-size: 13.5px; color: #3b424a; padding: 8px 0; }

/* ── 모바일(2B): 한 줄로 쌓는다 ── */
@media (max-width: 640px) {
  .spc-hero h1 { font-size: 24px; }
  .spc-lead { font-size: 14px; }
  .spc-flow3 { flex-direction: column; }
  .spc-arr { transform: rotate(90deg); }
  .spc-sec h2 { font-size: 18px; }
  .spc-chart-legend { margin-left: 0; }
  .spc-rule-th { display: none; }
  .spc-rule-row { grid-template-columns: minmax(0, 1fr) auto auto; }
  .spc-rule-row > span:nth-child(3) { grid-column: 1 / -1; grid-row: 2; }
  .spc-bar-group { grid-template-columns: 1fr; gap: 6px; }
  .spc-bar-row { grid-template-columns: 76px minmax(0, 1fr); }
  .spc-bar-val { grid-column: 2; }
  .spc-facts { border-left: none; padding-left: 0; }
  .spc-case-row { grid-template-columns: 1fr; gap: 4px; }
}
</style>"""
