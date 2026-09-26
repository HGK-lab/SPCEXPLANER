# 계획서의 코드 블록을 추출해 검증용 프로젝트를 만든다.
# 사용법: python extract_plan.py <plan.md> <out_dir> <마지막 태스크 번호, 예: 11-2>
import re
import sys
from pathlib import Path

plan = Path(sys.argv[1]).read_text(encoding="utf-8")
out = Path(sys.argv[2])
upto = sys.argv[3]

# 태스크 단위로 자른다 (문서 순서 유지, 11-1 같은 하위 번호 포함)
parts = re.split(r"^### Task ([0-9]+(?:-[0-9]+)?):", plan, flags=re.M)
tasks = [(parts[i], parts[i + 1]) for i in range(1, len(parts), 2)]

block = r"```[a-z]*\n(.*?)```"
ops = re.compile(
    r"(?P<create>Create `(?P<cpath>[^`]+)`[^\n]*:|Modify `(?P<fpath>[^`]+)` — 전체를 다음으로 교체:)\s*\n+" + block
    + r"|Modify `(?P<mpath>[^`]+)` — 찾을 코드[^\n]*:\s*\n+" + block + r"\s*\n바꿀 코드:\s*\n+" + block
    + r"|Append to `(?P<apath>[^`]+)`[^\n]*:\s*\n+" + block,
    flags=re.S,
)
for label, body in tasks:
    for m in ops.finditer(body):
        g = m.groups()
        if m.group("create"):
            path = m.group("cpath") or m.group("fpath")
            target = out / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(g[3], encoding="utf-8")
            print(f"[task {label}] write {path}")
        elif m.group("mpath"):
            path, old, new = m.group("mpath"), g[5], g[6]
            target = out / path
            text = target.read_text(encoding="utf-8")
            count = text.count(old)
            if count != 1:
                print(f"[task {label}] !! {path}: 찾을 코드가 {count}번 나옴\n---\n{old[:300]}")
                sys.exit(1)
            target.write_text(text.replace(old, new), encoding="utf-8")
            print(f"[task {label}] edit {path}")
        else:
            path = m.group("apath")
            target = out / path
            target.write_text(target.read_text(encoding="utf-8").rstrip("\n") + "\n\n\n" + g[8], encoding="utf-8")
            print(f"[task {label}] append {path}")
    if label == upto:
        break
