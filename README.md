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
- **백테스트**
  - 대상: 한 종목, 또는 여러 종목(관심종목 / 시가총액 상위 20·50 / 직접 고르기)을 동일 비중 포트폴리오로
  - 전략: 이동평균 크로스, RSI 역추세, 볼린저 박스권, 거래량 돌파, **직접 만들기(지표·비교·교차 조건을 AND/OR로 조합)**
  - 방향과 비중: 롱 / 숏 / 양방향, 자산 전액·일정 비율·ATR 위험 기준, 분할매수(물타기·불타기·신호 반복), 1차 익절 일부 매도, 대주 수수료
  - 리스크: 손절·익절·트레일링(평균단가 기준), 최대 보유 봉, 장 마감 전 청산
  - 체결 규칙(선택): 한국 호가 단위·1주 단위, 상·하한가에서 체결 불가, 한 봉 거래량 대비 주문 한도
  - 지표: 총수익, 보유 대비, 코스피200 대비, CAGR, MDD, 샤프·소르티노·칼마, 승률, 손익비, 거래당 기대값, 최대 연속 손실, 평균 보유, 시장 노출, 월별 수익표, 낙폭 차트
  - **설정 자동 탐색**: 항목별 범위를 정하면 모든 조합을 돌려, 앞 구간(학습)에서 고른 설정이 뒤 구간(검증)에서도 통하는지와 학습·검증 순위 상관을 보여줌. 두 항목이면 조합별 성적 표(히트맵)
  - **저장한 결과**: 실행 결과를 저장하고 여러 개를 나란히 비교, 자산 곡선 겹쳐보기, 설정 다시 불러오기
- **대화로 설정하기**: 백테스트 탭에서 "SK하이닉스 1시간봉 RSI 25/75, 손절 3% 넣어서 돌려줘", "손절 넣으면 나아질까? 비교해줘" 처럼 말로 설정·실행하고 결과 해석과 추천을 받음 (Claude API 연결 필요, 연결 전에는 간단한 명령만 인식)
- **Pine Script 내보내기**: 백테스트한 전략과 설정을 TradingView용 코드로 바로 변환

## 구조

```
index.html                     화면
assets/data.js                 시세 불러오기 (저장된 시세 / 중계 서버), 종목 검색, 봉 묶기
assets/chart.js                메인 차트, 보조지표, 범례
assets/draw.js                 그리기 도구
assets/util.js                 공통 도구 (포맷, 검색 상자, 저장소)
assets/bt.js                   백테스트 화면 (한 종목·여러 종목, 자동 탐색, 저장·비교, 대화)
assets/app.js                  화면 연결 (차트, 포트폴리오, 설정)
assets/backtest.js             백테스트 엔진 v2 (방향·비중·분할·체결 규칙), 지표, 전략, 조건 조합, Pine Script 생성
assets/style.css               스타일 (한국식: 상승 빨강 / 하락 파랑)
watchlist.json                 기본 관심종목  ← 여기 넣은 종목은 중계 서버 없이도 보임
scripts/fetch_data.py          시세 수집 → data/ 에 JSON 저장, 검색용 종목 목록 생성
worker/worker.js               중계 서버 (Cloudflare Workers): 시세 중계 + 대화 도우미용 Claude API 연결
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
중계 서버는 `worker.js` 위쪽 `ALLOWED_ORIGINS`에 적힌 사이트(`https://kelvenkim.github.io`, 로컬 테스트용 `http://localhost:8000`)에서만 쓸 수 있어요. 다른 주소에서 쓰려면 거기에 추가하세요.

## 대화 도우미 연결하기 (선택)

