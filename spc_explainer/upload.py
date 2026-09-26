# 내 데이터 판정: 올리거나 붙여넣은 글자를 검사해 막 두께 숫자 열을 꺼내고,
# 관리한계(앞 N점 추정 또는 직접 입력)로 기존 규칙 엔진을 그대로 돌린다.
# 파일은 저장하지 않는다. 결과는 실험 지표(04 검증)에 섞지 않는다.
import csv
import math
from datetime import datetime, timedelta

from . import rules, secom

MAX_ROWS = 2000
MIN_ROWS = 10  # 판정에 쓸 최소 행 수
MIN_PHASE1 = 20  # 한계 추정에 쓸 앞 구간의 최소 점 수
PHASE1_CAP = 100  # 앞 N점 기본값의 상한
MAX_ABS_VALUE = 1e9  # 이보다 큰 값은 막 두께로 볼 수 없다 (그림·통계 계산이 넘치는 것도 막는다)
MISSING_TOKENS = {"nan", "inf", "+inf", "-inf", "infinity", "-infinity", "#n/a", "n/a", "na", "null", "none"}


class UploadError(ValueError):
    """화면에 그대로 보여줄 한국어 오류 (몇째 줄인지 포함)."""


def decode(raw: bytes) -> str:
    """올린 파일의 글자. UTF-8(BOM 포함)을 먼저, 안 되면 엑셀 기본인 CP949로 읽는다."""
    for encoding in ("utf-8-sig", "cp949"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise UploadError("글자 인코딩을 읽을 수 없습니다. UTF-8 또는 CP949(엑셀 기본)로 저장한 CSV를 올려 주세요.")


def read_input(raw: bytes | None, pasted: str) -> str | None:
    """판정할 글자. 올린 파일이 있으면 그것(비어 있으면 오류), 없으면 붙여넣은 글자. 둘 다 비었으면 None(기다림)."""
    if raw is not None:
        text = decode(raw)
        if not text.strip():
            raise UploadError("올린 파일이 비어 있습니다. 막 두께 숫자가 한 줄에 하나씩 있는 CSV를 올려 주세요.")
        return text
    return pasted if pasted.strip() else None


def _number(cell: str) -> float | None:
    """숫자 칸이면 값, 아니면 None. nan·inf도 숫자가 아닌 것으로 본다."""
    try:
        v = float(cell.strip())
    except ValueError:
        return None
    return v if math.isfinite(v) else None


def parse(text: str) -> dict:
    """{"values": [막 두께], "times": [시점 글자] 또는 None, "name": 값 열 이름}.
    열은 1개(막 두께) 또는 2개(시점, 막 두께). 첫 줄의 막 두께 칸이 숫자가 아니면 머리글로 본다.
    빈 줄·빈 칸(결측), 숫자가 아닌 값, 열 개수 불일치, 행 수 초과·부족은 UploadError."""
    if "\x00" in text:
        raise UploadError("글자에 NUL 문자가 있습니다. UTF-8 또는 CP949 CSV로 저장해 주세요 (UTF-16은 읽지 않습니다).")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    while lines and not lines[-1].strip():  # 끝의 빈 줄만 무시한다 (중간의 빈 줄은 결측)
        lines.pop()
    if not lines:
        raise UploadError("비어 있습니다. 막 두께 숫자가 한 줄에 하나씩 있는 CSV를 올리거나 붙여넣어 주세요.")
    first = lines[0]
    delimiter = "\t" if "\t" in first else (";" if ";" in first and "," not in first else ",")
    try:
        # 줄 끝을 붙여 넘긴다: 닫히지 않은 따옴표가 여러 줄을 삼키면 그 칸에 줄바꿈이 남아 아래에서 알아챈다
        rows = list(csv.reader((line + "\n" for line in lines), delimiter=delimiter))
    except csv.Error as e:
        raise UploadError(f"CSV 형식을 읽을 수 없습니다 ({e}). 한 줄에 시점과 막 두께만 쉼표로 구분해 주세요.") from None
    width = len(rows[0])
    if width == 0 or all(not c.strip() for c in rows[0]):
        raise UploadError("1행이 비어 있습니다(결측). 빈 줄을 지워 주세요.")
    if width > 2:
        raise UploadError(f"1행에 열이 {width}개 있습니다. 막 두께 숫자 열 1개(앞에 시점 열은 선택)만 올려 주세요.")
    first = rows[0][-1].strip()
    if not first:
        raise UploadError("1행: 막 두께 값이 비어 있습니다(결측). 머리글이라면 이름을 적어 주세요.")
    if first.lower() in MISSING_TOKENS:
        raise UploadError(f"1행: 막 두께 값 '{first}'은(는) 결측 표시입니다. 값을 채우거나 그 줄을 지워 주세요.")
    header = _number(first) is None
    values, times = [], []
    for line_no, row in enumerate(rows[1:] if header else rows, start=2 if header else 1):
        if not row or all(not c.strip() for c in row):
            raise UploadError(f"{line_no}행이 비어 있습니다(결측). 값을 채우거나 그 줄을 지워 주세요.")
        if any("\n" in c for c in row):  # 닫히지 않은 따옴표가 다음 줄들을 한 칸으로 삼킨 경우
            raise UploadError(f"{line_no}행: 따옴표가 닫히지 않았습니다.")
        if len(row) != width:
            raise UploadError(f"{line_no}행의 열이 {len(row)}개입니다. 1행처럼 {width}개여야 합니다.")
        cell = row[-1].strip()
        if not cell:
            raise UploadError(f"{line_no}행: 막 두께 값이 비어 있습니다(결측).")
        value = _number(cell)
        if value is None:
            raise UploadError(f"{line_no}행: 막 두께 값 '{cell[:20]}'이(가) 숫자가 아닙니다.")
        if abs(value) > MAX_ABS_VALUE:
            raise UploadError(f"{line_no}행: 막 두께 값 '{cell[:20]}'이(가) 너무 큽니다 (절댓값 10억 이하).")
        values.append(value)
        times.append(row[0].strip() if width == 2 else "")
    if len(values) > MAX_ROWS:
        raise UploadError(f"데이터가 {len(values):,}행입니다. 최대 {MAX_ROWS:,}행까지 판정합니다.")
    if len(values) < MIN_ROWS:
        raise UploadError(f"데이터가 {len(values)}행뿐입니다. {MIN_ROWS}행 이상 올려 주세요.")
    return {"values": values, "times": times if width == 2 else None,
            "name": rows[0][-1].strip() if header else "막 두께"}


def default_phase1(n: int) -> int:
    """앞 N점 기본값: 행 수의 절반과 100 중 작은 값, 최소 20."""
    return max(MIN_PHASE1, min(PHASE1_CAP, n // 2))


def judge_estimated(values: list[float], phase1_n: int) -> dict:
    """앞 phase1_n점으로 한계를 추정(SECOM과 같은 방식: 평균, σ = 평균 이동범위 / 1.128)하고 나머지를 판정한다."""
    if len(values) < MIN_PHASE1 + MIN_ROWS:
        raise UploadError(f"추정 방식은 {MIN_PHASE1 + MIN_ROWS}행 이상 필요합니다 (앞 {MIN_PHASE1}점으로 추정 + "
                          f"{MIN_ROWS}점 이상 감시). 한계를 직접 입력해 주세요.")
    if not MIN_PHASE1 <= phase1_n <= len(values) - MIN_ROWS:
        raise UploadError(f"앞 N점은 {MIN_PHASE1}~{len(values) - MIN_ROWS} 사이여야 합니다.")
    limits = secom.phase1_limits(values[:phase1_n])
    if not math.isfinite(limits["sigma"]) or limits["sigma"] <= 0:
        raise UploadError(f"앞 {phase1_n}점의 값이 모두 같아 한계를 추정할 수 없습니다. 한계를 직접 입력해 주세요.")
    limits, events = secom.monitor(values, phase1_n)
    return {"mode": "estimated", "limits": limits, "events": events, "phase1_n": phase1_n}


def judge_fixed(values: list[float], center: float, ucl: float, lcl: float) -> dict:
    """직접 입력한 한계로 모든 점을 판정한다."""
    if not lcl < center < ucl:
        raise UploadError("관리한계는 LCL < 중심선(CL) < UCL 이어야 합니다.")
    limits = {"center": center, "ucl": ucl, "lcl": lcl}
    return {"mode": "fixed", "limits": limits, "events": rules.detect(values, center, ucl, lcl), "phase1_n": None}


def example_csv(values: list[float], start: str = "2026-09-01 08:00", minutes: int = 30) -> str:
    """예시 CSV (시점, 막 두께). 가상 시리즈 값을 그대로 쓴다."""
    t0 = datetime.strptime(start, "%Y-%m-%d %H:%M")
    rows = ["시점,막두께_nm"]
    rows += [f"{(t0 + timedelta(minutes=minutes * i)):%Y-%m-%d %H:%M},{v:.2f}" for i, v in enumerate(values)]
    return "\n".join(rows) + "\n"
