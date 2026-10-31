"""설정 탐색(앞 2/3 기간) → 검증(뒤 1/3 기간). 결과는 results/에 저장."""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

import boxlab as BL

OUT = Path(__file__).parent / "results"
OUT.mkdir(exist_ok=True)
SPLIT = pd.Timestamp("2025-11-01", tz="Asia/Seoul")


def portfolio(per_sym, key, mask_fn):
    """종목별 수익을 같은 비중으로 합친 포트폴리오 봉 수익 (시간축 정렬)."""
    frames = [pd.Series(r[key], index=idx)[mask_fn(idx)] for idx, r in per_sym]
    return pd.concat(frames, axis=1).fillna(0).mean(axis=1)


def evaluate(data, p, cost_s=0.0005, cost_i=0.0002):
    per = [(idx, BL.run_symbol(x, xi, p, cost_s, cost_i)) for idx, x, xi in data.values()]
    res = {}
    for name, m in [("train", lambda i: i < SPLIT), ("test", lambda i: i >= SPLIT)]:
        for k in ["A", "B", "C", "BH"]:
            port = portfolio(per, k, m)
            res[f"{name}_{k}"] = BL.stats(port.to_numpy())
            res[f"{name}_{k}"]["series"] = port
        for k, e in [("A", "expA"), ("B", "expB")]:
            res[f"{name}_exp{k}"] = float(np.mean([r[e][m(idx)].mean() for idx, r in per]))
            res[f"{name}_turn{k}"] = float(np.mean([r[f"turn{k}"][m(idx)].sum() for idx, r in per]))
        # 종목별 검증 성과
        res[f"{name}_pos"] = {k: float(np.mean([(np.prod(1 + r[k][m(idx)]) - 1) > 0 for idx, r in per])) for k in ["A", "B", "C"]}
    return res, per


if __name__ == "__main__":
    t0 = time.time()
    data = BL.load("60m")
    rows = []
    for i, p in enumerate(BL.grid()):
        res, _ = evaluate(data, p)
        row = {**p}
        for split in ["train", "test"]:
            for k in ["A", "B", "C"]:
                s = res[f"{split}_{k}"]
                row[f"{split}_{k}_sharpe"] = s["sharpe"]
                row[f"{split}_{k}_ret"] = s["ret"]
                row[f"{split}_{k}_mdd"] = s["mdd"]
            row[f"{split}_expA"] = res[f"{split}_expA"]
            row[f"{split}_expB"] = res[f"{split}_expB"]
        rows.append(row)
        if i % 24 == 0:
            print(i, f"{time.time() - t0:.0f}s", flush=True)
    df = pd.DataFrame(rows)
    df.to_csv(OUT / "grid_60m.csv", index=False)

    # 기준선
    res, _ = evaluate(data, next(BL.grid()))
    for split in ["train", "test"]:
        s = res[f"{split}_BH"]
        print(f"[{split}] 대형주 동일비중 보유: ret {s['ret']:.1f}% sharpe {s['sharpe']:.2f} mdd {s['mdd']:.1f}%")

    for k in ["A", "B", "C"]:
        best = df.sort_values(f"train_{k}_sharpe", ascending=False).iloc[0]
        rho = df[f"train_{k}_sharpe"].corr(df[f"test_{k}_sharpe"], method="spearman")
        print(f"\n== {k}: 학습기간 최고 설정 ==")
        print(best[["N", "er", "wmin", "z1", "b", "eod"]].to_dict())
        print(f"  train sharpe {best[f'train_{k}_sharpe']:.2f} ret {best[f'train_{k}_ret']:.1f}% mdd {best[f'train_{k}_mdd']:.1f}%")
        print(f"  test  sharpe {best[f'test_{k}_sharpe']:.2f} ret {best[f'test_{k}_ret']:.1f}% mdd {best[f'test_{k}_mdd']:.1f}%")
        print(f"  학습-검증 샤프 순위상관 {rho:.2f} | 검증 샤프>0 비율 {(df[f'test_{k}_sharpe'] > 0).mean():.0%} | 검증 샤프 중앙값 {df[f'test_{k}_sharpe'].median():.2f}")
    print(f"done {time.time() - t0:.0f}s")
