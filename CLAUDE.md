# CLAUDE.md — 진짜 갈놈

AI 협업 가이드. Claude Code/다른 AI가 이 리포에 작업할 때 참고.

## 목적

3개 스크리너(`divergence`·`new-high`·`smart-money`)를 메타 검증해
**"지금 진입(🅰️)"** + **"장기 매집(🅱️)"** 두 바구니에 자동 분류·매매룰까지 부여.

## 절대 원칙

1. **원본 스크리너에 의존**. 시세·수급·재무 데이터는 직접 안 받음. 항상 3개 URL fetch.
2. **매매가는 재계산 금지**. new-high가 이미 entry/stop/target을 계산해 두므로 그대로 차용. fallback만 자체 계산.
3. **빈 결과 허용**. 일부 소스 실패 시 가능한 만큼만 처리하고 종료(이전 결과 덮어쓰지 않음).
4. **외부 의존성 최소화**. 표준 라이브러리만 사용 — GitHub Actions 가볍게.

## 자동화 흐름

- KST 16:10, 21:10 (UTC 07:10, 12:10) cron — 기존 3개 스크리너가 끝난 후 10분 뒤
- `python -m src.main` 실행 → `unified_results.json`, `last_update.json` 갱신
- `main` 브랜치 푸시 → GitHub Pages 자동 배포

## 수정 시 주의

- `cross_validate.py` 의 분류 키워드 상수를 바꾸면 카테고리가 크게 흔들림. 이전 결과와 diff 확인.
- 안전장치(RSI≥80 등) 임계값은 원본 스크리너 알고리즘 명세와 일치 유지.
- `index.html`은 정적 JSON만 fetch — 외부 API 호출 추가 금지(CORS, 무료 한도 등).

## 디버깅

```powershell
# 한 소스만 빠르게 확인
python -c "from src.fetch_sources import fetch_one; import json; p=fetch_one('sm','https://vipasset1004-lucky.github.io/smart-money-screener/results.json'); print(json.dumps(p.data, ensure_ascii=False, indent=2)[:2000])"

# 전체 파이프라인
python -m src.main
```

`unified_results.json`의 `meta.sources` 에 각 소스의 ok/error/scan_at 기록됨 → 무엇이 실패했는지 확인.

## 향후 확장 후보

- 텔레그램 알림 (3중 검증 종목 신규 등장 시)
- 과거 추천 추적·실현수익률 백테스트
- TradingView 위젯 임베드
- 자동매매 API 연동(키움/한투) — `unified_results.json` 의 trading 필드 그대로 주문값으로
