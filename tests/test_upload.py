# 내 데이터 판정: 입력 검사(결측·문자·행 수·열 수·인코딩), 한계 추정·직접 입력, 가상 시리즈를 CSV로 넣었을 때 같은 판정
import json

import pytest

from spc_explainer import config, rules
from spc_explainer.upload import (MAX_ROWS, UploadError, decode, default_phase1, example_csv, judge_estimated,
                                  judge_fixed, parse, read_input)

SERIES = json.loads(config.SERIES_PATH.read_text(encoding="utf-8"))["series"]


def numbers(n: int, start: float = 100.0) -> str:
    return "\n".join(f"{start + (i % 5) * 0.3:.2f}" for i in range(n))


def test_normal_csv_with_header_and_time_column():
    text = "시점,막두께_nm\n" + "\n".join(f"2026-09-01 {8 + i // 60:02d}:{i % 60:02d},{100 + i * 0.01:.2f}" for i in range(12))
    p = parse(text + "\n\n")  # 끝의 빈 줄은 무시
    assert p["name"] == "막두께_nm" and len(p["values"]) == 12 and p["values"][1] == 100.01
    assert p["times"][0] == "2026-09-01 08:00"


def test_single_column_without_header_and_tab_or_semicolon_paste():
    assert parse(numbers(10))["name"] == "막 두께" and parse(numbers(10))["times"] is None
    assert len(parse("\n".join(f"t{i}\t{100 + i}" for i in range(10)))["values"]) == 10  # 엑셀 복사(탭)
    assert len(parse("\n".join(f"t{i};{100 + i}" for i in range(10)))["values"]) == 10


def test_missing_value_is_rejected_with_line_number():
    lines = numbers(12).split("\n")
    lines[3] = ""
    with pytest.raises(UploadError, match="4행이 비어 있습니다"):
        parse("\n".join(lines))
    with pytest.raises(UploadError, match="3행: 막 두께 값이 비어 있습니다"):
        parse("t,v\nt1,100\nt2,\n" + "\n".join(f"t{i},100" for i in range(10)))


def test_text_value_is_rejected():
    lines = numbers(12).split("\n")
    lines[5] = "10O.2"  # 숫자 0 대신 영문 O
    with pytest.raises(UploadError, match="6행: 막 두께 값 '10O.2'이\\(가\\) 숫자가 아닙니다"):
        parse("\n".join(lines))
    with pytest.raises(UploadError, match="숫자가 아닙니다"):
        parse(numbers(12) + "\nnan")


def test_row_limits_empty_file_and_column_count():
    with pytest.raises(UploadError, match=f"최대 {MAX_ROWS:,}행"):
        parse(numbers(MAX_ROWS + 1))
    assert len(parse(numbers(MAX_ROWS))["values"]) == MAX_ROWS
    with pytest.raises(UploadError, match="10행 이상"):
        parse(numbers(9))
    with pytest.raises(UploadError, match="비어 있습니다"):
        parse(" \n\n")
    with pytest.raises(UploadError, match="열이 3개"):
        parse("a,b,c\n1,2,3")
    with pytest.raises(UploadError, match="2행의 열이 1개"):
        parse("t,v\n100\n" + "\n".join(f"t{i},100" for i in range(10)))


def test_decode_accepts_utf8_and_cp949():
    assert decode("시점,값\n".encode("utf-8-sig")) == "시점,값\n"
    assert decode("시점,값\n".encode("cp949")) == "시점,값\n"
    with pytest.raises(UploadError, match="인코딩"):
        decode(b"\xff\xfe\xfa\x80\x81")


def test_estimated_limits_use_the_first_n_points():
    assert default_phase1(30) == 20 and default_phase1(120) == 60 and default_phase1(2000) == 100
    values = [0.0, 1.0] * 25 + [10.0] + [0.5] * 9  # 앞 50점으로 추정 → 50번 점이 급변
    r = judge_estimated(values, 50)
    assert r["mode"] == "estimated" and r["phase1_n"] == 50 and abs(r["limits"]["sigma"] - 1 / 1.128) < 1e-9
    assert r["events"][0].pattern == "spike" and r["events"][0].start == 50
    assert all(e.start >= 50 for e in r["events"])
    with pytest.raises(UploadError, match="30행 이상"):
        judge_estimated(values[:29], 20)
    with pytest.raises(UploadError, match="모두 같아"):
        judge_estimated([5.0] * 40, 20)
    with pytest.raises(UploadError, match="20~50"):
        judge_estimated(values, 55)


