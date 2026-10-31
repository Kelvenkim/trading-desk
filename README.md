# Trading Desk

나만의 주식 현황 · 포트폴리오 · 백테스트 사이트. GitHub Pages에 무료로 올려서 쓰는 정적 사이트입니다.

- **차트**: TradingView 같은 작업 화면
  - 종목 검색: 한국 전 종목·ETF, 미국 주요 종목. 이름, 코드, 초성(ㅅㅅㅈㅈ)으로 검색. 단축키 `/`
  - 봉 주기: 1분, 5분, 15분, 30분, 1시간, 일, 주, 월
  - 보조지표: 이동평균(5/20/60/120), 볼린저 밴드, 거래량, RSI, MACD (아래 창, 경계선 끌어서 높이 조절)
  - 그리기 도구: 추세선, 연장선, 수평선, 수직선, 박스, 피보나치 되돌림, 가격·기간 측정, 텍스트
    - 클릭해서 선택 → 끌어서 이동, 끝점 끌어서 수정, `Delete`로 삭제, `Esc`로 취소
    - 자석: 시가·고가·저가·종가에 자동으로 붙음
    - 종목별로 브라우저에 저장, 봉 주기를 바꿔도 같은 자리에 표시
  - 관심종목 목록: 별표로 추가
- **포트폴리오**: 보유 종목 평가액, 손익, 수익률, 비중. 보유 내역은 **내 브라우저에만 저장**되고 GitHub에는 올라가지 않음
- **백테스트**: 이동평균 크로스 / RSI 역추세 / 볼린저 박스권 / 거래량 돌파(급등 포착) 전략, 손절·익절·트레일링·당일청산, 수수료·세금·슬리피지 반영, 매매 시점 차트와 자산 곡선, 거래 내역 CSV 저장
- **Pine Script 내보내기**: 백테스트한 전략과 설정을 TradingView용 코드로 바로 변환

## 구조

```
index.html                     화면
assets/data.js                 시세 불러오기 (저장된 시세 / 중계 서버), 종목 검색, 봉 묶기
assets/chart.js                메인 차트, 보조지표, 범례
assets/draw.js                 그리기 도구
assets/app.js                  화면 연결 (차트, 포트폴리오, 백테스트, 설정)
assets/backtest.js             백테스트 엔진, 지표, 전략, Pine Script 생성
assets/style.css               스타일 (한국식: 상승 빨강 / 하락 파랑)
watchlist.json                 기본 관심종목  ← 여기 넣은 종목은 중계 서버 없이도 보임
scripts/fetch_data.py          시세 수집 → data/ 에 JSON 저장, 검색용 종목 목록 생성
worker/worker.js               시세 중계 서버 (Cloudflare Workers)
.github/workflows/update-data.yml   평일 장중 30분마다 자동 갱신
data/                          수집된 시세 (자동 생성)
```

## 시세 중계 서버 만들기 (Cloudflare, 무료, 5분)

브라우저는 보안 정책 때문에 네이버·야후 시세를 직접 받을 수 없어요. `watchlist.json`에 넣은 종목은 GitHub Actions가 미리 받아두니 바로 보이지만, **검색한 다른 종목, 1분봉, 최신 시세 받기**는 중계 서버가 있어야 해요.

1. https://dash.cloudflare.com/sign-up 에서 무료 가입 (이메일 인증까지)
2. 왼쪽 메뉴 **Compute (Workers)** → **Workers & Pages** → **Create** → **Start with Hello World!** (Worker 만들기)
3. 이름을 `trading-desk`로 정하고 **Deploy**
4. **Edit code** 를 눌러 기존 코드를 전부 지우고, 이 저장소의 `worker/worker.js` 내용을 붙여넣은 뒤 **Deploy**
5. 화면 위에 나온 주소(`https://trading-desk.<내아이디>.workers.dev`)를 복사
6. 사이트 오른쪽 위 **⚙** → 주소 붙여넣기 → **저장하고 연결 확인**

