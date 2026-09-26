# cdp_steps.py용 단계 파일(JSON) 만들기: 앱을 열고, (선택) 시리즈를 고른 뒤, 요소를 누르거나 잘라 찍는다.
# 사용법: python app_steps.py <out.json> <url> <폭> <모바일 0|1> <시리즈 번호|-> <그림 접두어> [동작 ...]
#   동작 "이름:js"  → 그 요소만 잘라 <접두어>-<이름>.png로 저장
#   동작 "!이름:js" → 그 요소를 누른다 (데스크톱 클릭)
# 예: python app_steps.py s.json http://localhost:8501 1440 0 11 out/b1 "!open:document.querySelector('...')" "card:document.querySelector('.st-key-check_card')"
import json
import sys

out, url, width, mobile, sid, prefix = sys.argv[1:7]
steps = [{"do": "size", "w": int(width), "h": 1400 if mobile == "1" else 1000, "mobile": mobile == "1"},
         {"do": "go", "url": url},
         {"do": "wait", "js": "document.querySelectorAll('.js-plotly-plot').length > 0", "timeout": 120},
         {"do": "idle"}]
if sid != "-":
    steps += [{"do": "click", "js": "document.querySelector('[data-testid=stSelectbox] input')"},
              {"do": "type", "text": f"시리즈 {int(sid):02d}"}, {"do": "key", "key": "Enter", "s": 2}, {"do": "idle"}]
for spec in sys.argv[7:]:
    name, js = spec.split(":", 1)
    if name.startswith("!"):
        steps += [{"do": "click", "js": js, "s": 2}, {"do": "idle"}]
    else:
        steps.append({"do": "shot", "out": f"{prefix}-{name}.png", "js": js, "pad": 6})
with open(out, "w", encoding="utf-8") as f:
    json.dump(steps, f, ensure_ascii=False, indent=1)
