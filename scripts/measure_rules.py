# 규칙 엔진 판정 시간 측정 → results/rule_timing.json (04 검증에서 LLM 호출 시간과 나란히 보여준다)
# 사용법: python scripts/measure_rules.py [--repeats 20]   (LLM을 부르지 않는다)
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 저장소 루트를 import 경로에 추가

from spc_explainer import config, experiment, generator, rules  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="규칙 엔진 판정 시간 측정")
    parser.add_argument("--repeats", type=int, default=20, help="시리즈 20개를 몇 번 반복해 잴지")
    args = parser.parse_args()
    dataset = (json.loads(config.SERIES_PATH.read_text(encoding="utf-8")) if config.SERIES_PATH.exists()
               else generator.generate_dataset())
    rules.detect(dataset["series"][0]["values"])  # 첫 호출의 import·준비 시간은 빼고 잰다
    timing = experiment.rule_timing(dataset, args.repeats)
    config.RULE_TIMING_PATH.write_text(json.dumps(timing, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"시리즈 1개 판정 평균 {timing['mean_ms_per_series']:.3f}ms (중앙값 {timing['median_ms_per_series']:.3f}ms, "
          f"{timing['calls']}회) → {config.RULE_TIMING_PATH}")


if __name__ == "__main__":
    main()