백테스트 탭의 대화창이 Claude와 대화하려면 **Claude API 키**가 필요해요. claude.ai 구독과는 별개로, API는 쓴 만큼 요금이 나가요(요금은 https://www.anthropic.com/pricing 참고). 키는 중계 서버에 비밀값으로만 넣고, 사이트 코드나 GitHub에는 절대 넣지 마세요.

1. https://platform.claude.com 에 로그인 → **Billing**에서 크레딧 충전 → **API Keys** → **Create Key** → 만들어진 키 복사 (`sk-ant-`로 시작, 다시 볼 수 없으니 바로 다음 단계로)
2. Cloudflare 대시보드 → 만든 Worker → **Edit code** → `worker/worker.js` 최신 내용으로 전부 바꿔 붙여넣기 → **Deploy**
3. Worker 화면 **Settings** → **Variables and Secrets** → **Add**
   - Type **Secret**, Name `ANTHROPIC_API_KEY`, Value 에 1번 키 → 저장
   - 한 번 더 **Add**: Type **Secret**, Name `CHAT_PASSWORD`, Value 에 내가 정한 비밀번호 → 저장 (남이 내 키로 대화하는 것을 막아줘요)
   - **Deploy** (저장 후 배포 버튼이 나오면 눌러주세요)
4. 사이트 오른쪽 위 **⚙** → **대화 도우미**에서 모델 고르고 **대화 비밀번호**에 3번 비밀번호 입력
5. 백테스트 탭 대화창에서 "삼성전자 5분봉 거래량 돌파 전략 돌려줘" 처럼 말해보기

중계 서버 주소를 브라우저에서 열었을 때 `Trading Desk proxy OK · chat ready` 가 보이면 키가 제대로 들어간 거예요.
연결 전에는 대화창이 **간단 모드**로 동작해서 "종목 + 봉 + 전략 + 손절 N + N년 + 실행" 같은 짧은 명령만 알아들어요.

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

## 화면 파일을 고친 뒤에는

`assets/` 안의 파일을 고쳤다면 커밋 전에 `python scripts/stamp_assets.py`를 실행하세요. `index.html`의 파일 주소에 버전이 붙어서, 브라우저가 예전 파일을 캐시에서 꺼내 쓰지 않아요.

## 로컬에서 보기

```bash
pip install -r requirements.txt
python scripts/fetch_data.py      # 시세 받기
python -m http.server 8000        # http://localhost:8000 접속
```
`index.html`을 더블클릭해서 열면 브라우저 보안 때문에 데이터를 못 읽어요. 꼭 위처럼 서버로 여세요.

## 백테스트 규칙

- 방향(롱·숏·양방향)과 비중(전액·비율·ATR 위험)은 설정에 따름. 숏은 매도 신호에 진입하고 매수 신호에 청산
- 손절·익절·1차 익절은 평균단가 기준, 분할매수하면 평균단가가 바뀜
- 신호는 봉 **종가**로 판단, 체결은 **다음 봉 시가** (미래 데이터 참조 방지)
- 손절/익절/트레일링은 봉 안에서 체결, 같은 봉에서 둘 다 닿으면 **손절 우선** (보수적)
- 갭으로 손절가를 뚫고 시작하면 시가에 체결
- 기본 비용: 매수 수수료 0.015%, 매도 수수료+거래세 0.215%, 슬리피지 편도 0.05%. 본인 증권사·세율에 맞게 바꾸세요.
- 설정 자동 탐색은 지표를 전체 기간으로 계산한 뒤 성과만 학습·검증 구간으로 나눠 계산 (구간 경계를 넘는 거래는 청산 시점 기준)
- 여러 종목은 자금을 종목 수로 똑같이 나눠 각자 운용한 합계
- TradingView에서 CSV로 내보낸 데이터(`time, open, high, low, close, Volume`)도 불러와서 백테스트할 수 있어요.

## 데이터 출처와 한계

- 한국 일봉: FinanceDataReader (네이버). 야후 일봉 종가가 실제와 어긋나는 경우가 있어서 이쪽을 씀
- 5분봉·미국 주식: yfinance (야후)
- 검색한 종목: 중계 서버를 통해 한국 일봉은 네이버, 분봉과 미국 주식은 야후에서 받음. 주봉·월봉은 일봉을 묶어서 만들고, 15분·30분·1시간봉은 저장된 5분봉을 묶어서 만듦
- 검색 목록: 한국 전 종목과 ETF(FinanceDataReader), 미국은 시가총액 3억 달러 이상(공개 데이터셋 US-Stock-Symbols). 하루 한 번 갱신
- 야후의 한국 5분봉은 **15:00 무렵까지만** 제공되고 마감 동시호가가 빠져 있어요. 분봉 백테스트의 "당일청산"은 그날 마지막 봉(보통 14:55) 종가 기준입니다.
- GitHub Actions 예약 실행은 몇 분씩 늦어질 수 있어서 실시간 시세 용도는 아닙니다.

개인 학습·연구용 도구입니다. 과거 수익률이 미래 수익을 보장하지 않습니다.

## 오늘의 순위 (매일 자동)

- `scripts/rank_daily.py` 가 평일 16:20(KST)에 시총 상위 300 종목을 항목별(추세·변동성·금리/환율 민감도·뉴스·실적 등)로 점수 매겨 `data/rank/latest.json` 에 저장해요.
- 그날 순위는 `data/rank/snap/` 에 남고, 5일·20일 뒤 실제 수익률로 채점돼 `data/rank/live.json` 에 쌓여요. 항목별 비중은 이 채점 결과(+과거 검증)로 매일 다시 정해져요.
- **DART 실적 켜기**: opendart.fss.or.kr 에서 인증키 발급 → 저장소 Settings → Secrets and variables → Actions → New repository secret → 이름 `DART_API_KEY`, 값에 키. 그 다음 Actions 탭에서 "순위 과거 검증 다시 계산"을 한 번 실행하면 실적 항목도 2014년부터 과거 공시로 검증돼요.


## 미국 주식 중심 개편 (2026-11-06)

- 첫 화면은 **홈**: 지수·금리·환율·유가·금·비트코인(장중 1분마다 실시간), 섹터 흐름, 많이 오른/내린 종목, 시장 체력, 강한 테마, 추천 바구니, 주요 뉴스, 거시 예측시장
- 차트: 미국 종목은 열 때 최신 시세, 열어두면 1분마다 자동 갱신(장 밖은 15분), 분봉 시각은 뉴욕 시각, 아래에 미국장 상태·마지막 갱신 시각
- `scripts/us_daily.py` (Actions `us-daily.yml`, 미국장 마감 후): S&P500+나스닥100 순위(테마 눌림·추천 바구니·모멘텀·우리 점수, 다음 날 시가 기준 채점·추적), 미국 장기 테마 16개(`scripts/us_narr_def.py`), 추천 기업(월가 애널리스트·StockTwits·예측시장)
- 과거 검증: `research/us/variants.py`, `research/us/theme_backfill.py`
- 한국 순위 자동 실행(`rank-daily.yml`)은 멈춤 (코드는 남겨둠)
