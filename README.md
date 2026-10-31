# Trading Desk

나만의 주식 현황 · 포트폴리오 · 백테스트 사이트. GitHub Pages에 무료로 올려서 쓰는 정적 사이트입니다.

- **현황**: 관심종목 현재가, 등락률, 52주 범위, 일봉/5분봉 차트 (이동평균 20/60/120)
- **포트폴리오**: 보유 종목 평가액, 손익, 수익률, 비중. 보유 내역은 **내 브라우저에만 저장**되고 GitHub에는 올라가지 않음
- **백테스트**: 이동평균 크로스 / RSI 역추세 / 볼린저 박스권 / 거래량 돌파(급등 포착) 전략, 손절·익절·트레일링·당일청산, 수수료·세금·슬리피지 반영, 매매 시점 차트와 자산 곡선, 거래 내역 CSV 저장
- **Pine Script 내보내기**: 백테스트한 전략과 설정을 TradingView용 코드로 바로 변환

## 구조

```
index.html                     화면
assets/app.js                  화면 로직 (현황, 포트폴리오, 백테스트 UI)
assets/backtest.js             백테스트 엔진, 지표, 전략, Pine Script 생성
assets/style.css               스타일 (한국식: 상승 빨강 / 하락 파랑)
watchlist.json                 관심종목 목록  ← 여기만 고치면 종목 추가
scripts/fetch_data.py          시세 수집 → data/ 에 JSON 저장
.github/workflows/update-data.yml   평일 장중 30분마다 자동 갱신
data/                          수집된 시세 (자동 생성)
```

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
- 야후의 한국 5분봉은 **15:00 무렵까지만** 제공되고 마감 동시호가가 빠져 있어요. 분봉 백테스트의 "당일청산"은 그날 마지막 봉(보통 14:55) 종가 기준입니다.
- GitHub Actions 예약 실행은 몇 분씩 늦어질 수 있어서 실시간 시세 용도는 아닙니다.

개인 학습·연구용 도구입니다. 과거 수익률이 미래 수익을 보장하지 않습니다.
