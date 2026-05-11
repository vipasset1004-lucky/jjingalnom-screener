# 🎯 진짜 갈놈 — 3중 검증 추천주

3개 스크리너(`divergence`·`new-high`·`smart-money`)의 라이브 스캔 결과를 자동 수집·교차검증해
**"지금 진입(🅰️)"** 과 **"장기 매집(🅱️)"** 두 바구니에 자동 분류해주는 메타 스크리너.

라이브: https://vipasset1004-lucky.github.io/진짜갈놈-screener/

## 흐름

```
[16:00 / 21:00] divergence·new-high·smart-money 자동 스캔
        ↓
[16:10 / 21:10] 본 리포 cron 트리거
        ↓
   3개 results.json fetch → 교차검증 → A/B 분류
        ↓
   unified_results.json + last_update.json 커밋
        ↓
   GitHub Pages 자동 배포
```

## 핵심 로직

- **검증도(verification)**: 한 종목이 잡힌 스크리너 수 (1/2/3). 3중 검증 = 🏆.
- **카테고리**:
  - 🅰️ 단기: ⚡단타·🌅폭발·MACD골크·신고가 추세진행·눌림 재돌파 등
  - 🅱️ 매집: 🎯VCP·💎텐버거·OBV 다이버전스·Wyckoff 매집·long base
  - AB(양쪽 신호): 황금자리 후보
- **안전장치(자동 회피)**: RSI≥80, new-high 과열 경고, divergence 과열,
  failed_breakout, BEAR장+1중 검증.
- **권장 비중**: 검증도 × 시장 레짐(0.4~1.2배).
- **매매가**: new-high의 `entry/stop/target` 우선,
  없으면 smart-money의 `trading_guide.computed` fallback.

## 로컬 실행

```powershell
cd "G:\내 드라이브\진짜갈놈-screener"
python -m src.main
```

`unified_results.json` 생성 후 `index.html` 열면 끝.

## 파일 구조

```
.
├── src/
│   ├── fetch_sources.py    # 3개 GitHub Pages JSON 수집
│   ├── cross_validate.py   # 교차검증·A/B 분류·매매가·비중·안전장치
│   └── main.py             # 파이프라인 진입점
├── .github/workflows/
│   └── scan.yml            # KST 16:10·21:10 cron
├── index.html              # 대시보드 (2탭 + 3중 검증 탭)
├── unified_results.json    # 출력 (자동 생성)
├── last_update.json        # 마지막 갱신 시각
├── ALGORITHM.md            # 알고리즘 상세
└── CLAUDE.md               # AI 협업 가이드
```

## 데이터 출처

- `https://vipasset1004-lucky.github.io/smart-money-screener/results.json`
- `https://vipasset1004-lucky.github.io/new-high-screener/results.json`
- `https://vipasset1004-lucky.github.io/divergence-screener/divergence_results.json`

## 주의

이 도구는 기술적 분석 결과를 통합·표시할 뿐, 투자 자문이 아닙니다.
모든 매매 판단·책임은 사용자에게 있습니다.
