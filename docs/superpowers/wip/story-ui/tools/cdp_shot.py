# Chrome 원격 디버깅(CDP)으로 페이지를 열고, 실제 렌더링을 기다린 뒤 캡처한다 (검증용 스크립트)
import base64, json, subprocess, sys, time, urllib.request
import websocket

import os
W, H = int(os.environ.get("SHOT_W", 1440)), int(os.environ.get("SHOT_H", 2300))
chrome, profile, port = r"C:\Program Files\Google\Chrome\Application\chrome.exe", sys.argv[1], 9333
jobs = [(sys.argv[i], sys.argv[i + 1]) for i in range(2, len(sys.argv), 2)]  # (url, out.png) 쌍
proc = subprocess.Popen([chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                         f"--remote-debugging-port={port}", "--remote-allow-origins=*", f"--user-data-dir={profile}",
                         f"--window-size={W},{H}", "about:blank"])
try:
    for _ in range(50):
        try:
            targets = json.load(urllib.request.urlopen(f"http://127.0.0.1:{port}/json")); break
        except Exception:
            time.sleep(0.3)
    ws = websocket.create_connection([t for t in targets if t["type"] == "page"][0]["webSocketDebuggerUrl"])
    n = 0
    def cmd(method, params=None):
        global n
        n += 1
        ws.send(json.dumps({"id": n, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(ws.recv())
            if msg.get("id") == n:
                return msg.get("result", {})
    cmd("Emulation.setDeviceMetricsOverride", {"width": W, "height": H, "deviceScaleFactor": 1, "mobile": False})
    for url, out in jobs:
        cmd("Page.navigate", {"url": url})
        time.sleep(12)  # Streamlit 스크립트 실행·렌더링 대기
        data = cmd("Page.captureScreenshot", {"format": "png"})["data"]
        open(out, "wb").write(base64.b64decode(data))
        print("saved", out)
finally:
    proc.kill()
