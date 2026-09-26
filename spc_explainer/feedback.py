# "오탐이에요" 피드백: 이 세션 안에만 모은다 (외부 저장소에 쓰지 않는다). 시연용이다.
import csv
import io

DEMO_NOTE = "시연용: 실제 운영에서는 이 피드백으로 규칙·원인표를 개선한다"
COLUMNS = {"series": "시리즈", "event_id": "사건", "pattern": "패턴", "span": "구간", "rule": "근거 규칙",
           "time": "표시 시각"}


def _key(e: dict) -> tuple:
    return e["series"], e["pattern"], e["span"]


def is_flagged(entries: list[dict], series: str, pattern: str, span: str) -> bool:
    return any(_key(e) == (series, pattern, span) for e in entries)


def toggle(entries: list[dict], entry: dict) -> list[dict]:
    """같은 사건(시리즈·패턴·구간)이 이미 있으면 뺀(취소) 목록, 없으면 더한 목록을 새로 만든다."""
    if is_flagged(entries, *_key(entry)):
        return [e for e in entries if _key(e) != _key(entry)]
    return entries + [entry]


def to_csv(entries: list[dict]) -> str:
    """피드백 목록 CSV (머리글은 한국어)."""
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\n")
    writer.writerow(COLUMNS.values())
    for e in entries:
        writer.writerow([e[k] for k in COLUMNS])
    return buf.getvalue()


def table(entries: list[dict]) -> list[dict]:
    """화면 표용: 열 이름을 한국어로."""
    return [{label: e[k] for k, label in COLUMNS.items()} for e in entries]
