"""
매일 순위 — 공통 계산 (매일 실행 scripts/rank_daily.py, 과거 검증 research/rank/backfill.py 가 같이 씀)

각 항목(팩터)은 그날 300종목 안에서 순위를 매겨 -1(최하) ~ +1(최상)로 바꾼 뒤,
가중치를 곱해 더한 값이 종합 점수. 가중치는 '그 항목이 실제로 20일 뒤 수익률 순위를 맞힌 정도(IC)'로 정함.
"""
import numpy as np
import pandas as pd

FACTORS = {
    #  key      이름                설명                                                    사전 기대 IC(데이터 없을 때 출발점)
    "mom":    ("6개월 상승세",     "최근 1개월을 뺀 6개월 수익률 (주도주일수록 높음)",               0.00),
    "hi52":   ("52주 고점 근접",   "종가 ÷ 최근 1년 최고가",                                       0.00),
    "trend":  ("추세 정렬",        "종가>20일선>60일선>120일선, 60일선 상승 여부 (0~4점)",          0.00),
    "volx":   ("거래량 급증",      "최근 5일 평균 거래량 ÷ 60일 평균",                              0.00),
    "rev":    ("단기 눌림",        "최근 5일 수익률의 반대 (많이 빠졌을수록 높음)",                  0.00),
    "lowvol": ("낮은 변동성",      "최근 60일 하루 변동폭이 작을수록 높음",                          0.00),
    "rate":   ("금리 흐름 수혜",   "이 종목의 미국 10년 금리 민감도 × 최근 20일 금리 변화",           0.00),
    "fx":     ("환율 흐름 수혜",   "이 종목의 원/달러 환율 민감도 × 최근 20일 환율 변화",             0.00),
    "news":   ("뉴스 분위기",      "최근 3일 뉴스 제목의 호재·악재 단어 점수",                       0.005),
    "earn":   ("실적 성장",        "최근 공시 실적의 영업이익·매출 전년 대비 증가율 (DART)",          0.01),
}
PRICE_FACTORS = ["mom", "hi52", "trend", "volx", "rev", "lowvol", "rate", "fx"]
HORIZONS = (5, 20)
T_MIN = 2.0      # 확실성(t) 이 2 이상이어야 순위에 씀 (우연일 가능성 약 5% 이하)
N_MIN = 12.0     # 겹치지 않는 20일 관측이 12개(약 1년치) 이상


# ---------- 우리 점수 (100점) : 사람이 읽을 수 있는 고정 규칙 ----------
OURS = {  # key: (이름, 만점, 설명)
    "trend": ("차트 추세", 25, "종가>20일선, 20일>60일선, 60일>120일선, 60일선 상승, 52주 고점의 85% 이상 — 각 5점"),
    "earn":  ("실적",      25, "영업이익·매출 전년 대비: 크게 성장 25 · 성장 20 · 유지 14 · 소폭 감소 8 · 크게 감소 3 · 자료 없음 12"),
    "news":  ("뉴스",      20, "최근 3일 기사 분위기: 매우 좋음 20 · 좋음 16 · 보통/없음 10 · 나쁨 5 · 매우 나쁨 1"),
    "flow":  ("수급",      15, "최근 5일: 거래량 1.5배↑+상승 15 · 1.2배↑+상승 12 · 상승 9 · 보합/하락 6 · 거래량 1.5배↑+하락 2"),
    "safe":  ("안정성",    15, "하루 변동폭이 300종목 중 작을수록 높음"),
}
GRADES = [(80, "S"), (70, "A"), (60, "B"), (45, "C"), (0, "D")]


