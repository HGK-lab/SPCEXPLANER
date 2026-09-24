# 일회성 비교 실험: 같은 데이터에 두 라이브러리를 돌려 3패턴 탐지가 일치하는지 확인
import json, time
import numpy as np

CENTER, SIGMA = 100.0, 1.0  # 관리한계 97~103 = ±3σ

def make_series(seed):
    rng = np.random.default_rng(seed)
    x = rng.normal(CENTER, SIGMA * 0.8, 100)  # 정상 구간은 σ보다 약간 작게 흔들림
    truth = {}
    x[30] = 104.2; truth["spike"] = [30]                          # 급변: 한계 밖 1점
    x[50:57] = CENTER - 1.0 + np.arange(7) * 0.35; truth["trend"] = list(range(50, 57))  # 추세: 7점 연속 상승
    x[75:85] = CENTER + 1.3 + rng.normal(0, 0.3, 10); truth["shift"] = list(range(75, 85))  # 치우침: 10점 평균 위
    return x, truth

x, truth = make_series(7)

# --- pycontrolcharts: 고정 한계 + 테스트 1,2,3만 ---
import pycontrolcharts as pcc
t = time.perf_counter()
df = pcc.run_tests_with_custom_limits(
    list(x),
    limits=pcc.CustomLimits(center_line=CENTER, ucl=CENTER + 3 * SIGMA, lcl=CENTER - 3 * SIGMA),
    run_tests=pcc.RunTestConfig(test5=False, test6=False),
)
t_pcc = time.perf_counter() - t
print("pycontrolcharts columns:", list(df.columns))
pcc_hits = {}
for i, vs in enumerate(df["violations"]):
    for v in vs or []:
        pcc_hits.setdefault(f'{v["type"]}:{v["description"]}', []).append(i)
print("pycontrolcharts 위반 (type:description -> points):")
for k, pts in pcc_hits.items():
    print("  ", k, "->", pts)
print("  sample row json:", df.iloc[30].to_json(force_ascii=False)[:400])

# --- shewhart: 고정 baseline + nelson, 1/2/3만 필터 ---
import shewhart as sw
t = time.perf_counter()
r = sw.imr(x, rules="nelson", limits={"i_center": CENTER, "sigma_within": SIGMA, "mr_center": SIGMA * 1.128})
t_sw = time.perf_counter() - t
sw_hits = [s.to_dict() for s in r.signals if s.rule in ("nelson_1", "nelson_2", "nelson_3")]
others = sorted({s.rule for s in r.signals} - {"nelson_1", "nelson_2", "nelson_3"})
print("shewhart 위반 (1/2/3):")
for s in sw_hits:
    print("  ", s["rule"], s["note"], "->", s["points"])
print("  (기타 규칙에서 추가로 뜬 것:", others, ")")
print("  summary():", r.summary()[:300].replace("\n", " | "))

print("정답 라벨:", json.dumps(truth))
print(f"실행 시간: pcc {t_pcc*1000:.1f}ms, shewhart {t_sw*1000:.1f}ms")
