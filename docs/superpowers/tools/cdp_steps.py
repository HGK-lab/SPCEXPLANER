# Chrome 원격 디버깅(CDP)으로 페이지를 열고 단계별 동작(대기·클릭·터치·입력·캡처)을 실행한다 (검증용 스크립트).
# 사용법: python cdp_steps.py <chrome_profile_dir> <steps.json>
# steps.json은 단계 목록이다. 예:
#   [{"do": "size", "w": 1440, "h": 2600, "mobile": false},
#    {"do": "go", "url": "http://localhost:8501"},
#    {"do": "wait", "js": "document.querySelectorAll('.js-plotly-plot').length > 0", "timeout": 60},
#    {"do": "idle"},                                   Streamlit 실행 표시가 사라질 때까지 대기
#    {"do": "click", "js": "document.querySelector('[data-testid=stSelectbox] input')"},
#    {"do": "tap", "js": "..."},                        터치(모바일) 탭. 앞에 size의 mobile: true 필요
#    {"do": "type", "text": "시리즈 11"}, {"do": "key", "key": "Enter"},
#    {"do": "scroll", "js": "..."},                     요소를 화면 가운데로
#    {"do": "sleep", "s": 2},
#    {"do": "shot", "out": "a.png"}, {"do": "shot", "out": "b.png", "js": "<요소>", "pad": 8},  요소만 잘라 찍기
#    {"do": "eval", "js": "...", "print": true}]
# 요소를 가리키는 js는 요소 하나를 돌려주는 식이어야 한다. 필요 패키지: websocket-client
import base64
import json
import subprocess
import sys
import time
import urllib.request

import websocket

CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PORT = 9334

profile, steps_path = sys.argv[1], sys.argv[2]
steps = json.loads(open(steps_path, encoding="utf-8").read())
proc = subprocess.Popen([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                         f"--remote-debugging-port={PORT}", "--remote-allow-origins=*", f"--user-data-dir={profile}",
                         "--window-size=1440,2600", "about:blank"])
try:
    for _ in range(50):
        try:
            targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{PORT}/json"))
            break
        except Exception:
            time.sleep(0.3)
    ws = websocket.create_connection([t for t in targets if t["type"] == "page"][0]["webSocketDebuggerUrl"])
    counter = [0]

    def cmd(method, params=None):
        counter[0] += 1
        ws.send(json.dumps({"id": counter[0], "method": method, "params": params or {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == counter[0]:
                if "error" in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get("result", {})

    def js(expr):
        r = cmd("Runtime.evaluate", {"expression": expr, "returnByValue": True, "awaitPromise": True})
        if "exceptionDetails" in r:
            raise RuntimeError(f"JS 오류: {r['exceptionDetails'].get('text')} :: {expr[:120]}")
        return r["result"].get("value")

    def rect(expr, scroll=True):
        """요소를 화면 가운데로 스크롤하고 경계 상자(뷰포트 좌표)를 돌려준다."""
        scroll_js = 'el.scrollIntoView({block: "center"});' if scroll else ""
        box = js(f"(() => {{ const el = ({expr}); if (!el) return null; {scroll_js} "
                 "const r = el.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height}; })()")
        if box is None:
            raise RuntimeError(f"요소 없음: {expr[:120]}")
        time.sleep(0.4)
        return js(f"(() => {{ const r = ({expr}).getBoundingClientRect(); return {{x: r.x, y: r.y, w: r.width, h: r.height}}; }})()")

    mobile = False
    for st in steps:
        do = st["do"]
        if do == "size":
            mobile = bool(st.get("mobile"))
            cmd("Emulation.setDeviceMetricsOverride",
                {"width": st["w"], "height": st["h"], "deviceScaleFactor": 1, "mobile": mobile})
            cmd("Emulation.setTouchEmulationEnabled", {"enabled": mobile, "maxTouchPoints": 5 if mobile else 1})
        elif do == "go":
            cmd("Page.navigate", {"url": st["url"]})
            time.sleep(st.get("s", 3))
        elif do == "wait":
            end = time.time() + st.get("timeout", 60)
            while not js(st["js"]):
                if time.time() > end:
                    raise RuntimeError(f"대기 시간 초과: {st['js'][:120]}")
                time.sleep(0.5)
        elif do == "idle":
            # Streamlit이 스크립트를 실행하는 동안 보이는 실행 표시가 없어진 상태가 2초 이어질 때까지
            end, quiet = time.time() + st.get("timeout", 60), 0
            while quiet < 4:
                busy = js("!!document.querySelector('[data-testid=\"stStatusWidget\"]')")
                quiet = 0 if busy else quiet + 1
                if time.time() > end:
                    raise RuntimeError("Streamlit 실행이 끝나지 않음")
                time.sleep(0.5)
        elif do in ("click", "tap"):
            b = rect(st["js"])
            x, y = b["x"] + b["w"] * st.get("fx", 0.5), b["y"] + b["h"] * st.get("fy", 0.5)
            if do == "click":
                for t in ("mouseMoved", "mousePressed", "mouseReleased"):
                    cmd("Input.dispatchMouseEvent", {"type": t, "x": x, "y": y, "button": "left", "clickCount": 1})
            else:  # 실제 손가락 탭처럼 제스처로 보낸다 (브라우저가 click까지 합성한다)
                cmd("Input.synthesizeTapGesture", {"x": x, "y": y, "duration": 50, "tapCount": 1,
                                                   "gestureSourceType": "touch"})
            time.sleep(st.get("s", 1))
        elif do == "type":
            cmd("Input.insertText", {"text": st["text"]})
            time.sleep(st.get("s", 0.8))
        elif do == "key":
            codes = {"Enter": 13, "Escape": 27, "ArrowDown": 40}
            k = st["key"]
            for t in ("keyDown", "keyUp"):
                cmd("Input.dispatchKeyEvent", {"type": t, "key": k, "code": k,
                                               "windowsVirtualKeyCode": codes.get(k, 0)})
            time.sleep(st.get("s", 1))
        elif do == "file":  # {"do": "file", "css": "input[type=file]", "path": "C:/.../a.csv"} 파일 올리기
            root = cmd("DOM.getDocument", {"depth": -1, "pierce": True})["root"]["nodeId"]
            node = cmd("DOM.querySelector", {"nodeId": root, "selector": st["css"]})["nodeId"]
            cmd("DOM.setFileInputFiles", {"nodeId": node, "files": [st["path"]]})
            time.sleep(st.get("s", 2))
        elif do == "scroll":
            rect(st["js"])
        elif do == "sleep":
            time.sleep(st["s"])
        elif do == "shot":
            params = {"format": "png"}
            if st.get("js"):
                b = rect(st["js"], scroll=st.get("scroll", True))
                pad = st.get("pad", 8)
                params["clip"] = {"x": max(0, b["x"] - pad), "y": max(0, b["y"] - pad),
                                  "width": b["w"] + 2 * pad, "height": b["h"] + 2 * pad, "scale": 1}
            data = cmd("Page.captureScreenshot", params)["data"]
            open(st["out"], "wb").write(base64.b64decode(data))
            print("saved", st["out"])
        elif do == "eval":
            value = js(st["js"])
            if st.get("print"):
                print("eval:", json.dumps(value, ensure_ascii=False)[:2000])
        else:
            raise ValueError(f"모르는 단계: {do}")
finally:
    proc.kill()