def our_score(c, m20, m60, m120, m60_20ago, hi52, ret5, volr, vol60, earn=None, news=None, news_n=None):
    """모두 종목별 Series (같은 날짜). 반환: 항목별 점수 DataFrame + total"""
    idx = c.index
    t = (5 * (c > m20).astype(float) + 5 * (m20 > m60) + 5 * (m60 > m120) + 5 * (m60 > m60_20ago) + 5 * (hi52 >= 0.85))
    t = t.where(m120.notna(), 12.5)
    e = pd.Series(12.0, index=idx)
    if earn is not None:
        x = earn.reindex(idx)
        e = pd.Series(np.select([x >= 0.3, x >= 0.1, x >= 0, x >= -0.2, x.notna()], [25, 20, 14, 8, 3], 12.0), index=idx)
    nw = pd.Series(10.0, index=idx)
    if news is not None:
        x = news.reindex(idx)
        nw = pd.Series(np.select([x >= 1, x >= 0.3, x > -0.3, x > -1, x.notna()], [20, 16, 10, 5, 1], 10.0), index=idx)
    fl = pd.Series(np.select([(volr >= 1.5) & (ret5 > 0), (volr >= 1.2) & (ret5 > 0), ret5 > 0.005, (volr >= 1.5) & (ret5 < 0)],
                             [15, 12, 9, 2], 6.0), index=idx)
    vp = vol60.rank(pct=True)
    sf = (15 * (1 - vp)).fillna(7.5)
    D = pd.DataFrame({"trend": t, "earn": e, "news": nw, "flow": fl, "safe": sf})
    D["total"] = D.sum(axis=1)
    return D


def grade_of(x):
    for th, g in GRADES:
        if x >= th:
            return g
    return "D"


def ours_inputs(C, H, V):
    """our_score 에 들어갈 날짜×종목 표들"""
    m20, m60, m120 = (C.rolling(n, min_periods=n).mean() for n in (20, 60, 120))
    return {"c": C, "m20": m20, "m60": m60, "m120": m120, "m60_20ago": m60.shift(20),
            "hi52": C / H.rolling(250, min_periods=200).max(), "ret5": C / C.shift(5) - 1,
            "volr": V.rolling(5).mean() / V.rolling(60).mean(),
            "vol60": C.pct_change(fill_method=None).rolling(60, min_periods=50).std()}


def wide(stocks, calendar):
    """stocks: {code: [[date,o,h,l,c,v],...]} → 날짜×종목 표 (C, H, V)"""
    C, H, V = {}, {}, {}
    for code, rows in stocks.items():
        if not rows:
            continue
        idx = pd.to_datetime([r[0] for r in rows])
        a = np.array([r[1:] for r in rows], dtype=float)
        C[code] = pd.Series(a[:, 3], idx)
        H[code] = pd.Series(a[:, 1], idx)
        V[code] = pd.Series(a[:, 4], idx)
    cal = pd.DatetimeIndex(calendar)
    C = pd.DataFrame(C).reindex(cal).ffill(limit=5)
    H = pd.DataFrame(H).reindex(cal).ffill(limit=5)
    V = pd.DataFrame(V).reindex(cal).fillna(0)
    return C, H, V


def opens(stocks, calendar):
    """날짜×종목 시가 표"""
    Op = {}
    for code, rows in stocks.items():
        if rows:
            Op[code] = pd.Series([r[1] for r in rows], pd.to_datetime([r[0] for r in rows]))
    return pd.DataFrame(Op).reindex(pd.DatetimeIndex(calendar))


def theme_pullback(C, d, cols, theme_pct, primary, rev_days=5, w=0.5):
    """테마 눌림 점수 = 강한 테마 소속(순위) + 0.5 × 최근 5일 하락(순위). 과거 검증: research/rank/variants.py"""
    th = pd.Series({c: theme_pct.get(primary.get(c), 0.5) for c in cols}, dtype=float)
    i = C.index.get_loc(d)
    rev = -(C.loc[d, cols] / C.iloc[i - rev_days][cols] - 1)
    return xrank(th) + w * xrank(rev), th


