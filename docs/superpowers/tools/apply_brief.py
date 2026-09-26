# 태스크 브리프의 코드 블록을 저장소에 그대로 옮긴다 (손으로 옮겨 적는 오타 방지).
# 사용법: python apply_brief.py <brief.md> <repo> tests|impl
#   tests: tests/ 아래 파일만 (TDD의 '실패하는 테스트 먼저')
#   impl : 나머지 전부 (구현·스크립트·부분 수정·덧붙이기)
import re
import sys
from pathlib import Path

brief = Path(sys.argv[1]).read_text(encoding="utf-8")
repo = Path(sys.argv[2])
mode = sys.argv[3]

block = r"```[a-z]*\n(.*?)```"
ops = re.compile(
    r"(?P<create>Create `(?P<cpath>[^`]+)`[^\n]*:|Modify `(?P<fpath>[^`]+)` — 전체를 다음으로 교체:)\s*\n+" + block
    + r"|Modify `(?P<mpath>[^`]+)` — 찾을 코드[^\n]*:\s*\n+" + block + r"\s*\n바꿀 코드:\s*\n+" + block
    + r"|Append to `(?P<apath>[^`]+)`[^\n]*:\s*\n+" + block,
    flags=re.S,
)


def wanted(path: str) -> bool:
    return path.startswith("tests/") if mode == "tests" else not path.startswith("tests/")


for m in ops.finditer(brief):
    g = m.groups()
    if m.group("create"):
        path = m.group("cpath") or m.group("fpath")
        if wanted(path):
            target = repo / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(g[3], encoding="utf-8")
            print(f"write {path}")
    elif m.group("mpath"):
        path, old, new = m.group("mpath"), g[5], g[6]
        if wanted(path):
            target = repo / path
            text = target.read_text(encoding="utf-8")
            if text.count(old) != 1:
                sys.exit(f"!! {path}: 찾을 코드가 {text.count(old)}번 나옴")
            target.write_text(text.replace(old, new), encoding="utf-8")
            print(f"edit {path}")
    else:
        path = m.group("apath")
        if wanted(path):
            target = repo / path
            target.write_text(target.read_text(encoding="utf-8").rstrip("\n") + "\n\n\n" + g[8], encoding="utf-8")
            print(f"append {path}")
