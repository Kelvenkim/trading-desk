"""
코인 5분봉 단기 실험 — 중계 서버(Cloudflare Worker)의 /scalp 상태를 data/us/crypto_scalp.json 으로 저장
매매는 Worker가 5분마다 직접 해요 (worker/worker.js runScalp). 이 스크립트는 사이트·보고서용 기록만.
근거·한계: research/crypto5m/bt.py — 수수료 한쪽 0.05% 기준 과거 60일 모든 방식이 손실. 실험 기록용.
"""
import json, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main():
    proxy = json.loads((ROOT / "data/config.json").read_text())["proxy"].rstrip("/")
    req = urllib.request.Request(proxy + "/scalp", headers={"Origin": "https://kelvenkim.github.io", "User-Agent": "trading-desk"})
    try:
        S = json.loads(urllib.request.urlopen(req, timeout=20).read() or b"{}")
    except Exception as e:
        print("5분 실험 상태 못 받음:", e); return
    if not S.get("eq"):
        print("5분 실험: 아직 기록 없음 (Worker 새 코드·매일 Cron 필요)"); return
    S["n_trades"] = len(S.get("trades", []))
    (ROOT / "data/us/crypto_scalp.json").write_text(json.dumps(S, ensure_ascii=False, separators=(",", ":")))
    print("5분 실험 저장:", S.get("eq_now"), "거래", S["n_trades"])


if __name__ == "__main__":
    main()
