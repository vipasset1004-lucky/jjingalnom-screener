"""3개 스크리너 결과를 ticker 기준으로 교차검증하고 A/B로 분류한다."""
from __future__ import annotations

from typing import Any

# === 분류 키워드 ============================================================
# A: 지금 진입 (단기 수익)
A_SMARTMONEY_LABELS = {"⚡단타", "🌅폭발임박"}
A_SMARTMONEY_POSITION = {"돌파진행"}
A_NEWHIGH_TYPES = {"PULLBACK_REBREAK", "TREND_CONTINUE"}
A_NEWHIGH_GRADES = {"A+", "A"}
A_DIVERGENCE_PHASES_KEYWORDS = ("상승 추세", "상승 중반", "상승 초기")
A_DIVERGENCE_DAILY_KEYWORDS = ("거래량 폭발", "거래량 폭발 ", "MACD 상승", "5일선 돌파", "정배열", "골든크로스")

# B: 장기 횡보 → 빅무브 준비
B_SMARTMONEY_LABELS = {"💎텐버거", "🎯VCP", "🌑매집중"}
B_NEWHIGH_TYPES = {"BREAKOUT_BOTTOM"}  # 폐기됐지만 혹시 남아있을 시
B_DIVERGENCE_KEYWORDS = (
    "OBV", "Stochastic", "매집", "거래량 선행 매집", "Pocket Pivot",
    "20주선 안착", "바닥", "수렴", "VCP",
)
B_DIVERGENCE_PHASES_KEYWORDS = ("매집", "바닥", "수렴")


# === 정규화/추출 헬퍼 ========================================================
def _safe_get(obj: Any, *path: str, default: Any = None) -> Any:
    cur = obj
    for k in path:
        if cur is None:
            return default
        if isinstance(cur, dict):
            cur = cur.get(k, default if k == path[-1] else None)
        else:
            return default
    return cur if cur is not None else default