"연결됐어요" 가 뜨면 끝이에요. 무료 플랜은 하루 10만 번 요청까지라 개인 사용에는 충분해요.
다른 사람이 내 중계 서버를 쓰지 못하게 하려면 `worker.js` 위쪽 `ALLOWED_ORIGINS`에 `"https://<내아이디>.github.io"`를 넣으세요.

## GitHub에 올리기

1. GitHub에서 새 저장소 만들기 (예: `trading-desk`). GitHub Pages 무료 사용은 **Public** 저장소 기준입니다. 보유 내역은 브라우저에만 저장되니 공개해도 노출되지 않아요.
2. 이 폴더 내용을 그대로 올리기
   ```bash
   git init
   git add .
   git commit -m "first commit"
   git branch -M main
   git remote add origin https://github.com/<내아이디>/trading-desk.git
   git push -u origin main
   ```
3. **Settings → Actions → General → Workflow permissions** 에서 **Read and write permissions** 선택 후 저장 (Actions가 시세를 커밋할 수 있게)
4. **Settings → Pages** 에서 Source를 **Deploy from a branch**, Branch를 **main / (root)** 로 저장
5. **Actions** 탭 → **시세 데이터 갱신** → **Run workflow** 로 한 번 실행
6. 1~2분 뒤 `https://<내아이디>.github.io/trading-desk/` 접속

## 종목 추가

`watchlist.json`에 한 줄 추가하고 커밋하면 다음 갱신 때 반영됩니다.

```json
{ "symbol": "042700.KS", "name": "한미반도체", "intraday": true }
```

- 코스피 `.KS`, 코스닥 `.KQ`, 미국 주식은 티커 그대로 (`NVDA`, `TSLA`)
- `intraday: true` 면 5분봉(최근 60거래일)도 저장 → 단타 백테스트 가능

## 로컬에서 보기

```bash
pip install -r requirements.txt
python scripts/fetch_data.py      # 시세 받기
python -m http.server 8000        # http://localhost:8000 접속
```
`index.html`을 더블클릭해서 열면 브라우저 보안 때문에 데이터를 못 읽어요. 꼭 위처럼 서버로 여세요.

## 백테스트 규칙

- 롱(매수)만, 신호가 나오면 자금 전액 진입/청산
- 신호는 봉 **종가**로 판단, 체결은 **다음 봉 시가** (미래 데이터 참조 방지)
- 손절/익절/트레일링은 봉 안에서 체결, 같은 봉에서 둘 다 닿으면 **손절 우선** (보수적)
- 갭으로 손절가를 뚫고 시작하면 시가에 체결
- 기본 비용: 매수 수수료 0.015%, 매도 수수료+거래세 0.215%, 슬리피지 편도 0.05%. 본인 증권사·세율에 맞게 바꾸세요.
- TradingView에서 CSV로 내보낸 데이터(`time, open, high, low, close, Volume`)도 불러와서 백테스트할 수 있어요.

## 데이터 출처와 한계

- 한국 일봉: FinanceDataReader (네이버). 야후 일봉 종가가 실제와 어긋나는 경우가 있어서 이쪽을 씀
- 5분봉·미국 주식: yfinance (야후)
- 검색한 종목: 중계 서버를 통해 한국 일봉은 네이버, 분봉과 미국 주식은 야후에서 받음. 주봉·월봉은 일봉을 묶어서 만들고, 15분·30분·1시간봉은 저장된 5분봉을 묶어서 만듦
- 검색 목록: 한국 전 종목과 ETF(FinanceDataReader), 미국은 시가총액 3억 달러 이상(공개 데이터셋 US-Stock-Symbols). 하루 한 번 갱신
- 야후의 한국 5분봉은 **15:00 무렵까지만** 제공되고 마감 동시호가가 빠져 있어요. 분봉 백테스트의 "당일청산"은 그날 마지막 봉(보통 14:55) 종가 기준입니다.
- GitHub Actions 예약 실행은 몇 분씩 늦어질 수 있어서 실시간 시세 용도는 아닙니다.

개인 학습·연구용 도구입니다. 과거 수익률이 미래 수익을 보장하지 않습니다.
