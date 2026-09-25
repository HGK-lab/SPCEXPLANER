# 채점: 정답 이상과 탐지 사건을 구간 겹침으로 맞춰 본다 (규칙·LLM 공통 기준)
from .patterns import PATTERNS, Event, overlaps


def classify(truth: list[Event], found: list[Event]) -> tuple[list[bool], list[str]]:
    """(정답별 탐지 여부, 탐지 사건별 분류). 분류: "hit" 정탐 | "confusion" 패턴 혼동 | "false" 오탐."""
    detected = [any(f.pattern == t.pattern and overlaps(f, t) for f in found) for t in truth]
    kinds = []
    for f in found:
        if any(f.pattern == t.pattern and overlaps(f, t) for t in truth):
            kinds.append("hit")
        elif any(overlaps(f, t) for t in truth):
            kinds.append("confusion")
        else:
            kinds.append("false")
    return detected, kinds


def summarize(truths: list[list[Event]], founds: list[list[Event]]) -> dict:
    """전체 시리즈 채점 요약. truths[i]·founds[i]는 i번 시리즈의 정답·탐지 사건."""
    per_pattern = {p: {"injected": 0, "detected": 0} for p in PATTERNS}
    normal = {"series": 0, "alarmed_series": 0, "false_events": dict.fromkeys(PATTERNS, 0)}
    anomalous = {"false_events": dict.fromkeys(PATTERNS, 0), "confusions": 0}
    false_list = []
    for sid, (truth, found) in enumerate(zip(truths, founds)):
        detected, kinds = classify(truth, found)
        for t, hit in zip(truth, detected):
            per_pattern[t.pattern]["injected"] += 1
            per_pattern[t.pattern]["detected"] += int(hit)
        if not truth:
            normal["series"] += 1
            normal["alarmed_series"] += int(bool(found))
        for f, kind in zip(found, kinds):
            if kind == "false":
                (normal if not truth else anomalous)["false_events"][f.pattern] += 1
                false_list.append({"series": sid, **f.to_dict()})
            elif kind == "confusion":
                anomalous["confusions"] += 1
    injected = sum(v["injected"] for v in per_pattern.values())
    detected_total = sum(v["detected"] for v in per_pattern.values())
    return {
        "per_pattern": per_pattern,
        "injected": injected,
        "detected": detected_total,
        "rate": detected_total / injected if injected else None,
        "normal": normal,
        "anomalous": anomalous,
        "false_list": false_list,
    }