def macro_aligned(series, calendar):
    """미국 시장 값(금리·환율)을 한국 거래일에 맞춤. 한국 D일 장 마감 시점엔 미국 D일 종가가 아직 없으므로 D-1까지만 사용."""
    s = pd.Series(series).sort_index()
    s.index = pd.to_datetime(s.index)
    cal = pd.DatetimeIndex(calendar)
    out = s.reindex(s.index.union(cal)).ffill().shift(1)   # 하루 늦게
    return out.reindex(cal)


def price_factors(C, H, V, tnx=None, krw=None):
    """가격으로 계산하는 항목들 (날짜×종목 표 dict)"""
    F = {}
    F["mom"] = C.shift(21) / C.shift(126) - 1
    F["hi52"] = C / H.rolling(250, min_periods=200).max()
    m20, m60, m120 = (C.rolling(n, min_periods=n).mean() for n in (20, 60, 120))
    F["trend"] = ((C > m20).astype(float) + (m20 > m60) + (m60 > m120) + (m60 > m60.shift(20))).where(m120.notna())
    v5, v60 = V.rolling(5).mean(), V.rolling(60).mean()
    F["volx"] = np.log((v5 + 1) / (v60 + 1)).where(v60 > 0)
    F["rev"] = -(C / C.shift(5) - 1)
    R = C.pct_change(fill_method=None)
    F["lowvol"] = -R.rolling(60, min_periods=50).std()
    for key, x in (("rate", tnx), ("fx", krw)):
        if x is None:
            F[key] = pd.DataFrame(np.nan, index=C.index, columns=C.columns)
            continue
        dx = x.diff() if key == "rate" else np.log(x).diff()
        # 250일 민감도(베타) = cov(종목수익률, 변화) / var(변화)
        mx = dx.rolling(250, min_periods=200).mean()
        vx = dx.rolling(250, min_periods=200).var()
        mr = R.rolling(250, min_periods=200).mean()
        mrx = R.mul(dx, axis=0).rolling(250, min_periods=200).mean()
        beta = (mrx.sub(mr.mul(mx, axis=0))).div(vx, axis=0)
        chg20 = x - x.shift(20) if key == "rate" else np.log(x / x.shift(20))
        F[key] = beta.mul(chg20, axis=0)     # 민감도 × 최근 흐름 = 그 흐름이 이어질 때의 기대 방향
    return F


def xrank(row):
    """한 날짜의 값들을 -1~+1 순위 점수로. 값이 없으면 0(중간)"""
    s = pd.Series(row, dtype=float)
    ok = s.notna() & np.isfinite(s)
    out = pd.Series(0.0, index=s.index)
    n = ok.sum()
    if n >= 5:
        out[ok] = (s[ok].rank(method="average") - 0.5) / n * 2 - 1
    return out


def spearman(a, b):
    a, b = pd.Series(a, dtype=float), pd.Series(b, dtype=float)
    ok = a.notna() & b.notna() & np.isfinite(a) & np.isfinite(b)
    if ok.sum() < 20:
        return np.nan
    x, y = a[ok].rank(), b[ok].rank()
    if x.std() == 0 or y.std() == 0:
        return np.nan
    return float(np.corrcoef(x, y)[0, 1])


