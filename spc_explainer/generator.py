# 가상 시리즈 생성기: 정상 잡음 위에 3패턴을 규칙 정의를 만족하도록 심고, 위치를 정답 라벨로 남긴다.
import json
from pathlib import Path

import numpy as np

from . import config
from .patterns import Event

LENGTHS = {"spike": 1, "trend": config.TREND_LEN, "shift": config.SHIFT_LEN}


def _place(rng: np.random.Generator, kinds: list[str], n: int) -> list[tuple[int, int, str]]:
    """이상들의 구간 [(start, end, kind)]을 무작위로 정한다. 앞 WARMUP점은 비우고 이상끼리 MIN_GAP점 이상 띄운다."""
    for _ in range(10_000):
        spans = []
        for kind in kinds:
            start = int(rng.integers(config.WARMUP, n - LENGTHS[kind] + 1))
            spans.append((start, start + LENGTHS[kind] - 1, kind))
        spans.sort()
        if all(b[0] - a[1] - 1 >= config.MIN_GAP for a, b in zip(spans, spans[1:])):
            return spans
    raise RuntimeError("이상 위치를 정하지 못했습니다")


def _inject(rng: np.random.Generator, x: np.ndarray, kind: str, start: int, sign: int) -> None:
    """x[start:]에 이상 하나를 심는다. sign=+1이면 위/상승, -1이면 아래/하강. 값은 소수 둘째 자리."""
    c, sd = config.CENTER, config.SIGMA
    if kind == "spike":
        x[start] = round(c + sign * sd * rng.uniform(*config.SPIKE_OFFSET), 2)
    elif kind == "trend":
        base = c - sign * sd * rng.uniform(*config.TREND_START_OFFSET)
        total = sd * rng.uniform(*config.TREND_TOTAL)
        weights = rng.uniform(0.5, 1.5, config.TREND_LEN - 1)
        steps = total * weights / weights.sum()  # 증가분이 모두 양수(최소 약 0.13) → 반올림해도 엄격한 단조
        seg = base + sign * np.concatenate([[0.0], np.cumsum(steps)])
        x[start:start + config.TREND_LEN] = np.round(seg, 2)
    elif kind == "shift":
        lo, hi = (c, config.UCL) if sign > 0 else (config.LCL, c)
        for i in range(start, start + config.SHIFT_LEN):
            while True:  # 중심선 한쪽이면서 한계 안인 값만 쓴다 (기각 표집)
                v = round(float(rng.normal(c + sign * sd * config.SHIFT_MEAN_OFFSET, sd)), 2)
                if lo < v < hi:
                    x[i] = v
                    break
    else:
        raise ValueError(f"알 수 없는 패턴: {kind}")


def generate_series(series_id: int, kinds: list[str], rng: np.random.Generator) -> dict:
    """시리즈 하나: 정상 잡음 N(CENTER, SIGMA²) 위에 kinds의 이상을 심는다."""
    x = np.round(rng.normal(config.CENTER, config.SIGMA, config.N_POINTS), 2)
    anomalies = []
    for start, end, kind in (_place(rng, kinds, config.N_POINTS) if kinds else []):
        sign = 1 if rng.random() < 0.5 else -1
        _inject(rng, x, kind, start, sign)
        anomalies.append(Event(kind, start, end, "up" if sign > 0 else "down").to_dict())
    return {"id": series_id, "values": [float(v) for v in x], "anomalies": anomalies}


def generate_dataset(seed: int = config.SEED) -> dict:
    """SCENARIOS 순서대로 전체 시리즈를 만든다. 같은 시드면 항상 같은 결과."""
    rng = np.random.default_rng(seed)
    return {
        "seed": seed,
        "center": config.CENTER,
        "ucl": config.UCL,
        "lcl": config.LCL,
        "series": [generate_series(i, kinds, rng) for i, kinds in enumerate(config.SCENARIOS)],
    }


def save_dataset(dataset: dict, path: Path = config.SERIES_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dataset, ensure_ascii=False, indent=1), encoding="utf-8")


def load_dataset(path: Path = config.SERIES_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def truth_events(series: dict) -> list[Event]:
    """시리즈에 심은 이상(정답)을 Event 목록으로."""
    return [Event.from_dict(a) for a in series["anomalies"]]
