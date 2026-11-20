"""
장기 투자 리서치 공통 틀 — 모든 산업(장기 테마 16개)이 같은 7단계로 만들어져요.
1 매크로 → 2 산업 내러티브 → 3 공급망 병목 → 4 상장 공급사 → 5 회사 검증 8항목 → 6 시나리오 → 7 분류
각 문장: (내용, 구분, 출처) — 구분: 사실 / 추정 / 모름. 규칙 원문: 프로젝트 문서 '장기-리서치-규칙.md'
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
D = ROOT / "data/us/longterm"
F, E, U = "사실", "추정", "모름"

# 사이트 장기 테마 16개 ↔ 리서치 키 (같은 key 사용)
THEMES = ["industrial", "consumer", "software", "cyber", "defense", "bio", "banks", "crypto", "robot", "energy",
          "ai_infra", "nuclear", "ai_chip", "clean_ev", "materials", "quantum"]

# ---- 1단계 공통 매크로 (모든 산업이 같이 쓰는 사실, 산업별로 good/bad를 더 붙여요) ----
MS = {
    "minutes": "https://www.investmentnews.com/equities/the-fed-came-close-to-an-october-rate-hike-fomc-minutes-show/269079",
    "waller": "https://www.mpamag.com/us/mortgage-industry/industry-trends/fed-rate-hike-odds-hit-100-as-waller-floats-bigger-december-move/596880",
    "wsr1119": "https://thewallstreetrepublic.substack.com/p/anthropic-closes-at-9717-s-and-p",
    "vista1119": "https://vistapglobal.com/stock-market-today-november-19-2026-anthropic-ipo-pops-wall-street-loses-its-appetite-amd-ant-eprx-insm-jpm-ma-modd-panw-ser-sls-v-wmt/",
}
MACRO_BASE = {
    "rates": [
        ("기준금리 3.75~4.00%. 10월 근원물가 +0.3%(3개월 연속) — 12/8~9 회의 인상이 거의 확정, 월러 이사는 0.5%p도 검토 필요", F, MS["waller"]),
        ("10월 회의록: 거의 모든 위원이 추가 인상이 적절할 가능성이 높다고 봄", F, MS["minutes"]),
        ("10년 국채 5.05%, S&P500 6일 연속 하락·200일선 −2.3%, VIX 28 (11/19)", F, MS["wsr1119"]),
        ("필라델피아 연은 제조업 20.9→6.3, 원가 지수 43→58: 경기는 식고 물가는 안 잡히는 조합 (11/19)", F, MS["vista1119"]),
    ],
    "liquidity": [
        ("대형 공모가 자금을 흡수: 앤트로픽 약 $813억(11/19), 스페이스X 상장 등", F, MS["wsr1119"]),
        ("금리 인상기 — 이익이 먼 성장주일수록 더 크게 할인되는 국면", E, ""),
    ],
}


def co(t, name, exch, layer, products, customers, growth, pos, sub, grade, grade_why, capa, fin, dil, mgmt, geo, val,
       best, base, worst, cls, good_if, break_if, ev, src):
    """4~7단계 회사 한 곳. ev = {g: 최고 배수, l: 최악 배수, pg: 잘 풀릴 확률 %} (추정)"""
    return {"t": t, "name": name, "exch": exch, "layer": layer, "products": products, "customers": customers, "growth": growth,
            "v": {"pos": pos, "sub": sub, "grade": grade, "grade_why": grade_why, "capa": capa, "fin": fin, "dil": dil, "mgmt": mgmt, "geo": geo, "val": val},
            "sc": {"best": best, "base": base, "worst": worst}, "cls": cls, "good_if": good_if, "break_if": break_if, "ev": ev, "src": src}


def macro(verdict, why, good, bad, extra_liq=(), geo=()):
    return {"verdict": verdict, "verdict_why": why, "good": list(good), "bad": list(bad) + MACRO_BASE["rates"],
            "liquidity": MACRO_BASE["liquidity"] + list(extra_liq), "geo": list(geo)}


def save(R, S):
    """R 저장 + index.json 갱신. S = 출처 dict"""
    srcs = set(v for v in S.values() if v) | set(v for v in MS.values())
    R["sources"] = sorted(srcs)
    D.mkdir(parents=True, exist_ok=True)
    p = D / f"{R['key']}.json"
    old = json.loads(p.read_text()) if p.exists() else {}
    for c in R["companies"]:  # 숫자(m)는 longterm_metrics가 채움 — 다시 만들 때 기존 숫자 유지
        oc = next((x for x in old.get("companies", []) if x["t"] == c["t"]), None)
        if oc and oc.get("m"):
            c["m"] = oc["m"]
    if old.get("metrics_at"):
        R["metrics_at"] = old["metrics_at"]
    p.write_text(json.dumps(R, ensure_ascii=False, indent=1))
    idx = D / "index.json"
    I = json.loads(idx.read_text()) if idx.exists() else {"industries": []}
    I["industries"] = [x for x in I["industries"] if x["key"] != R["key"]] + [
        {"key": R["key"], "name": R["name"], "asof": R["asof"], "verdict": R["macro"]["verdict"], "n": len(R["companies"])}]
    I["industries"].sort(key=lambda x: THEMES.index(x["key"]) if x["key"] in THEMES else 99)
    idx.write_text(json.dumps(I, ensure_ascii=False, indent=1))
    print("장기 리서치 저장:", R["key"], len(R["companies"]), "개 회사")
