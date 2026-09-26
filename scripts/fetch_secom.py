# UCI SECOM을 받아 선정 센서만 CSV로 저장한다. 한 번 실행하고 결과 CSV를 커밋한다.
# 사용법: python scripts/fetch_secom.py
import io
import sys
import urllib.request
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # 저장소 루트를 import 경로에 추가

import pandas as pd  # noqa: E402

from spc_explainer import config  # noqa: E402
from spc_explainer.secom import select_sensors  # noqa: E402


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # 윈도 콘솔에서도 한글이 깨지지 않게
    raw = urllib.request.urlopen(config.SECOM_URL, timeout=120).read()
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        X = pd.read_csv(z.open("secom.data"), sep=r"\s+", header=None)
        L = pd.read_csv(z.open("secom_labels.data"), sep=r"\s+", header=None, names=["label", "timestamp"])
    ts = pd.to_datetime(L["timestamp"], format="%d/%m/%Y %H:%M:%S")
    order = ts.argsort(kind="stable")  # 시간순 정렬 (원본도 이미 시간순)
    X = X.iloc[order].reset_index(drop=True)
    L = L.iloc[order].reset_index(drop=True)
    ts = ts.iloc[order].reset_index(drop=True)
    cols = select_sensors(X)
    if len(cols) < config.SECOM_N_SENSORS:
        sys.exit(f"조건에 맞는 센서가 {len(cols)}개뿐입니다: {cols}")
    out = pd.DataFrame({"timestamp": ts, "label": L["label"]})
    for c in cols:
        out[f"sensor_{c}"] = X[c]
    config.SECOM_PATH.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(config.SECOM_PATH, index=False)
    print(f"선정 센서 {cols} -> {config.SECOM_PATH} ({len(out)}행)")


if __name__ == "__main__":
    main()
