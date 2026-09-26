# 관리도 그림(plotly)과 그림 머리말·꼬리말(HTML). 02 규칙 판정(가상 데이터)과 05 실데이터(SECOM) 섹션이 같이 쓴다.
# 스타일 출처: docs/design/ref/control-chart.png — CL 실선, UCL·LCL 점선과 오른쪽 라벨, 패턴별 마커(◆▲■),
# 규칙이 판정한 구간의 세로 음영 + 위쪽 라벨. 정답(심은 이상)은 테두리만 있는 점선 사각형으로 구분한다.
import statistics

import plotly.graph_objects as go

from .patterns import KOREAN, PATTERNS, Event
from .ui_html import PATTERN_COLORS, SYMBOL, esc, span_text

LINE = "#2a2f35"  # 측정값 선
LIMIT = "#5b626b"  # 중심선·관리한계
GRID = "#eceef0"
TICK = "#6b727b"
MONO = "IBM Plex Mono, monospace"
SANS = "IBM Plex Sans KR, sans-serif"
MARKERS = {"spike": ("diamond", 12), "trend": ("triangle-up", 11), "shift": ("square", 9)}
MAX_BAND_LABELS = 8  # 사건이 이보다 많으면(예: SECOM) 음영 위 라벨을 생략한다
NARROW_PLOT_PX = 200  # 모바일(폭 400px) 카드 안의 그림 영역 폭. 라벨 겹침은 가장 좁은 이 폭으로 판단한다
LABEL_ROW_PX = 16
MAX_LABEL_ROWS = 3  # 라벨이 이보다 많은 줄을 차지하면 생략한다 (음영과 규칙 판정 표로 충분)


def _rgba(hex_color: str, alpha: float) -> str:
    h = hex_color.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


def _band_text(e: Event) -> str:
    return f"{SYMBOL[e.pattern]} {KOREAN[e.pattern]} {span_text(e.start, e.end)}"


def _label_px(text: str) -> float:
    """굵은 12px 라벨의 대략적인 폭(px): 한글·도형 기호 12, 공백 4, 나머지(숫자·#·–) 7.5."""
    return sum(12 if "가" <= ch <= "힣" or "■" <= ch <= "◿" else 4 if ch == " " else 7.5
               for ch in text)


def _label_rows(events: list[Event], n_points: int) -> list[int]:
    """시작점 순으로 놓인 사건마다 라벨 줄 번호. 좁은 화면에서도 앞 라벨과 겹치지 않는 첫 줄에 놓는다."""
    per_point = NARROW_PLOT_PX / (n_points + 0.6)  # x축 범위(-0.8 ~ n-0.2)에서 점 하나의 폭(px)
    ends, rows = [], []  # 줄마다 마지막 라벨이 끝나는 x (점 단위)
    for e in events:
        x0 = e.start - 0.5
        row = next((r for r, end in enumerate(ends) if end <= x0), len(ends))
        if row == len(ends):
            ends.append(x0)
        ends[row] = x0 + _label_px(_band_text(e)) / per_point
        rows.append(row)
    return rows


