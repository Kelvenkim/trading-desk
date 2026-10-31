"""
index.html 안의 assets/ 파일 주소 뒤에 내용 기반 버전(?v=해시)을 붙입니다.
파일 내용이 바뀌면 주소가 바뀌어서, 브라우저가 예전 파일을 캐시에서 쓰지 않고 새로 받아요.

사용: python scripts/stamp_assets.py   (assets/ 파일을 고친 뒤 커밋 전에 실행)
"""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
index = ROOT / "index.html"
html = index.read_text(encoding="utf-8")


def stamp(m):
    path = m.group(2)
    f = ROOT / path
    if not f.exists():
        return m.group(0)
    h = hashlib.sha1(f.read_bytes()).hexdigest()[:8]
    return f'{m.group(1)}{path}?v={h}{m.group(3)}'


new = re.sub(r'((?:src|href)=")(assets/[^"?]+)(?:\?v=[0-9a-f]+)?(")', stamp, html)
if new != html:
    index.write_text(new, encoding="utf-8")
    print("index.html 버전 갱신")
else:
    print("변경 없음")