def learn_weights(ic_records, asof=None, half_life_years=3.0, K=24.0):
    """
    ic_records: [{"date": "YYYY-MM-DD", "src": "backfill"|"live", "step": 거래일 간격, "ic": {factor: IC(20일)}}]
    각 항목의 평균 IC를 '사전 기대값' 쪽으로 당겨서(데이터가 적을수록 많이) 가중치로 씀.
    20일 수익률은 날마다 겹치므로 독립 관측 수 = 날짜 수 × 간격 / 20.
    """
    asof = pd.Timestamp(asof) if asof else pd.Timestamp.today()
    out = {}
    for f, (name, desc, prior) in FACTORS.items():
        num = den = n_eff = 0.0
        vals, wts = [], []
        for r in ic_records:
            v = r["ic"].get(f)
            if v is None or not np.isfinite(v):
                continue
            age = (asof - pd.Timestamp(r["date"])).days / 365.25
            decay = 0.5 ** (max(age, 0) / half_life_years)
            obs = r.get("step", 1) / 20.0
            num += v * obs * decay
            den += obs * decay
            n_eff += obs * decay
            vals.append(v); wts.append(obs * decay)
        mean = num / den if den else 0.0
        if len(vals) > 2:
            w = np.array(wts); x = np.array(vals)
            sd = float(np.sqrt(np.average((x - mean) ** 2, weights=w)))
            t = mean / sd * np.sqrt(n_eff) if sd > 0 else 0.0
        else:
            sd, t = 0.0, 0.0
        shrunk = (n_eff * mean + K * prior) / (n_eff + K)
        out[f] = {"name": name, "desc": desc, "prior": prior, "mean_ic": round(mean, 4), "t": round(t, 2),
                  "n_eff": round(n_eff, 1), "n_days": len(vals), "raw": shrunk}
    for v in out.values():
        v["active"] = bool(abs(v["t"]) >= T_MIN and v["n_eff"] >= N_MIN and np.sign(v["raw"]) == np.sign(v["mean_ic"]))
        if not v["active"]:
            v["raw"] = 0.0
    tot = sum(abs(v["raw"]) for v in out.values())
    for v in out.values():
        v["weight"] = round(v["raw"] / tot, 4) if tot else 0.0
        del v["raw"]
    return out


def combine(Z, weights):
    """Z: {factor: Series(종목→-1~1)}, weights: learn_weights 결과 → 종합 점수 Series"""
    s = None
    for f, z in Z.items():
        w = weights.get(f, {}).get("weight", 0.0)
        s = z * w if s is None else s.add(z * w, fill_value=0)
    return s


# ---------- 뉴스 키워드 ----------
POS = {
    "흑자전환": 2, "사상 최대": 2, "사상최대": 2, "역대 최대": 2, "역대최대": 2, "어닝 서프라이즈": 2, "어닝서프라이즈": 2,
    "최대 실적": 2, "호실적": 2, "수주": 1.5, "공급계약": 1.5, "공급 계약": 1.5, "계약 체결": 1.5, "목표가 상향": 1.5,
    "목표주가 상향": 1.5, "자사주 소각": 1.5, "자사주 매입": 1, "배당 확대": 1, "상향": 1, "신고가": 1, "급등": 1,
    "승인": 1, "허가": 1, "특허": 0.5, "인수": 0.5, "수혜": 1, "독점": 1, "돌파": 0.5, "강세": 0.5, "순매수": 0.5,
    "증가": 0.5, "성장": 0.5, "개선": 0.5, "기대": 0.3, "출시": 0.3, "협력": 0.3, "반등": 0.5, "상승": 0.3,
}
NEG = {
    "적자전환": 2, "어닝 쇼크": 2, "어닝쇼크": 2, "횡령": 2, "배임": 2, "상장폐지": 2, "거래정지": 2, "감자": 1.5,
    "유상증자": 1.5, "압수수색": 1.5, "목표가 하향": 1.5, "목표주가 하향": 1.5, "리콜": 1.5, "과징금": 1.5, "제재": 1,
    "소송": 1, "적자": 1, "하향": 1, "급락": 1, "신저가": 1, "전환사채": 1, "불성실": 1, "손실": 1, "해지": 1,
    "철회": 1, "부진": 1, "우려": 0.5, "감소": 0.5, "하락": 0.3, "약세": 0.5, "순매도": 0.5, "쇼크": 1, "경고": 0.5,
}


def headline_score(title):
    t = title.replace("&quot;", '"')
    s = 0.0
    for k, w in POS.items():
        if k in t:
            s += w
    for k, w in NEG.items():
        if k in t:
            s -= w
    # '적자전환'과 '적자'처럼 겹치는 단어 이중 계산 보정
    if "적자전환" in t:
        s += NEG["적자"]
    if "흑자전환" in t and "적자" in t:
        s += NEG["적자"]
    return max(-3.0, min(3.0, s))
