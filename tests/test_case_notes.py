# 사례 해설(수동 분석)의 집계 숫자가 결과 파일에서 다시 센 값과 같은지
import json
import runpy
from pathlib import Path

from spc_explainer import config

COUNTS = runpy.run_path(str(Path(__file__).resolve().parent.parent / "scripts" / "case_counts.py"))


def test_inside_limit_spike_count_matches_the_notes():
    detections = json.loads(config.DETECTIONS_PATH.read_text(encoding="utf-8"))
    dataset = json.loads(config.SERIES_PATH.read_text(encoding="utf-8"))
    c = COUNTS["inside_limit_spikes"](detections, dataset, "gpt-4.1-mini")
    notes = config.CASE_NOTES_PATH.read_text(encoding="utf-8")
    assert f"{c['inside_points']}개 점" in notes and f"{c['reported_points']}개 점 중" in notes
    assert COUNTS["inside_limit_spikes"](detections, dataset, "gpt-6-sol")["inside_points"] == 0