def test_fixed_limits_are_checked():
    r = judge_fixed([100.0] * 9 + [104.0], 100, 103, 97)
    assert r["mode"] == "fixed" and r["phase1_n"] is None and [(e.pattern, e.start) for e in r["events"]] == [("spike", 9)]
    with pytest.raises(UploadError, match="LCL < 중심선"):
        judge_fixed([100.0] * 10, 100, 97, 103)


def test_synthetic_series_as_csv_gives_the_same_judgement():
    for s in (SERIES[11], SERIES[14], SERIES[0]):
        p = parse(example_csv(s["values"]))
        assert p["values"] == s["values"] and p["name"] == "막두께_nm" and p["times"][1] == "2026-09-01 08:30"
        assert judge_fixed(p["values"], config.CENTER, config.UCL, config.LCL)["events"] == rules.detect(s["values"])


def test_empty_uploaded_file_is_an_error_but_empty_paste_is_idle():
    for raw in (b"", b"\xef\xbb\xbf", b"\r\n\r\n"):  # 빈 파일, BOM만 있는 파일(엑셀 빈 시트), 빈 줄뿐
        with pytest.raises(UploadError, match="올린 파일이 비어 있습니다"):
            read_input(raw, "")
    assert read_input(None, "  \n") is None  # 아무것도 안 넣음 → 기다림
    assert read_input(None, "100\n") == "100\n" and read_input("100\n".encode(), "999") == "100\n"  # 파일이 먼저


def test_broken_csv_text_is_rejected_not_crashing():
    with pytest.raises(UploadError, match="NUL"):
        parse("100\x00.1\n" + numbers(12))
    with pytest.raises(UploadError, match="CSV 형식을 읽을 수 없습니다"):
        parse("1" * 140_000 + "\n" + numbers(12))  # 한 칸이 csv 모듈 한도(131072자)를 넘음
    with pytest.raises(UploadError, match="따옴표"):
        parse('t,v\n"t1,100\n' + "\n".join(f"t{i},100" for i in range(12)))


def test_missing_or_nan_first_row_is_not_taken_as_header():
    with pytest.raises(UploadError, match="1행: 막 두께 값이 비어 있습니다"):
        parse("t0,\n" + "\n".join(f"t{i},100" for i in range(1, 20)))
    for token in ("NaN", "inf", "#N/A", "n/a"):
        with pytest.raises(UploadError, match="1행: 막 두께 값"):
            parse(token + "\n" + numbers(20))


def test_absurdly_large_values_are_rejected():
    with pytest.raises(UploadError, match="3행: 막 두께 값 '1e300'이\\(가\\) 너무 큽니다"):
        parse("100\n101\n1e300\n" + numbers(12))


def test_long_spike_run_is_summarized():
    # 추정 한계 뒤로 공정이 크게 옮겨 가면 한계 밖 점이 수백 개 이어진다 → 규칙 문장과 LLM 입력은 요약만
    from spc_explainer.explain import build_input, build_messages
    values = [100.0 + (i % 7 - 3) * 0.2 for i in range(100)] + [110.0 + (i % 5) * 0.1 for i in range(1500)]
    r = judge_estimated(values, 100)
    spike = [e for e in r["events"] if e.pattern == "spike"][0]
    assert spike.end - spike.start + 1 == 1500
    rule = rules.describe(spike, values, r["limits"]["ucl"], r["limits"]["lcl"])
    assert len(rule) < 160 and "외 1497점" in rule
    inp = build_input(values, r["events"], r["limits"])
    item = [e for e in inp["events"] if e["pattern"] == "급변"][0]
    assert len(item["values"]) == 5 and item["n_points"] == 1500 and item["max"] >= item["min"]
    assert len(build_messages(inp)[1]) < 4000
