# 실험 실행: 가상 데이터 → 규칙 판정 → LLM 설명·단독 판정(캐시 사용) → 지표·리포트·ai_errors
# 사용법: python scripts/run_experiment.py [--no-llm] [--force]
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 저장소 루트를 import 경로에 추가

from spc_explainer import experiment, llm_client  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="SPC 설명기 검증 실험")
    parser.add_argument("--no-llm", action="store_true", help="LLM을 부르지 않고 저장된 결과로 지표·리포트만 다시 만든다")
    parser.add_argument("--force", action="store_true", help="캐시를 무시하고 LLM을 다시 부른다")
    args = parser.parse_args()
    llm = None
    if not args.no_llm:
        if not llm_client.get_api_key():
            sys.exit("OPENAI_API_KEY가 없습니다. .env를 확인하거나 --no-llm으로 실행하세요.")
        llm = llm_client.call_json
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # 윈도 콘솔에서도 한글이 깨지지 않게
    m = experiment.run_all(llm, force=args.force)
    print(f"규칙 탐지 {m['rules']['detected']}/{m['rules']['injected']}")
    for d in m["detect"]:
        rates = ", ".join("-" if r["rate"] is None else f"{r['rate']:.0%}" for r in d["runs"])
        fmt = sum(r["format_violations"] for r in d["runs"])
        err = sum(r["call_errors"] for r in d["runs"])
        print(f"단독 판정 {d['model']}: 반복별 탐지율 {rates} (형식 위반 {fmt}, 호출 오류 {err})")
    e = m["explain"]
    if e:
        io = e["issue_outputs"]
        print(f"설명 출력 {e['outputs']}개 중 통과 {e['passed']} (형식 위반 {io['format']}, 원인표 밖 {io['cause']}, "
              f"판정 불일치 {io['mismatch']}, 호출 오류 {e['call_errors']}, 반복 간 차이 {e['repeat_changed_series']}개 시리즈)")
    print(f"리포트: {experiment.Paths().report}")


if __name__ == "__main__":
    main()
