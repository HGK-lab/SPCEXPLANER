# 소개 이미지 문구 점검: 금지 표현이 없고, 슬라이드의 숫자가 모두 docs/portfolio/numbers.md에 있는지.
# 사용법: python docs/portfolio/showcase/check.py  (문제가 있으면 목록을 찍고 종료 코드 1)
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent


class Text(HTMLParser):
    """style·script를 뺀 보이는 글자만 모은다."""
    def __init__(self):
        super().__init__()
        self.skip, self.parts = 0, []

    def handle_starttag(self, tag, attrs):
        self.skip += tag in ("style", "script", "title")

    def handle_endtag(self, tag):
        self.skip -= tag in ("style", "script", "title")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)


def main() -> int:
    parser = Text()
    parser.feed((HERE / "slides.html").read_text(encoding="utf-8"))
    text = " ".join(" ".join(parser.parts).split())
    numbers_md = (ROOT / "docs" / "portfolio" / "numbers.md").read_text(encoding="utf-8")
    problems = []
    # 공고 맞춤 표현, AI 티 나는 장치
    for bad in ("해커톤", "하이닉스", "SK", "심사", "공모", " · ", " — ", "→"):
        if bad in text:
            problems.append(f"금지 표현: {bad!r}")
    names = {"SECOM", "SPCEXPLANER"}  # 데이터셋 이름, 저장소 주소 (라벨이 아님)
    caps = [w for w in re.findall(r"[A-Z]{4,}", text) if w not in names]
    if caps:
        problems.append(f"영문 대문자 라벨: {caps}")
    # 슬라이드 숫자 → numbers.md에 같은 값이 있어야 한다 (표기만 다른 값은 옆에 적음)
    same = {"2.1초": "2.05초", "10.8초": "10.82초", "0.48ms": "0.48ms", "$0.46": "$0.46", "1.3개": "평균 1.3",
            "103건": "103", "6건": "6건", "21/21": "21 / 21", "14/21": "14/21", "24건": "24 (15/3/6)", "48개": "48 / 48"}
    for shown, source in same.items():
        if shown not in text:
            problems.append(f"슬라이드에 없는 숫자(점검 목록 확인): {shown}")
        elif source not in numbers_md:
            problems.append(f"numbers.md에 없는 값: {shown} (찾은 표기 {source!r})")
    for p in problems:
        print("문제:", p)
    print(f"점검 {'통과' if not problems else '실패'} — 글자 {len(text)}자")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
