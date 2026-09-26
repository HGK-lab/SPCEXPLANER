#!/usr/bin/env bash
# 앱을 새로 띄우고(모듈 변경을 반영하려고 매번 새로), 준비되면 단계 파일들을 차례로 실행한 뒤 서버를 끈다. (Git Bash, 윈도)
# 사용법: bash docs/superpowers/tools/run_shots.sh <앱 폴더> <포트> <steps.json> [steps.json ...]
set -u
dir=$1; port=$2; shift 2
here=$(cd "$(dirname "$0")" && pwd)
repo=$(cd "$here/../../.." && pwd)
py="$repo/.venv/Scripts/python"
(cd "$dir" && exec "$py" -m streamlit run streamlit_app.py --server.headless true --server.port "$port" \
  >"${TMPDIR:-/tmp}/streamlit-$port.log" 2>&1) &
for _ in $(seq 1 90); do curl -s "localhost:$port/_stcore/health" | grep -q ok && break; sleep 1; done
rc=0
for f in "$@"; do "$py" "$here/cdp_steps.py" "$(cygpath -m "${TMPDIR:-/tmp}")/chrome-$port" "$f" || rc=$?; done
pid=$(netstat -ano | grep LISTENING | grep ":$port " | awk '{print $5}' | head -1)
[ -n "$pid" ] && taskkill //F //PID "$pid" >/dev/null 2>&1
exit $rc
