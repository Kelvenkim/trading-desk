"""
터틀 트레이딩 (Richard Dennis·William Eckhardt, 1983) — 원래 규칙을 미국 주식 롱 전용으로 옮김
  N       = 20일 ATR (와일더 방식: N = (19×전날 N + 오늘 TR) / 20)
  1 유닛  = 계좌의 1%  ÷  N   주  → 하루 평균 변동(N)만큼 움직이면 계좌가 1% 움직임
  시스템1 = 20일 최고가 돌파 시 매수, 10일 최저가 깨면 청산. 직전 시스템1 신호가 이익이었으면 이번 신호는 건너뜀
            (건너뛴 경우 55일 돌파 때는 들어감 — 원래 규칙의 '안전장치')
  시스템2 = 55일 최고가 돌파 시 매수, 20일 최저가 깨면 청산. 걸러내기 없음
  추가    = 첫 매수가에서 +½N 마다 1유닛씩, 최대 4유닛
  손절    = 마지막 매수가 − 2N (추가할 때마다 모든 유닛 손절을 같이 올림)
"""
import numpy as np


def wilder_n(H, L, C, n=20):
    """H, L, C: (일, 종목) 배열 → N (같은 모양). 앞쪽 n일은 NaN"""
    pc = np.vstack([np.full((1, C.shape[1]), np.nan), C[:-1]])
    tr = np.nanmax(np.stack([H - L, np.abs(H - pc), np.abs(L - pc)]), axis=0)
    N = np.full_like(C, np.nan)
    T = C.shape[0]
    for j in range(C.shape[1]):
        s, cnt, prev = 0.0, 0, np.nan
        for i in range(T):
            x = tr[i, j]
            if not np.isfinite(x):
                if np.isfinite(prev):
                    N[i, j] = prev
                continue
            if not np.isfinite(prev):
                s += x; cnt += 1
                if cnt == n:
                    prev = s / n; N[i, j] = prev
            else:
                prev = (prev * (n - 1) + x) / n; N[i, j] = prev
    return N


def roll_max_prev(X, n):
    """오늘을 뺀 직전 n일 최고 (i일 값 = i-n..i-1)"""
    out = np.full_like(X, np.nan)
    for i in range(n, X.shape[0]):
        out[i] = np.nanmax(X[i - n:i], axis=0) if np.isfinite(X[i - n:i]).any() else np.nan
    return out


def roll_min_prev(X, n):
    out = np.full_like(X, np.nan)
    for i in range(n, X.shape[0]):
        out[i] = np.nanmin(X[i - n:i], axis=0) if np.isfinite(X[i - n:i]).any() else np.nan
    return out


def stock_trades(o, h, l, c, N, hi20, lo10, hi55, lo20, mode="both", filt=True, start=0):
    """한 종목에 터틀 규칙을 처음부터 적용 (포트폴리오 제약 없이). 현재 상태와 거래 목록을 돌려줌.
    mode: 's1' | 's2' | 'both'  — both는 원래 규칙(시스템1 + 걸러진 신호는 55일 돌파로 대신)"""
    trades, pos = [], None
    last_s1_win = False       # 직전 시스템1 '가상' 거래 결과
    hyp = None                # 시스템1 가상 거래 (실제 진입 여부와 상관없이 걸러내기 판단용)
    T = len(c)
    for i in range(max(start, 56), T):
        if not (np.isfinite(N[i - 1]) and np.isfinite(hi20[i]) and np.isfinite(c[i])):
            continue
        n_ = N[i - 1]
        # --- 시스템1 가상 거래 (걸러내기용)
        if hyp:
            stop = hyp["px"] - 2 * hyp["n"]
            ex = None
            if l[i] <= stop: ex = min(o[i], stop)
            elif l[i] <= lo10[i]: ex = min(o[i], lo10[i])
            if ex is not None:
                last_s1_win = ex > hyp["px"]; hyp = None
        prev_win = last_s1_win
        new_s1 = False
        if not hyp and h[i] > hi20[i]:
            hyp = {"px": max(o[i], hi20[i]), "n": n_}; new_s1 = True
        # --- 실제 포지션 청산
        if pos:
            ex_lo = lo10[i] if pos["sys"] == 1 else lo20[i]
            ex, why = None, ""
            if l[i] <= pos["stop"]:
                ex, why = min(o[i], pos["stop"]), "2N 손절"
            elif np.isfinite(ex_lo) and l[i] <= ex_lo:
                ex, why = min(o[i], ex_lo), ("10일" if pos["sys"] == 1 else "20일") + " 최저 이탈"
            if ex is not None:
                pos.update(exit=ex, exit_i=i, why=why); trades.append(pos); pos = None
                continue
            # 추가 매수 (+½N 마다)
            while pos["units"] < 4 and h[i] >= pos["next_add"]:
                px = max(o[i], pos["next_add"])
                pos["fills"].append(px); pos["units"] += 1
                pos["stop"] = px - 2 * pos["n"]
                pos["next_add"] = px + 0.5 * pos["n"]
            continue
        # --- 진입
        sys_ = 0
        s1 = h[i] > hi20[i]
        s2 = np.isfinite(hi55[i]) and h[i] > hi55[i]
        if mode in ("s1", "both") and s1 and new_s1 and (not filt or not prev_win):
            sys_, lvl = 1, hi20[i]
        elif mode == "s2" and s2:
            sys_, lvl = 2, hi55[i]
        elif mode == "both" and s2:
            sys_, lvl = 2, hi55[i]
        if sys_:
            px = max(o[i], lvl)
            pos = {"sys": sys_, "entry_i": i, "n": n_, "fills": [px], "units": 1, "stop": px - 2 * n_, "next_add": px + 0.5 * n_}
            while pos["units"] < 4 and h[i] >= pos["next_add"]:          # 같은 날 크게 오르면 추가도 같은 날
                px2 = max(o[i], pos["next_add"])
                pos["fills"].append(px2); pos["units"] += 1; pos["stop"] = px2 - 2 * n_; pos["next_add"] = px2 + 0.5 * n_
    return trades, pos, {"last_s1_win": last_s1_win, "hyp_open": hyp is not None}