def _index_by_ticker(items: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for it in items or []:
        t = str(it.get("ticker") or "").strip()
        if not t:
            continue
        out[t] = it
    return out


# === 카테고리 판별 (신호 강도 점수제) =======================================
# 한 소스의 강한 신호 = 2점, 약한 신호 = 1점.
# A 또는 B 임계값(=2점)을 넘으면 그 카테고리 후보.
# A와 B 둘 다 강할 때만 AB(황금자리). 그 외는 강한 쪽 하나만.

def _a_signals_per_source(sm, nh, dv) -> tuple[int, int, int]:
    """A 신호 점수를 (smart_money, new_high, divergence) 각각 반환."""
    sm_pt = 0
    nh_pt = 0
    dv_pt = 0
    if sm:
        labels = set(sm.get("labels") or [])
        if labels & {"⚡단타", "🌅폭발임박"}:
            sm_pt = 2
        elif _safe_get(sm, "position", "label") == "돌파진행":
            sm_pt = 1
    if nh:
        grade = nh.get("grade") or ""
        type_ = nh.get("type") or ""
        if grade == "A+" and type_ in A_NEWHIGH_TYPES:
            nh_pt = 2
        elif grade in {"A+", "A"} and type_ in A_NEWHIGH_TYPES:
            nh_pt = 1
        elif grade == "A+":
            nh_pt = 1
    if dv:
        phase = dv.get("surge_phase") or ""
        daily = dv.get("daily_signals") or []
        has_action = any(
            ("거래량 폭발" in x) or ("MACD 상승" in x) or ("정배열" in x) or ("골든크로스" in x) or ("5일선 돌파" in x)
            for x in daily
        )
        if phase in {"상승 추세", "상승 중반"} and has_action:
            dv_pt = 2
        elif phase in {"상승 추세", "상승 중반"}:
            dv_pt = 1
    return sm_pt, nh_pt, dv_pt


def _b_signals_per_source(sm, nh, dv) -> tuple[int, int, int]:
    """B 신호 점수를 (smart_money, new_high, divergence) 각각 반환."""
    sm_pt = 0
    nh_pt = 0
    dv_pt = 0
    if sm:
        labels = set(sm.get("labels") or [])
        if labels & {"💎텐버거"}:
            sm_pt += 2
        if labels & {"🎯VCP", "🌑매집중"}:
            sm_pt += 2
        weekly_vcp = _safe_get(sm, "weekly_pack", "vcp", "vcp") is True
        if weekly_vcp:
            sm_pt += 2
        in_accum = _safe_get(sm, "accumulation", "in_accumulation") is True
        duration = _safe_get(sm, "accumulation", "duration") or 0
        if in_accum and duration >= 200:
            sm_pt += 1
        if labels & {"⚡단타", "🌅폭발임박"}:
            sm_pt = max(0, sm_pt - 2)  # 이미 출발한 종목은 매집 후보 약화
    if nh:
        weinstein_stage = _safe_get(nh, "weinstein", "stage") or ""
        weinstein_sub = _safe_get(nh, "weinstein", "sub") or ""
        if "Stage1" in weinstein_stage:
            nh_pt += 2
        elif "Stage2" in weinstein_stage and "early" in weinstein_sub:
            nh_pt += 1
        if nh.get("vol_dried") is True and (nh.get("base_days") or 0) >= 60:
            nh_pt += 1
        if nh.get("is_prime_s") and nh.get("prime_s_sub") == "Safe":
            nh_pt += 1
    if dv:
        signals = dv.get("signals") or []
        strong_b = ("OBV", "거래량 선행 매집", "매집비율", "Pocket Pivot")
        if any(any(k in x for k in strong_b) for x in signals):
            dv_pt += 2
        phase = dv.get("surge_phase") or ""
        if any(k in phase for k in ("매집", "바닥", "수렴")):
            dv_pt += 2
        if any("20주선 안착" in x for x in signals):
            dv_pt += 1
    return sm_pt, nh_pt, dv_pt


# === 💎 진짜 갈놈 합성 점수 ==================================================
# 세 알고리즘의 고유 강점을 시간축에 맞춰 가중 결합:
#   T-N 매집 진행  → divergence (30점)
#   T-0 출발 시점  → smart-money (35점)
#   T+N 추세 검증  → new-high (25점)
#   + 폭발 잠재력  → 시총·매집기간·미발견 (10점)

def _accumulation_subscore(dv: dict[str, Any] | None) -> tuple[int, list[str]]:
    """divergence 기반 매집 발견 점수 (0~30)."""
    score = 0
    hits: list[str] = []
    if not dv:
        return 0, []
    signals = dv.get("signals") or []
    sig_text = " | ".join(signals)
    if "OBV" in sig_text:
        score += 15; hits.append("OBV 다이버전스")
    if "Stochastic" in sig_text or "Stoch" in sig_text:
        score += 8; hits.append("Stochastic 다이버전스")
    if "Pocket Pivot" in sig_text:
        score += 7; hits.append("Pocket Pivot")
    if "매집비율" in sig_text or "거래량 선행 매집" in sig_text:
        score += 7; hits.append("거래량 선행 매집")
    if "20주선 안착" in sig_text:
        score += 4; hits.append("20주선 안착")
    if "트렌드 구조 양호" in sig_text:
        score += 3; hits.append("트렌드 구조")
    # 보너스: 주봉 다이버전스 강도
    score_100 = dv.get("score_100") or 0
    if score_100 >= 70:
        score += 3
    elif score_100 >= 50:
        score += 1
    return min(30, score), hits


def _ignition_subscore(sm: dict[str, Any] | None) -> tuple[int, list[str]]:
    """smart-money 기반 출발 신호 점수 (0~35)."""
    score = 0
    hits: list[str] = []
    if not sm:
        return 0, []
    # 수급 일치도 — 외인+기관 동시 매수
    conf = _safe_get(sm, "score", "confluence") or 0
    if conf >= 20:
        score += 12; hits.append("외인+기관 동시매수")
    elif conf >= 10:
        score += 6; hits.append("수급 일치")
    # 출발 신호 — position.label
    pos_label = _safe_get(sm, "position", "label") or ""
    if pos_label == "돌파진행":
        score += 10; hits.append("Stage 1→2 전환")
    elif pos_label in ("관찰", "매집"):
        score += 3
    # 수급 총점
    total = _safe_get(sm, "score", "total") or 0
    if total >= 70:
        score += 8; hits.append(f"수급점수 {total:.0f}")
    elif total >= 50:
        score += 4
    # VCP 주봉 확인
    if _safe_get(sm, "weekly_pack", "vcp", "vcp") is True:
        score += 5; hits.append("주봉 VCP")
    # 라벨로 보조
    labels = set(sm.get("labels") or [])
    if "⚡단타" in labels and "🌅폭발임박" in labels:
        score += 3
    return min(35, score), hits


def _trend_subscore(nh: dict[str, Any] | None) -> tuple[int, list[str]]:
    """new-high 기반 추세 검증 점수 (0~25)."""
    score = 0
    hits: list[str] = []
    if not nh:
        return 0, []
    # Trend Template 8/8
    tmpl = nh.get("template_cnt") or 0
    if tmpl >= 8:
        score += 10; hits.append(f"Trend Template {tmpl}/8")
    elif tmpl >= 6:
        score += 6
    # Retest 76% 승률
    if nh.get("retest") is True:
        score += 8; hits.append("Retest 76%")
    elif nh.get("retest_bonus") is True:
        score += 4
    # PRIME-S 등급
    if nh.get("is_prime_s") is True:
        score += 5; hits.append(f"PRIME-S {nh.get('prime_s_sub') or ''}")
    elif nh.get("is_prime") is True:
        score += 3; hits.append("PRIME")
    elif nh.get("grade") == "A+":
        score += 2
    # ATH 근접 (52주 신고가)
    if nh.get("is_ath") is True:
        score += 2; hits.append("ATH")
    return min(25, score), hits


def _explosion_subscore(
    sm: dict[str, Any] | None,
    nh: dict[str, Any] | None,
    dv: dict[str, Any] | None,
    acc: int, ign: int, trend: int,
) -> tuple[int, list[str]]:
    """폭발 잠재력 보너스 (0~10): 시총↓ + 매집기간↑ + 미발견."""
    score = 0
    hits: list[str] = []
    # 시총 (smart-money.marcap 단위: 원)
    mcap_won = _safe_get(sm, "marcap")
    if isinstance(mcap_won, (int, float)) and mcap_won > 0:
        mcap_eok = mcap_won / 1e8  # 억원
        if mcap_eok < 3000:
            score += 5; hits.append(f"소형주 {mcap_eok:.0f}억")
        elif mcap_eok < 7000:
            score += 3; hits.append(f"중소형 {mcap_eok:.0f}억")
        elif mcap_eok < 15000:
            score += 1
    # 매집 기간
    dur = _safe_get(sm, "accumulation", "duration") or 0
    if dur >= 400:
        score += 3; hits.append(f"장기 매집 {dur}일")
    elif dur >= 200:
        score += 2; hits.append(f"매집 {dur}일")
    elif dur >= 100:
        score += 1
    # 미발견 보너스: 단일 소스인데 강한 신호
    sources = sum(1 for x in [sm, nh, dv] if x)
    if sources == 1:
        max_sub = max(acc, ign, trend)
        if max_sub >= 18:
            score += 2; hits.append("미발견 강신호")
    return min(10, score), hits


def _genuine_score(sm, nh, dv) -> dict[str, Any]:
    acc, acc_hits = _accumulation_subscore(dv)
    ign, ign_hits = _ignition_subscore(sm)
    trend, trend_hits = _trend_subscore(nh)
    expl, expl_hits = _explosion_subscore(sm, nh, dv, acc, ign, trend)
    total = acc + ign + trend + expl
    if total >= 80:
        rank = ("이그니션", "🚀")
    elif total >= 60:
        rank = ("다이아몬드", "💎")
    elif total >= 40:
        rank = ("레이더", "🔍")
    elif total >= 20:
        rank = ("씨앗", "🌱")
    else:
        rank = ("미관심", "")
    return {
        "total": total,
        "rank": rank[0],
        "rank_emoji": rank[1],
        "breakdown": {
            "accumulation": acc,
            "ignition": ign,
            "trend": trend,
            "explosion": expl,
        },
        "hits": {
            "accumulation": acc_hits,
            "ignition": ign_hits,
            "trend": trend_hits,
            "explosion": expl_hits,
        },
    }


# === 🚀 갈놈 코어 점수 ========================================================
# "신호 강도"가 아닌 "실제 갈 가능성"을 측정.
# 핵심 조합: 소형주 + OBV 매집 + RSI 안전 + 과속 안 함 + 매집 길이 + 출발 임박.

def _core_score(sm, nh, dv) -> dict[str, Any]:
    score = 0
    hits: list[str] = []
    penalties: list[str] = []

    # === 시총 — 35점 (소형주 폭발력) ===
    mcap_won = _safe_get(sm, "marcap")
    if isinstance(mcap_won, (int, float)) and mcap_won > 0:
        mcap_eok = mcap_won / 1e8
        if mcap_eok < 1000:
            score += 30; hits.append(f"극소형 {mcap_eok:.0f}억")
        elif mcap_eok < 2500:
            score += 25; hits.append(f"초소형 {mcap_eok:.0f}억")
        elif mcap_eok < 5000:
            score += 18; hits.append(f"소형 {mcap_eok:.0f}억")
        elif mcap_eok < 10000:
            score += 10; hits.append(f"중소형 {mcap_eok:.0f}억")
        elif mcap_eok < 30000:
            score += 3
        # 대형주는 0점

    # === OBV / 매집 신호 — 30점 ===
    dv_signals = (dv or {}).get("signals") or []
    sig_text = " | ".join(dv_signals)
    obv_sub = 0
    if "OBV" in sig_text:
        obv_sub += 18; hits.append("OBV 다이버전스")
    if "거래량 선행 매집" in sig_text:
        obv_sub += 8; hits.append("거래량 매집")
    if "매집비율" in sig_text:
        obv_sub += 5
    if "Pocket Pivot" in sig_text:
        obv_sub += 5; hits.append("Pocket Pivot")
    if "20주선 안착" in sig_text:
        obv_sub += 3
    score += min(30, obv_sub)

    # 외인+기관 동시 매집 — 5점 보너스
    sm_conf = _safe_get(sm, "score", "confluence") or 0
    if sm_conf >= 20:
        score += 5; hits.append("외인+기관 매집")

    # === RSI 안전 — 20점 (75+ 페널티) ===
    rsi = _safe_get(nh, "rsi") or _safe_get(dv, "daily_rsi") or _safe_get(dv, "current_rsi")
    if isinstance(rsi, (int, float)):
        if rsi < 50:
            score += 20; hits.append(f"RSI {rsi:.0f} 매우 안전")
        elif rsi < 60:
            score += 18; hits.append(f"RSI {rsi:.0f} 안전")
        elif rsi < 70:
            score += 12
        elif rsi < 75:
            score += 5
        elif rsi < 80:
            score -= 5; penalties.append(f"RSI {rsi:.0f} 부담")
        else:
            score -= 15; penalties.append(f"RSI {rsi:.0f} 과열")
    else:
        score += 8  # RSI 데이터 없음 = 중립

    # === 과속 안 함 — 15점 (30%+ 페널티) ===
    ret_20d = _safe_get(nh, "ret_20d")
    if isinstance(ret_20d, (int, float)):
        if ret_20d < 5:
            score += 15; hits.append("최근 횡보 (잠재력)")
        elif ret_20d < 15:
            score += 12
        elif ret_20d < 25:
            score += 6
        elif ret_20d < 35:
            pass
        else:
            score -= 10; penalties.append(f"20일 +{ret_20d:.0f}% 과속")
    else:
        score += 5

    # === 매집 기간 — 10점 ===
    dur = _safe_get(sm, "accumulation", "duration") or 0
    if dur >= 400:
        score += 10; hits.append(f"장기 매집 {dur}일")
    elif dur >= 250:
        score += 7; hits.append(f"매집 {dur}일")
    elif dur >= 150:
        score += 4

    # === 출발 임박 / 실적 — 10점 ===
    labels = set((sm or {}).get("labels") or [])
    if "🌅폭발임박" in labels and "⚡단타" in labels:
        score += 8; hits.append("출발 동시 점등")
    elif "🌅폭발임박" in labels:
        score += 5; hits.append("폭발 임박")
    elif "⚡단타" in labels:
        score += 4
    elif "🎯VCP" in labels:
        score += 3; hits.append("VCP 진행")

    # === 실적 가중 ===
    if any(("적자전환" in lab) or ("💀" in lab) for lab in labels):
        score -= 8; penalties.append("적자 전환")
    elif any("적자" in lab for lab in labels):
        score -= 4
    elif any(("실적폭발" in lab) or ("🔥실적" in lab) for lab in labels):
        score += 4; hits.append("실적 폭발")
    elif any(("흑자전환" in lab) or ("🔄흑자" in lab) for lab in labels):
        score += 3; hits.append("흑자 전환")

    score = max(0, min(120, score))

    if score >= 80:
        rank = ("핵폭발", "🚀")
    elif score >= 65:
        rank = ("진짜 갈놈", "💥")
    elif score >= 50:
        rank = ("강력 후보", "🎯")
    elif score >= 35:
        rank = ("관찰", "🔍")
    else:
        rank = ("부적합", "")

    return {
        "score": score,
        "rank": rank[0],
        "rank_emoji": rank[1],
        "hits": hits,
        "penalties": penalties,
    }


def _classify(sm, nh, dv) -> tuple[str | None, int, int]:
    """A/B 분류 — 다중 소스 합의 필수.
       조건: 점수 매긴 소스가 2개 이상 ∧ 총점 ≥ 3.
       AB(황금자리)는 양쪽 다 강한 합의가 있을 때만 (총점 5+ 각각)."""
    a_per = _a_signals_per_source(sm, nh, dv)
    b_per = _b_signals_per_source(sm, nh, dv)
    a_total = sum(a_per)
    b_total = sum(b_per)
    a_sources = sum(1 for x in a_per if x > 0)
    b_sources = sum(1 for x in b_per if x > 0)

    is_a = a_sources >= 2 and a_total >= 3
    is_b = b_sources >= 2 and b_total >= 3

    if is_a and is_b:
        # AB는 양쪽이 모두 매우 강할 때만 (5점 이상 각각)
        if a_total >= 5 and b_total >= 5:
            return ("AB", a_total, b_total)
        return ("A", a_total, b_total) if a_total >= b_total else ("B", a_total, b_total)
    if is_a:
        return ("A", a_total, b_total)
    if is_b:
        return ("B", a_total, b_total)
    return (None, a_total, b_total)


# === 점수 통합 ===============================================================
def _normalized_score(sm: dict[str, Any] | None, nh: dict[str, Any] | None, dv: dict[str, Any] | None) -> float:
    """각 스크리너 점수를 0~100으로 정규화 후 평균. 검증 통과한 소스만 사용."""
    scores: list[float] = []
    if sm:
        s = _safe_get(sm, "score", "total")
        if isinstance(s, (int, float)):
            scores.append(min(100.0, max(0.0, float(s))))
    if nh:
        s = nh.get("score")
        if isinstance(s, (int, float)):
            scores.append(min(100.0, max(0.0, float(s))))
    if dv:
        s = dv.get("score_100")
        if isinstance(s, (int, float)):
            scores.append(min(100.0, max(0.0, float(s))))
    return round(sum(scores) / len(scores), 1) if scores else 0.0


def _extract_name(sm: Any, nh: Any, dv: Any) -> str:
    for src in (sm, nh, dv):
        if src and src.get("name"):
            return src["name"]
    return ""


def _extract_market(sm: Any, nh: Any) -> str:
    if sm and sm.get("market"):
        return sm["market"]
    if nh and nh.get("market"):
        return nh["market"]
    return ""


def _extract_themes(sm: Any, nh: Any, dv: Any) -> list[str]:
    for src in (nh, dv, sm):
        if src and src.get("themes"):
            return list(src["themes"])
    return []


def _extract_current_price(sm: Any, nh: Any, dv: Any) -> float | None:
    candidates = [
        _safe_get(nh, "current_price"),
        _safe_get(dv, "current_price"),
        _safe_get(sm, "metrics", "close"),
    ]
    for c in candidates:
        if isinstance(c, (int, float)) and c > 0:
            return float(c)
    return None


# === 추천 매매가 결정 ========================================================
def _pick_trading_levels(sm: Any, nh: Any, current_price: float | None) -> dict[str, Any]:
    """new-high에 entry/stop/target이 있으면 우선, 없으면 smart-money trading_guide.computed 사용."""
    if nh:
        ep = nh.get("entry_price")
        sl = nh.get("stop_loss")
        t1 = nh.get("target_1")
        t2 = nh.get("target_2")
        if all(isinstance(x, (int, float)) for x in [ep, sl, t1, t2]):
            return {
                "source": "new_high",
                "entry": float(ep),
                "stop": float(sl),
                "tp1": float(t1),
                "tp2": float(t2),
                "trailing": nh.get("trailing_stop"),
            }
    if sm:
        comp = _safe_get(sm, "trading_guide", "computed") or {}
        rule = _safe_get(sm, "trading_guide", "rule") or {}
        if comp.get("stop_price") and comp.get("tp1_price"):
            return {
                "source": "smart_money",
                "entry": current_price,
                "stop": float(comp["stop_price"]),
                "tp1": float(comp["tp1_price"]),
                "tp2": float(comp.get("tp2_price") or 0) or None,
                "size_rule": rule.get("size"),
                "horizon": rule.get("horizon"),
                "note": rule.get("note"),
            }
    # fallback
    if current_price:
        return {
            "source": "fallback_default",
            "entry": current_price,
            "stop": round(current_price * 0.95, 2),
            "tp1": round(current_price * 1.15, 2),
            "tp2": round(current_price * 1.30, 2),
        }
    return {"source": "none"}


# === 비중 결정 ===============================================================
def _position_size_pct(verification: int, regime_score: float | None) -> float:
    """검증도 × 시장 레짐 → 권장 비중(%)."""
    base = {3: 12.0, 2: 8.0, 1: 5.0}.get(verification, 0.0)
    if regime_score is None:
        return base
    if regime_score < 35:
        mult = 0.4
    elif regime_score < 50:
        mult = 0.6
    elif regime_score < 65:
        mult = 0.8
    elif regime_score < 80:
        mult = 1.0
    else:
        mult = 1.2
    return round(base * mult, 1)


# === 메인 진입점 =============================================================
def cross_validate(smart_money: dict, new_high: dict, divergence: dict) -> dict[str, Any]:
    sm_items = _index_by_ticker(smart_money.get("results") or [])
    nh_items = _index_by_ticker(new_high.get("results") or [])
    dv_items = _index_by_ticker(divergence.get("results") or [])

    all_tickers = set(sm_items) | set(nh_items) | set(dv_items)

    regime_score = _safe_get(smart_money, "regime", "score")
    regime_mode = _safe_get(smart_money, "regime", "mode") or ""
    breadth_trend = new_high.get("breadth_trend") or ""

    unified: list[dict[str, Any]] = []
    for t in all_tickers:
        sm, nh, dv = sm_items.get(t), nh_items.get(t), dv_items.get(t)

        sources: list[str] = []
        if sm: sources.append("smart_money")
        if nh: sources.append("new_high")
        if dv: sources.append("divergence")
        verification = len(sources)

        category, a_sig, b_sig = _classify(sm, nh, dv)
        genuine = _genuine_score(sm, nh, dv)
        core = _core_score(sm, nh, dv)

        # A/B 분류 실패 종목은 genuine_score 20점 이상일 때만 유지
        # (1중 검증이지만 강한 매집/추세 신호인 잠재력 종목)
        if category is None:
            if genuine["total"] < 20:
                continue
            category = "watch"  # 별도 표시

        score = _normalized_score(sm, nh, dv)
        current_price = _extract_current_price(sm, nh, dv)
        levels = _pick_trading_levels(sm, nh, current_price)
        position_pct = _position_size_pct(verification, regime_score)

        # 안전장치: 과열 / 페일 진입 차단
        block_reasons: list[str] = []
        rsi = _safe_get(nh, "rsi") or _safe_get(dv, "daily_rsi")
        if isinstance(rsi, (int, float)) and rsi >= 80:
            block_reasons.append(f"RSI {rsi:.0f} 과열")
        if _safe_get(nh, "is_overheated_warn") is True:
            block_reasons.append("new-high 과열 경고")
        if dv and dv.get("is_overheated") is True:
            block_reasons.append("divergence 과열")
        if nh and nh.get("failed_breakout") is True:
            block_reasons.append("실패 돌파")
        if regime_score is not None and regime_score < 40 and verification < 2:
            block_reasons.append("BEAR장 + 단일 검증")

        # 신호 요약
        signals: list[str] = []
        if sm:
            signals.append("⚡ smart-money " + " ".join(sm.get("labels") or []))
        if nh:
            signals.append(f"🎯 new-high {nh.get('grade','')} {nh.get('score','')} {nh.get('type_ko') or ''}")
        if dv:
            grade = dv.get("grade") or ""
            sigs = dv.get("signals") or []
            top_sig = sigs[0] if sigs else ""
            signals.append(f"📈 divergence {grade} {dv.get('score_100','')} {top_sig}")

        # === 3단계 매수 신호 (✅ 사도 OK / ⚠️ 조심 분할 / ⛔ 회피) ===
        sm_labels_set = (sm or {}).get("labels") or []

        if block_reasons:
            action_level = "avoid"
            action_emoji = "⛔"
            action = "회피"
            action_reasons = list(block_reasons)
        else:
            cautions: list[str] = []

            # RSI 70~79 — 과열 직전 경고
            if isinstance(rsi, (int, float)) and 70 <= rsi < 80:
                cautions.append(f"RSI {rsi:.0f} 다소 높음")

            # 단일 소스만 잡힘 — 다중 합의 부재
            if verification == 1:
                cautions.append("단일 소스 신호")

            # 적자 기업
            if any(("적자" in lab) or ("💀" in lab) or ("⚠️적자" in lab) for lab in sm_labels_set):
                cautions.append("적자 기업")

            # 추세 검증 부족 (new-high에서 점수 못 받은 경우)
            if (genuine["breakdown"].get("trend") or 0) == 0 and (genuine["breakdown"].get("accumulation") or 0) > 0:
                cautions.append("추세 검증 부족")

            # 매집은 강한데 출발 신호 미발현
            if (genuine["breakdown"].get("ignition") or 0) == 0 and (genuine["breakdown"].get("accumulation") or 0) >= 15:
                cautions.append("출발 신호 미발현")

            # 종합 점수 부족 (40점 미만이지만 분류엔 잡힘)
            if genuine["total"] < 40:
                cautions.append("종합 점수 부족")

            # 사이클/이미 큰 폭 상승 — new-high의 ret_20d 검사
            if nh:
                ret_20d = nh.get("ret_20d")
                if isinstance(ret_20d, (int, float)) and ret_20d >= 30:
                    cautions.append(f"20일 +{ret_20d:.0f}% 과속")

            # 결정
            if not cautions and verification >= 2 and genuine["total"] >= 40:
                action_level = "safe"
                action_emoji = "✅"
                action = "사도 OK"
                action_reasons = []
            else:
                action_level = "cautious"
                action_emoji = "⚠️"
                action = "조심 분할"
                action_reasons = cautions

        # 보조 지표(카드 표시용)만 추출 — 원본 raw는 제거(용량 90%+ 절감)
        rsi_val = _safe_get(nh, "rsi") or _safe_get(dv, "daily_rsi")
        sm_score = _safe_get(sm, "score", "total")
        nh_score = nh.get("score") if nh else None
        dv_score = dv.get("score_100") if dv else None

        unified.append({
            "ticker": t,
            "name": _extract_name(sm, nh, dv),
            "market": _extract_market(sm, nh),
            "themes": _extract_themes(sm, nh, dv),
            "category": category,
            "verification": verification,
            "sources": sources,
            "combined_score": score,
            "current_price": current_price,
            "trading": levels,
            "position_size_pct": position_pct,
            "action": action,
            "action_level": action_level,   # safe / cautious / avoid
            "action_emoji": action_emoji,
            "action_reasons": action_reasons,
            "block_reasons": block_reasons,
            "signals_summary": signals,
            "a_signal": a_sig,
            "b_signal": b_sig,
            "genuine_score": genuine["total"],
            "genuine_rank": genuine["rank"],
            "genuine_rank_emoji": genuine["rank_emoji"],
            "genuine_breakdown": genuine["breakdown"],
            "genuine_hits": genuine["hits"],
            "core_score": core["score"],
            "core_rank": core["rank"],
            "core_rank_emoji": core["rank_emoji"],
            "core_hits": core["hits"],
            "core_penalties": core["penalties"],
            "metrics": {
                "rsi": rsi_val,
                "sm_score": sm_score,
                "nh_score": nh_score,
                "dv_score": dv_score,
                "sm_labels": (sm or {}).get("labels") or [],
                "nh_type_ko": (nh or {}).get("type_ko"),
                "nh_grade": (nh or {}).get("grade"),
                "dv_grade": (dv or {}).get("grade"),
            },
        })

    # 정렬: 검증도 ↓ → 합산 점수 ↓
    unified.sort(key=lambda x: (-x["verification"], -x["combined_score"]))

    return {
        "regime": {
            "smart_money_score": regime_score,
            "smart_money_mode": regime_mode,
            "smart_money_label": _safe_get(smart_money, "regime", "label"),
            "smart_money_advice": _safe_get(smart_money, "regime", "advice"),
            "new_high_breadth_trend": breadth_trend,
            "new_high_breadth_scan": new_high.get("breadth_scan"),
        },
        "counts": {
            "total": len(unified),
            "by_verification": {
                3: sum(1 for u in unified if u["verification"] == 3),
                2: sum(1 for u in unified if u["verification"] == 2),
                1: sum(1 for u in unified if u["verification"] == 1),
            },
            "by_category": {
                "A": sum(1 for u in unified if u["category"] == "A"),
                "B": sum(1 for u in unified if u["category"] == "B"),
                "AB": sum(1 for u in unified if u["category"] == "AB"),
            },
        },
        "stocks": unified,
    }
