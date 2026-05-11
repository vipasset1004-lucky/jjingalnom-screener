# ALGORITHM — 진짜 갈놈

## 1. 데이터 수집

| 소스 | URL | 키 |
|---|---|---|
| smart-money | `smart-money-screener/results.json` | `results[]`, `regime` |
| new-high | `new-high-screener/results.json` | `results[]`, `breadth_trend`, `breadth_scan` |
| divergence | `divergence-screener/divergence_results.json` | `results[]` |

모두 `results[]` 안의 항목이 `ticker` 필드를 키로 가짐 → 교차검증 가능.

## 2. 교차검증 (`cross_validate.py`)

### 검증도
```
verification = 1중 잡힌 스크리너 수 (1, 2, 3)
```

### 카테고리 분류
한 종목이 동시에 두 신호를 가질 수 있으므로 OR 분류 후 두 플래그 결합:

#### 🅰️ 지금 진입
- smart-money: `labels ⊇ {⚡단타, 🌅폭발임박}` 또는 `position.label == 돌파진행`
- new-high: `type ∈ {PULLBACK_REBREAK, TREND_CONTINUE}` 또는 `grade ∈ {A+, A}`
- divergence: `surge_phase` 가 "상승" 계열 또는 `daily_signals` 에 거래량 폭발/MACD 상승/정배열/골든크로스 포함

#### 🅱️ 장기 매집
- smart-money: `labels ⊇ {💎텐버거, 🎯VCP, 🌑매집중}` 또는 `accumulation.in_accumulation==true` 또는 `weekly_pack.vcp.vcp==true` 또는 `accumulation.duration ≥ 200`
- new-high: `vol_dried==true ∧ base_days ≥ 40` 또는 `weinstein.stage`가 Stage1/2-early
- divergence: `signals` 가 OBV/Stochastic/매집/Pocket Pivot/20주선 안착/VCP 포함

→ A만 = `"A"`, B만 = `"B"`, 둘 다 = `"AB"` (황금자리 후보)

### 합산 점수
```
combined_score = mean( smart_money.score.total,
                       new_high.score,
                       divergence.score_100 )    # 통과 소스만
```

## 3. 매매가 결정 (`_pick_trading_levels`)

우선순위:
1. new-high의 `entry_price / stop_loss / target_1 / target_2 / trailing_stop`
2. smart-money의 `trading_guide.computed.{stop_price, tp1_price, tp2_price}` + current_price를 entry로
3. fallback: current_price 기준 −5% / +15% / +30%

## 4. 권장 비중 (`_position_size_pct`)

```
base = {3:12, 2:8, 1:5}[verification]     # %

regime_score < 35 → × 0.4    (BEAR)
            < 50 → × 0.6    (약세)
            < 65 → × 0.8    (중립)
            < 80 → × 1.0    (강세)
            else → × 1.2    (불장)
```

## 5. 안전장치 (자동 회피)

다음 중 하나 해당 시 `action = "회피"`:

- `RSI ≥ 80` (new-high.rsi 또는 divergence.daily_rsi)
- `new_high.is_overheated_warn == true`
- `divergence.is_overheated == true`
- `new_high.failed_breakout == true`
- `regime_score < 40 ∧ verification < 2` (BEAR + 약한 검증)

## 6. 액션 등급

| 조건 | 라벨 | 이모지 |
|---|---|---|
| 안전장치 발동 | 회피 | ⛔ |
| 3중 검증 + 안전 | 강력 매수 | 🏆 |
| 2중 검증 + 안전 | 매수 | 🥇 |
| 1중 검증 + 안전 | 관심 | 👀 |

## 7. 정렬

기본: `(-verification, -combined_score)` 사전식.
UI에서 합산점수/가격으로 재정렬 가능.

## 8. 데이터 신선도

`last_update.json` 의 `updated_at` 으로 본 리포 갱신 시각 기록.
원 소스(`meta.sources.*.scan_at`)가 30시간 이상 경과 시 UI에서 ⚠️ 표시.
