# 사례 해설(docs/case_notes.md)에 쓴 집계 숫자를 결과 파일에서 다시 센다 (LLM 호출 없음)
# 사용법: python scripts/case_counts.py
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 저장소 루트를 import 경로에 추가

from spc_explainer import config  # noqa: E402


def inside_limit_spikes(detections: dict, dataset: dict, model: str) -> dict:
    """모델이 '급변'이라고 보고한 점 중 관리한계 안(LCL ≤ 값 ≤ UCL)인 점의 수. 모든 시리즈·반복 합계와 회차별."""
    ucl, lcl = dataset["ucl"], dataset["lcl"]
    reported, inside, per_run = 0, 0, {}
    for sid, s in detections["models"][model]["series"].items():
        values = dataset["series"][int(sid)]["values"]
        for r in s["runs"]:
            for e in r.get("events") or []:
                if e["pattern"] != "spike":
                    continue
                points = [i for i in range(e["start"], e["end"] + 1) if 0 <= i < len(values)]
                n = sum(1 for i in points if lcl <= values[i] <= ucl)
                reported += len(points)
                inside += n
                per_run[r["run"] + 1] = per_run.get(r["run"] + 1, 0) + n
    return {"reported_points": reported, "inside_points": inside, "per_run": dict(sorted(per_run.items()))}


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    detections = json.loads(config.DETECTIONS_PATH.read_text(encoding="utf-8"))
    dataset = json.loads(config.SERIES_PATH.read_text(encoding="utf-8"))
    for model in detections["models"]:
        c = inside_limit_spikes(detections, dataset, model)
        runs = ", ".join(f"{k}회차 {v}" for k, v in c["per_run"].items())
        print(f"{model}: 급변으로 보고한 점 {c['reported_points']}개 중 한계 안 {c['inside_points']}개 ({runs})")


if __name__ == "__main__":
    main()