def control_chart(values, events: list[Event], center: float, ucl: float, lcl: float,
                  truth: list[Event] | None = None, phase_boundary: int | None = None,
                  fail_idx: list[int] | None = None, y_title: str = "", show_legend: bool = True,
                  band_labels: bool | None = None, height: int = 440) -> go.Figure:
    """측정값 + CL 실선·UCL/LCL 점선(오른쪽 라벨) + 패턴별 마커 + 규칙 판정 구간 음영(+ 위 라벨)."""
    vals = [float(v) for v in values]
    xs = list(range(len(vals)))
    if band_labels is None:
        band_labels = len(events) <= MAX_BAND_LABELS
    fig = go.Figure()
    # 규칙 판정 구간: 패턴 색의 옅은 음영 + 얇은 테두리 (점·선 아래)
    ordered = sorted(events, key=lambda ev: ev.start)
    rows = _label_rows(ordered, len(vals)) if band_labels else []
    if rows and max(rows) >= MAX_LABEL_ROWS:
        rows = []
    for i, e in enumerate(ordered):
        color = PATTERN_COLORS[e.pattern]
        fig.add_vrect(x0=e.start - 0.5, x1=e.end + 0.5, fillcolor=_rgba(color["fill"], 0.10),
                      line={"color": _rgba(color["fill"], 0.35), "width": 1}, layer="below")
        if rows:
            fig.add_annotation(x=e.start - 0.5, y=1, xref="x", yref="paper", xanchor="left", yanchor="bottom",
                               yshift=rows[i] * LABEL_ROW_PX, text=f"<b>{_band_text(e)}</b>",
                               showarrow=False, font={"size": 12, "color": color["text"], "family": SANS})
    # 정답 구간: 테두리만 있는 점선 사각형 (규칙 음영과 구분)
    for t in truth or []:
        fig.add_shape(type="rect", x0=t.start - 0.5, x1=t.end + 0.5, y0=0, y1=1, xref="x", yref="paper",
                      line={"color": "#16191d", "width": 1.2, "dash": "dot"}, fillcolor="rgba(0,0,0,0)")
    # 중심선(실선)·관리한계(점선) + 오른쪽 라벨
    for label, y, dash in (("UCL", ucl, "dash"), ("CL", center, "solid"), ("LCL", lcl, "dash")):
        fig.add_hline(y=y, line={"color": LIMIT, "width": 1.2 if dash == "solid" else 1, "dash": dash}, layer="below")
        fig.add_annotation(x=1, y=y, xref="paper", yref="y", xanchor="left", yanchor="middle", xshift=8,
                           text=f"{label} {y:.4g}", showarrow=False, font={"size": 11, "color": "#3b424a", "family": MONO})
    # 측정값 선 + 정상 점(흰 원)
    dot = 6 if len(vals) <= 200 else 3
    fig.add_trace(go.Scatter(x=xs, y=vals, mode="lines+markers", name="측정값", showlegend=False,
                             line={"color": LINE, "width": 1.3},
                             marker={"size": dot, "color": "#ffffff", "line": {"color": LINE, "width": 1}},
                             hovertemplate="#%{x}: %{y:.2f}<extra></extra>"))
    # 규칙이 판정한 점: 패턴별 모양·색
    for p in PATTERNS:
        idx = sorted({i for e in events if e.pattern == p for i in range(e.start, e.end + 1)})
        if idx:
            symbol, size = MARKERS[p]
            fig.add_trace(go.Scatter(x=idx, y=[vals[i] for i in idx], mode="markers", name=KOREAN[p],  # 범례가 모양을 그림
                                     marker={"symbol": symbol, "size": size, "color": PATTERN_COLORS[p]["fill"],
                                             "line": {"color": PATTERN_COLORS[p]["text"], "width": 1}},
                                     hovertemplate="#%{x}: %{y:.2f}<extra>" + KOREAN[p] + "</extra>"))
    if fail_idx:
        fig.add_trace(go.Scatter(x=list(fail_idx), y=[vals[i] for i in fail_idx], mode="markers", name="불량 라벨",
                                 marker={"symbol": "x", "color": "black", "size": 7}))
    if phase_boundary is not None:
        fig.add_vline(x=phase_boundary - 0.5, line={"color": "#555555", "dash": "dot"})
        fig.add_annotation(x=phase_boundary - 0.5, y=1, xref="x", yref="paper", yanchor="bottom",
                           text="Phase I | Phase II", showarrow=False, font={"size": 11, "color": "#3b424a"})
    # 축: 값 범위가 좁으면 y는 정수 눈금, x는 10 간격. 눈금 글꼴은 모노
    lo, hi = min(vals + [lcl]), max(vals + [ucl])
    pad = (hi - lo) * 0.06 or 1.0
    yaxis = {"range": [lo - pad, hi + pad], "showgrid": True, "gridcolor": GRID, "zeroline": False,
             "tickfont": {"family": MONO, "size": 11, "color": TICK},
             "title": {"text": y_title, "font": {"size": 12, "color": TICK}}}
    if hi - lo + 2 * pad <= 14:
        yaxis["dtick"] = 1
    xaxis = {"range": [-0.8, len(vals) - 0.2], "showgrid": False, "zeroline": False, "showline": True,
             "linecolor": "#9aa0a7", "ticks": "outside", "ticklen": 4, "tickcolor": "#9aa0a7",
             "tickfont": {"family": MONO, "size": 11, "color": TICK}}
    if len(vals) <= 200:
        xaxis.update(tick0=0, dtick=10)
    top = 34 if rows or show_legend or phase_boundary is not None else 16
    top += LABEL_ROW_PX * max(rows, default=0)
    fig.update_layout(height=height, margin={"l": 44, "r": 76, "t": top, "b": 30},
                      paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", xaxis=xaxis, yaxis=yaxis,
                      showlegend=show_legend, legend={"orientation": "h", "x": 1, "xanchor": "right", "y": 1.02,
                                                      "yanchor": "bottom", "font": {"size": 12}},
                      font={"family": SANS, "color": "#16191d"}, hoverlabel={"font": {"family": MONO}})
    return fig


def chart_header_html(values, title: str, show_truth: bool = False) -> str:
    """그림 머리말: 제목 + n·x̄·σ(넘겨받은 값에서 계산) + 범례."""
    vals = [float(v) for v in values]
    mean = statistics.fmean(vals) if vals else 0.0
    sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
    legend = "".join(f'<span><b style="color:{PATTERN_COLORS[p]["fill"]}">{SYMBOL[p]}</b> {KOREAN[p]}</span>'
                     for p in PATTERNS)
    legend += '<span><i class="spc-lg-line"></i>관리한계</span>'
    if show_truth:
        legend += '<span><i class="spc-lg-truth"></i>정답(심은 이상)</span>'
    return (f'<div class="spc-chart-head"><span class="spc-chart-title">{esc(title)}</span>'
            f'<span class="spc-chart-stats"><span>n={len(vals)}</span><span>x̄={mean:.2f}</span><span>σ={sd:.2f}</span></span>'
            f'<span class="spc-chart-legend">{legend}</span></div>')


def chart_footer_html(show_truth: bool = False) -> str:
    right = "세로 음영 = 규칙이 판정한 이상 구간"
    if show_truth:
        right += " · 점선 테두리 = 심은 이상(정답)"
    return f'<div class="spc-chart-foot"><span>x축 · 측정 순번 (0부터)</span><span>{right}</span></div>'
