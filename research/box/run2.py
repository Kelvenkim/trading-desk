"""
박스권 공식 v2 — 두 가지 방향 백테스트
  1) 5분봉 당일 박스 그리드 (A: 하단 롱/상단 숏, B: 하단 롱+지수 숏), 매일 장 마감 청산
  2) 일봉 박스 하단 분할매수 (B: +지수 헤지, C: 롱 전용, A: 상단 숏 추가)
앞 기간에서 설정을 고르고(포트폴리오 샤프 기준) 뒤 기간에서 검증.
"""
import itertools
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

import boxlab as BL

OUT = Path(__file__).parent / "results"


def portfolio(per, key, m):
    frames = [pd.Series(r[key], index=idx)[m(idx)] for idx, r in per]
    return pd.concat(frames, axis=1).fillna(0).mean(axis=1)


def evaluate(data, p, split, bpy, cost_s, cost_i, target_fn=None, beta_n=120, keep=False):
    per = [(idx, BL.run_symbol(x, xi, p, cost_s, cost_i, target_fn, beta_n)) for idx, x, xi in data.values()]
    res = {}
    for name, m in [("train", lambda i: i < split), ("test", lambda i: i >= split)]:
        for k in ["A", "B", "C", "BH"]:
            port = portfolio(per, k, m)
            s = BL.stats(port.to_numpy(), bpy)
            if keep:
                s["series"] = port
            res[f"{name}_{k}"] = s
            if k != "BH":
                res[f"{name}_{k}_pos"] = float(np.mean([(np.prod(1 + r[k][m(idx)]) - 1) > 0 for idx, r in per]))
        res[f"{name}_expA"] = float(np.mean([r["expA"][m(idx)].mean() for idx, r in per]))
        res[f"{name}_expB"] = float(np.mean([r["expB"][m(idx)].mean() for idx, r in per]))
        res[f"{name}_turnA_day"] = float(np.mean([r["turnA"][m(idx)].sum() for idx, r in per]))
    return res


def search(data, grid, split, bpy, cost_s, cost_i, target_fn=None, beta_n=120, tag=""):
    rows = []
    t0 = time.time()
    for i, p in enumerate(grid):
        res = evaluate(data, p, split, bpy, cost_s, cost_i, target_fn, beta_n)
        row = dict(p)
        for sp in ["train", "test"]:
            for k in ["A", "B", "C"]:
                for m in ["sharpe", "ret", "mdd"]:
                    row[f"{sp}_{k}_{m}"] = res[f"{sp}_{k}"][m]
                row[f"{sp}_{k}_pos"] = res[f"{sp}_{k}_pos"]
            row[f"{sp}_expA"], row[f"{sp}_expB"] = res[f"{sp}_expA"], res[f"{sp}_expB"]
        rows.append(row)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / f"grid_{tag}.csv", index=False)
    print(f"[{tag}] {len(df)}개 설정, {time.time() - t0:.0f}s")
    return df


def report(df, data, split, bpy, cost_s, cost_i, target_fn, beta_n, tag, keys):
    base = evaluate(data, df.iloc[0][keys].to_dict() | fixed(df.iloc[0]), split, bpy, cost_s, cost_i, target_fn, beta_n)
    for sp in ["train", "test"]:
        s = base[f"{sp}_BH"]
        print(f"  [{sp}] 대형주 동일비중 보유: 수익 {s['ret']:.1f}% 샤프 {s['sharpe']:.2f} MDD {s['mdd']:.1f}%")
    best = {}
    for k in ["A", "B", "C"]:
        b = df.sort_values(f"train_{k}_sharpe", ascending=False).iloc[0]
        rho = df[f"train_{k}_sharpe"].corr(df[f"test_{k}_sharpe"], method="spearman")
        p = {kk: b[kk] for kk in keys} | fixed(b)
        best[k] = p
        print(f"\n  == {tag} {k} 학습 최고 설정: {{{', '.join(f'{kk}={b[kk]}' for kk in keys)}}}")
        print(f"     학습  샤프 {b[f'train_{k}_sharpe']:.2f}  수익 {b[f'train_{k}_ret']:.1f}%  MDD {b[f'train_{k}_mdd']:.1f}%  플러스 종목 {b[f'train_{k}_pos']:.0%}")
        print(f"     검증  샤프 {b[f'test_{k}_sharpe']:.2f}  수익 {b[f'test_{k}_ret']:.1f}%  MDD {b[f'test_{k}_mdd']:.1f}%  플러스 종목 {b[f'test_{k}_pos']:.0%}")
        print(f"     전체 설정 중 검증 샤프>0 {(df[f'test_{k}_sharpe'] > 0).mean():.0%} · 중앙값 {df[f'test_{k}_sharpe'].median():.2f} · 학습-검증 순위상관 {rho:.2f}")
    return best


def fixed(row):
    out = {}
    for k in ["wmax", "cool", "z2", "z3", "eod", "H", "s"]:
        if k in row:
            v = row[k]
            out[k] = bool(v) if k == "eod" else (int(v) if k in ("cool", "H") else float(v))
    out["N"] = int(row["N"])
    return out


# ------------------------------------------------------------------ 1) 5분봉 당일
def grid_5m():
    for N, er, wmin, z, b in itertools.product([36, 78, 156], [0.2, 0.3, 0.4], [0.01, 0.02], [(0.25, 0.5, 0.75), (0.4, 0.6, 0.8)], [0.0, 0.5]):
        yield dict(N=N, er=er, wmin=wmin, z1=z[0], z2=z[1], z3=z[2], b=b, wmax=0.1, cool=N // 2, eod=True)


# ------------------------------------------------------------------ 2) 일봉
def grid_1d():
    for N, er, wmin, z, s, H in itertools.product([20, 60, 120], [0.25, 0.35, 0.5], [0.05, 0.1], [(0.5, 0.75, 1.0), (0.25, 0.6, 1.0)], [0.5, 1.0], [20, 40]):
        yield dict(N=N, er=er, wmin=wmin, z1=z[0], z2=z[1], z3=z[2], s=s, H=H, wmax=0.5, cool=10, eod=False)


if __name__ == "__main__":
    which = sys.argv[1] if len(sys.argv) > 1 else "both"
    if which in ("5m", "both"):
        d5 = BL.load("5m")
        split5 = pd.Timestamp("2026-09-29", tz="Asia/Seoul")  # 앞 약 40거래일 / 뒤 약 20거래일
        bpy5 = 72 * 248
        df5 = search(d5, grid_5m(), split5, bpy5, 0.0005, 0.0002, tag="5m_intraday")
        print("\n### 5분봉 당일 박스 (편도 0.05%, 매일 장 마감 청산)")
        report(df5, d5, split5, bpy5, 0.0005, 0.0002, None, 120 * 12, "5m", ["N", "er", "wmin", "z1", "b"])
    if which in ("1d", "both"):
        d1 = BL.load("1d")
        split1 = pd.Timestamp("2022-01-01")
        df1 = search(d1, grid_1d(), split1, 248, 0.0005, 0.0002, BL.daily_targets, 60, tag="1d_swing")
        print("\n### 일봉 박스 하단 분할매수 (편도 0.05%)")
        report(df1, d1, split1, 248, 0.0005, 0.0002, BL.daily_targets, 60, "1d", ["N", "er", "wmin", "z1", "s", "H"])
