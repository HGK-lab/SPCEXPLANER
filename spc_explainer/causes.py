# 원인표: 패턴별 후보 원인과 점검 항목.
# 교과서 수준의 도메인 가정이며 실제 설비 데이터로 검증한 것이 아니다 (README·리포트에 명시).
CAUSES = {
    "SP-1": {"pattern": "spike", "cause": "계측 오류 (측정 위치 오정렬, 계측기 순간 오류)", "check": "같은 웨이퍼 재측정"},
    "SP-2": {"pattern": "spike", "cause": "파티클·이물로 인한 국부 이상", "check": "파티클·결함 검사 결과 확인"},
    "SP-3": {"pattern": "spike", "cause": "가스 유량 순간 이상 (MFC 스파이크)", "check": "해당 런의 MFC 유량 로그 확인"},
    "SP-4": {"pattern": "spike", "cause": "웨이퍼 로딩·척(chuck) 이상", "check": "로딩 로그와 척 상태 확인"},
    "SP-5": {"pattern": "spike", "cause": "레시피·작업 입력 오류", "check": "해당 런의 레시피·작업 이력 확인"},
    "TR-1": {"pattern": "trend", "cause": "챔버 벽 증착물 누적 (클리닝 주기 도래)", "check": "마지막 챔버 클리닝 이후 처리 매수 확인"},
    "TR-2": {"pattern": "trend", "cause": "히터·온도의 점진적 변화", "check": "온도 센서 로그 추이 확인"},
    "TR-3": {"pattern": "trend", "cause": "소스 소모 (전구체 잔량, 타깃 수명)", "check": "소모품 사용량과 교체 시점 확인"},
    "TR-4": {"pattern": "trend", "cause": "펌프 성능 저하로 인한 압력 변화", "check": "챔버 압력 로그 추이 확인"},
    "TR-5": {"pattern": "trend", "cause": "계측기 드리프트", "check": "표준 시편으로 계측기 점검"},
    "SH-1": {"pattern": "shift", "cause": "부품 교체·PM 후 조건 변화", "check": "PM 이력과 치우침 시작 시점 비교"},
    "SH-2": {"pattern": "shift", "cause": "원료 가스·전구체 로트 변경", "check": "원료 로트 변경 이력 확인"},
    "SH-3": {"pattern": "shift", "cause": "레시피 변경", "check": "레시피 변경 이력 확인"},
    "SH-4": {"pattern": "shift", "cause": "계측기 교정값 변경", "check": "계측기 교정 이력 확인"},
    "SH-5": {"pattern": "shift", "cause": "다른 챔버·장비로 전환", "check": "설비 배정 이력 확인"},
}


def rows_for(patterns: set[str]) -> dict[str, dict]:
    """주어진 패턴들의 원인표 행만 뽑는다 (설명 LLM 입력용)."""
    return {cid: row for cid, row in CAUSES.items() if row["pattern"] in patterns}
