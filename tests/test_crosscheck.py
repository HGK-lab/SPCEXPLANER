# 교차 검증: 독립 구현(shewhart)으로 같은 데이터를 판정해 점 단위로 일치하는지 본다
import numpy as np
import pytest

from spc_explainer import config
from spc_explainer.generator import generate_dataset
from spc_explainer.rules import detect

shewhart = pytest.importorskip("shewhart")  # 개발 전용 의존성

RULE_MAP = {"nelson_1": "spike", "nelson_2": "shift", "nelson_3": "trend"}


def shewhart_points(values) -> set[tuple[str, int]]:
    """shewhart가 표시한 (패턴, 점 번호) 집합. 3패턴 외 규칙은 버린다."""
    limits = {"i_center": config.CENTER, "sigma_within": config.SIGMA, "mr_center": config.SIGMA * 1.128}
    result = shewhart.imr(np.asarray(values, dtype=float), rules="nelson", limits=limits)
    return {(RULE_MAP[s.rule], int(i)) for s in result.signals if s.rule in RULE_MAP for i in s.points}


def our_points(values) -> set[tuple[str, int]]:
    return {(e.pattern, i) for e in detect(values) for i in range(e.start, e.end + 1)}


@pytest.mark.parametrize("seed", [config.SEED, 1, 2])
def test_same_points_as_shewhart(seed):
    for s in generate_dataset(seed)["series"]:
        assert our_points(s["values"]) == shewhart_points(s["values"]), f"seed {seed} series {s['id']}"
