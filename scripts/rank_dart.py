"""
DART(금융감독원 전자공시) 실적 — API 키는 환경변수 DART_API_KEY 에서만 읽음 (코드·저장소에 넣지 않음)
주요계정 다중회사 조회(fnlttMultiAcnt)로 한 번에 최대 100개 회사의 매출·영업이익(당기 vs 전년 같은 기간)을 받음.
"""
import io, json, os, time, zipfile, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

API = "https://opendart.fss.or.kr/api/"
REPRT = {"11013": "1분기", "11012": "반기", "11014": "3분기", "11011": "사업"}
REV_NAMES = ("매출액", "수익(매출액)", "영업수익", "매출")
OP_NAMES = ("영업이익", "영업이익(손실)")


def key():
    return os.environ.get("DART_API_KEY", "").strip()


def _get(path, params, raw=False):
    params = {"crtfc_key": key(), **params}
    url = API + path + "?" + urllib.parse.urlencode(params)
    for k in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                b = r.read()
            return b if raw else json.loads(b)
        except Exception:
            time.sleep(2 + k * 3)
    return None


def corp_codes(codes, cache_path):
    """종목코드 → DART 고유번호. 한 번 받아서 캐시 (고유번호는 공개 정보라 저장소에 둬도 됨)"""
    cache_path = Path(cache_path)
    m = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    if all(c in m for c in codes):
        return m
    b = _get("corpCode.xml", {}, raw=True)
    if not b:
        return m
    z = zipfile.ZipFile(io.BytesIO(b))
    root = ET.fromstring(z.read(z.namelist()[0]))
    for el in root.iter("list"):
        sc = (el.findtext("stock_code") or "").strip()
        if sc:
            m[sc] = el.findtext("corp_code").strip()
    cache_path.write_text(json.dumps(m))
    return m


def _amt(s):
    try:
        return float(str(s).replace(",", "").strip())
    except Exception:
        return None


def fetch_reports(corp_map, codes, year, reprt):
    """한 보고서(연도·분기)에 대해 회사별 {rcept_date, rev, rev_prev, op, op_prev}"""
    inv = {v: k for k, v in corp_map.items()}
    corps = [corp_map[c] for c in codes if c in corp_map]
    out = {}
    for i in range(0, len(corps), 100):
        j = _get("fnlttMultiAcnt.json", {"corp_code": ",".join(corps[i:i + 100]), "bsns_year": str(year), "reprt_code": reprt})
        if not j or j.get("status") != "000":
            continue
        rows = {}
        for it in j.get("list", []):
            sc = it.get("stock_code") or inv.get(it.get("corp_code"))
            if not sc or it.get("sj_div") != "IS":
                continue
            rows.setdefault(sc, []).append(it)
        for sc, items in rows.items():
            fs = "CFS" if any(x.get("fs_div") == "CFS" for x in items) else "OFS"
            rec = {"rcept_date": None, "fs": fs, "year": year, "reprt": reprt}
            for x in items:
                if x.get("fs_div") != fs:
                    continue
                nm = x.get("account_nm", "").replace(" ", "")
                rn = x.get("rcept_no", "")
                if rn and len(rn) >= 8:
                    rec["rcept_date"] = f"{rn[:4]}-{rn[4:6]}-{rn[6:8]}"
                if nm in OP_NAMES and "op" not in rec:
                    rec["op"], rec["op_prev"] = _amt(x.get("thstrm_amount")), _amt(x.get("frmtrm_amount"))
                elif nm in REV_NAMES and "rev" not in rec:
                    rec["rev"], rec["rev_prev"] = _amt(x.get("thstrm_amount")), _amt(x.get("frmtrm_amount"))
            if rec["rcept_date"] and ("op" in rec or "rev" in rec):
                out[sc] = rec
        time.sleep(0.3)
    return out


def growth(cur, prev):
    """전년 대비 증가율, -2~+2로 자름. 적자→흑자 +2, 흑자→적자 -2"""
    if cur is None or prev is None:
        return None
    if prev <= 0 and cur > 0:
        return 2.0
    if prev > 0 and cur <= 0:
        return -2.0
    if prev == 0:
        return None
    g = (cur - prev) / abs(prev)
    return max(-2.0, min(2.0, g))


def earn_raw(rec):
    """실적 원점수 = 영업이익 증가율 70% + 매출 증가율 30%"""
    if not rec:
        return None
    go, gr = growth(rec.get("op"), rec.get("op_prev")), growth(rec.get("rev"), rec.get("rev_prev"))
    if go is None and gr is None:
        return None
    return 0.7 * (go if go is not None else 0) + 0.3 * (gr if gr is not None else 0)


def report_list(today):
    """오늘 기준으로 이미 나왔을 수 있는 최근 보고서들 (최신 먼저)"""
    y = today.year
    seq = [(y, "11014"), (y, "11012"), (y, "11013"), (y - 1, "11011"), (y - 1, "11014"), (y - 1, "11012")]
    return seq
