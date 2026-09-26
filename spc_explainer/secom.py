# UCI SECOM 실데이터 확인: 센서 선정(불량 라벨 미사용), Phase I 한계 추정, Phase II 감시, 불량 라벨과의 겹침 관찰
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, rules
from .patterns import PATTERNS, Event

D2 = 1.128  # 크기 2 이동범위의 d2 상수 (σ = 평균 이동범위 / d2)


def select_sensors(X: pd.DataFrame, phase1_n: int = config.SECOM_PHASE1_N, k: int = config.SECOM_N_SENSORS,
                   min_unique: int = config.SECOM_MIN_UNIQUE,
                   max_abs_skew: float = config.SECOM_MAX_ABS_SKEW) -> list:
    """결측 0 + Phase I 고유값 min_unique 이상 + Phase I 왜도 절댓값 max_abs_skew 이하 → 번호 순 앞 k개.
    불량 라벨은 받지 않는다 (결과를 보고 센서를 고르는 것을 막기 위해)."""
    phase1 = X.iloc[:phase1_n]
    missing = X.isna().sum()
    ok = [c for c in X.columns
          if missing[c] == 0 and phase1[c].nunique() >= min_unique and abs(phase1[c].skew()) <= max_abs_skew]
    return ok[:k]


def phase1_limits(values) -> dict:
    """Phase I 구간으로 관리한계를 추정한다: 중심선 = 평균, σ = 평균 이동범위 / 1.128."""
    a = np.asarray(values, dtype=float)
    center = float(a.mean())
    sigma = float(np.abs(np.diff(a)).mean() / D2)
    return {"center": center, "sigma": sigma, "ucl": center + 3 * sigma, "lcl": center - 3 * sigma}


def monitor(values, phase1_n: int = config.SECOM_PHASE1_N) -> tuple[dict, list[Event]]:
    """앞 phase1_n점으로 한계를 정하고 나머지를 같은 규칙으로 감시한다. 사건 번호는 전체 시계열 기준."""
    v = [float(x) for x in values]
    limits = phase1_limits(v[:phase1_n])
    found = rules.detect(v[phase1_n:], center=limits["center"], ucl=limits["ucl"], lcl=limits["lcl"])
    return limits, [Event(e.pattern, e.start + phase1_n, e.end + phase1_n, e.direction) for e in found]


def overlap_summary(events: list[Event], labels, phase1_n: int = config.SECOM_PHASE1_N) -> dict:
    """알람과 불량 라벨(1)의 겹침 관찰. 탐지율이 아니다."""
    fail = np.asarray(labels) == 1
    flagged = np.zeros(len(fail), dtype=bool)
    for e in events:
        flagged[e.start:e.end + 1] = True
    fail2, flagged2 = fail[phase1_n:], flagged[phase1_n:]
    return {
        "events": len(events),
        "by_pattern": {p: sum(1 for e in events if e.pattern == p) for p in PATTERNS},
        "events_with_fail": sum(1 for e in events if fail[e.start:e.end + 1].any()),
        "flagged_points": int(flagged2.sum()),
        "fail_rate_flagged": float(fail2[flagged2].mean()) if flagged2.any() else None,
        "fail_rate_phase2": float(fail2.mean()),
    }


def load(path: Path = config.SECOM_PATH) -> pd.DataFrame | None:
    """선정 센서 CSV (timestamp, label, sensor_*). 없으면 None."""
    return pd.read_csv(path, parse_dates=["timestamp"]) if path.exists() else None


def summarize(df: pd.DataFrame, phase1_n: int = config.SECOM_PHASE1_N) -> dict:
    """센서별 Phase I 한계·Phase II 알람·불량 겹침 요약 (metrics.json·리포트용)."""
    labels = df["label"].tolist()
    sensors = {}
    for name in [c for c in df.columns if c.startswith("sensor_")]:
        limits, events = monitor(df[name].tolist(), phase1_n)
        sensors[name] = {"limits": limits, **overlap_summary(events, labels, phase1_n)}
    return {"n": len(df), "phase1_n": phase1_n, "sensors": sensors}
