# 오탐 피드백: 세션 목록 넣고 빼기, CSV, 시연용 문구
from spc_explainer.feedback import DEMO_NOTE, is_flagged, table, to_csv, toggle

A = {"series": "시리즈 11", "event_id": "E1", "pattern": "급변", "span": "#45", "rule": "관리한계 밖 1점 (45번)",
     "time": "2026-09-26 11:00:00"}
B = dict(A, event_id="E2", pattern="치우침", span="#48–59", rule="12점 연속 중심선 위")


def test_toggle_adds_then_removes_the_same_event():
    entries = toggle(toggle([], A), B)
    assert [e["event_id"] for e in entries] == ["E1", "E2"]
    assert is_flagged(entries, "시리즈 11", "급변", "#45") and not is_flagged(entries, "시리즈 12", "급변", "#45")
    assert toggle(entries, dict(A, time="나중")) == [B]  # 같은 사건을 다시 누르면 취소


def test_csv_and_table_use_korean_headers():
    text = to_csv([A, B])
    assert text.splitlines()[0] == "시리즈,사건,패턴,구간,근거 규칙,표시 시각"
    assert text.splitlines()[1] == "시리즈 11,E1,급변,#45,관리한계 밖 1점 (45번),2026-09-26 11:00:00"
    assert table([A])[0]["구간"] == "#45" and to_csv([]).count("\n") == 1


def test_demo_note_wording():
    assert DEMO_NOTE == "시연용: 실제 운영에서는 이 피드백으로 규칙·원인표를 개선한다"
