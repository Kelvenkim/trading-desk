"""
장기 테마(내러티브) 정의 — 기술·트렌드·정책 관점의 큰 이야기 16개
themes: 네이버 증권 테마 이름에 들어 있으면 그 테마 종목을 이 이야기에 넣음 (시총 상위 300 안의 종목만 사용)
story: 이 이야기가 왜 생겼는지 (기술 / 트렌드 / 정책) — 사람이 읽는 설명, 자동 판단에는 안 씀
words: 이 이야기와 관련된 정책·사업 키워드 (뉴스 제목에서 정책 신호를 셀 때 같이 씀)
"""

NARRATIVES = [
    {"key": "ai_chip", "name": "AI 반도체·HBM",
     "themes": ["HBM", "반도체 대표주", "CXL", "소캠", "반도체 장비", "반도체 재료", "반도체 기판", "유리 기판", "시스템반도체", "온디바이스 AI", "냉각시스템"],
     "story": {"기술": "AI 학습·추론에 고대역폭 메모리(HBM)와 첨단 패키징이 필수", "트렌드": "빅테크의 데이터센터 투자 경쟁", "정책": "반도체 특별법·세액공제, 미국 수출 규제"},
     "words": ["HBM", "반도체 특별법", "세액공제", "수출 규제", "보조금", "데이터센터"]},
    {"key": "power", "name": "AI 전력 인프라",
     "themes": ["전력설비", "전선", "스마트그리드", "전력저장장치", "전력반도체"],
     "story": {"기술": "데이터센터 전력 수요 급증, 초고압 변압기·전선 부족", "트렌드": "미국 노후 전력망 교체 주기", "정책": "전력망 특별법, 미국 인프라 투자"},
     "words": ["전력망", "변압기", "송전", "전력망 특별법", "수주", "ESS"]},
    {"key": "nuclear", "name": "원전·SMR",
     "themes": ["원자력발전", "핵융합"],
     "story": {"기술": "소형모듈원전(SMR)으로 데이터센터 직접 전력 공급", "트렌드": "탄소중립 + 전력 수요로 원전 재평가", "정책": "원전 수출(체코 등), 미국 원전 확대 행정명령"},
     "words": ["원전", "SMR", "체코", "수출", "원자력", "탈원전"]},
    {"key": "defense", "name": "방산·우주",
     "themes": ["방위산업", "우주항공", "항공기부품", "드론"],
     "story": {"기술": "K9·K2·천무 등 가성비 무기, 위성·발사체", "트렌드": "유럽·중동 재무장, 공급 가능한 나라가 적음", "정책": "방산 수출 금융 지원, 우주항공청"},
     "words": ["방산", "수출", "폴란드", "나토", "국방", "우주항공청", "수주"]},
    {"key": "ship", "name": "조선·LNG",
     "themes": ["조선", "LNG(액화천연가스)", "해운"],
     "story": {"기술": "LNG선·친환경 선박 기술 우위", "트렌드": "선박 교체 주기 + 미국 해군 MRO 협력", "정책": "한미 조선 협력(마스가), 해운 환경 규제"},
     "words": ["수주", "LNG선", "MRO", "마스가", "미 해군", "조선 협력"]},
    {"key": "valueup", "name": "밸류업·주주환원",
     "themes": ["지주사", "은행", "증권", "생명보험", "손해보험", "인터넷은행"],
     "story": {"기술": "—", "트렌드": "코리아 디스카운트 해소, 배당·자사주 소각 확대", "정책": "기업가치 제고 계획, 상법 개정, 배당소득 분리과세"},
     "words": ["밸류업", "상법 개정", "자사주 소각", "배당", "분리과세", "주주환원"]},
    {"key": "robot", "name": "로봇·피지컬 AI",
     "themes": ["피지컬 AI", "로봇(산업용", "지능형로봇", "스마트팩토리"],
     "story": {"기술": "휴머노이드·AI가 몸을 가진 로봇", "트렌드": "제조 인력 부족, 테슬라·엔비디아의 로봇 투자", "정책": "로봇 산업 육성, 스마트공장 지원"},
     "words": ["휴머노이드", "로봇", "피지컬 AI", "자동화", "지원"]},
    {"key": "battery", "name": "2차전지",
     "themes": ["2차전지", "리튬", "폐배터리"],
     "story": {"기술": "전고체·LFP·나트륨 등 차세대 전지", "트렌드": "전기차 수요 둔화 vs ESS 수요 증가", "정책": "미국 IRA 보조금 변화, 중국 견제"},
     "words": ["IRA", "보조금", "전고체", "LFP", "ESS", "관세"]},
    {"key": "bio", "name": "바이오·비만치료제",
     "themes": ["비만치료제", "바이오시밀러", "면역항암제", "유전자 치료", "보톡스", "제약업체"],
     "story": {"기술": "GLP-1 비만약, 항체·ADC 신약, 바이오시밀러", "트렌드": "기술수출(라이선스 아웃) 증가, 금리 하락 시 강세", "정책": "미국 약가 정책, 생물보안법"},
     "words": ["기술수출", "임상", "FDA", "승인", "약가", "생물보안법"]},
    {"key": "kculture", "name": "K-소비·콘텐츠",
     "themes": ["화장품", "엔터테인먼트", "음원/음반", "웹툰", "영상콘텐츠", "면세점"],
     "story": {"기술": "—", "트렌드": "K-뷰티 미국 수출, K-팝·콘텐츠 해외 확산", "정책": "중국 단체관광 재개, 한한령 완화"},
     "words": ["수출", "한한령", "단체관광", "K-뷰티", "콘서트", "미국"]},
    {"key": "auto", "name": "자동차·자율주행",
     "themes": ["자동차 대표주", "자동차부품", "자율주행", "전기차"],
     "story": {"기술": "자율주행·SDV(소프트웨어 중심 차)", "트렌드": "하이브리드 수요, 미국 현지 생산", "정책": "미국 자동차 관세"},
     "words": ["관세", "자율주행", "하이브리드", "현지 생산", "판매"]},
    {"key": "digital", "name": "디지털자산·핀테크",
     "themes": ["스테이블코인", "가상화폐", "STO", "블록체인", "핀테크", "두나무", "전자결제"],
     "story": {"기술": "블록체인 결제·토큰증권", "트렌드": "스테이블코인 확산, 디지털 결제", "정책": "원화 스테이블코인 법제화, 토큰증권 법안"},
     "words": ["스테이블코인", "법제화", "디지털자산", "토큰증권", "가상자산", "법안"]},
    {"key": "infra", "name": "건설·재건",
     "themes": ["건설 대표주", "전후 재건", "건설기계", "시멘트"],
     "story": {"기술": "—", "트렌드": "우크라이나·중동 재건, 해외 플랜트", "정책": "부동산 공급 대책, SOC 예산"},
     "words": ["재건", "수주", "공급 대책", "SOC", "플랜트", "규제 완화"]},
    {"key": "software", "name": "AI 소프트웨어·클라우드",
     "themes": ["클라우드", "AI 챗봇", "SI(시스템통합)", "보안주(정보)", "양자"],
     "story": {"기술": "생성형 AI 서비스, 소버린 AI, 양자컴퓨팅", "트렌드": "기업 AI 도입", "정책": "국가 AI 컴퓨팅 센터, AI 기본법"},
     "words": ["AI 기본법", "소버린", "GPU", "데이터센터", "정부", "클라우드"]},
    {"key": "green", "name": "태양광·풍력·수소",
     "themes": ["태양광", "풍력", "수소에너지"],
     "story": {"기술": "태양광 효율·해상풍력·수소 연료전지", "트렌드": "탄소중립, 재생에너지 비중 확대", "정책": "재생에너지 보조금, 해상풍력 특별법"},
     "words": ["해상풍력", "특별법", "재생에너지", "보조금", "탄소중립"]},
    {"key": "materials", "name": "철강·비철·소재",
     "themes": ["철강 주요종목", "비철금속", "희귀금속", "석유화학"],
     "story": {"기술": "—", "트렌드": "중국 공급 과잉 vs 구조조정, 원자재 가격", "정책": "석유화학 구조조정, 미국 철강 관세, 희토류 공급망"},
     "words": ["관세", "구조조정", "희토류", "공급망", "가격 인상"]},
]

POLICY_WORDS = ["정부", "정책", "예산", "법안", "특별법", "국회", "대통령", "산업부", "산업통상", "금융위", "과기정통부", "국토부",
                "기재부", "세액공제", "보조금", "행정명령", "관세", "법제화", "규제 완화", "규제완화", "육성책", "대책", "상법", "국정과제"]

# 자동 분류가 어긋난 종목 손보기 (종목코드)
EXCLUDE = {"ai_chip": ["010950", "078930"], "green": ["004020", "015760"]}
INCLUDE = {"nuclear": ["015760"]}

# 예측시장(Polymarket) 검색어: (검색어, 제목에 꼭 들어가야 할 단어들)
PM = {
    "ai_chip": [("nvidia", ["NVIDIA", "Nvidia", "NVDA"]), ("semiconductor tariff", ["semiconductor", "chip", "Chip"])],
    "power": [("data center", ["data center", "Data center", "Data Center"]), ("electricity price", ["electric", "Electric"])],
    "nuclear": [("nuclear power plant", ["nuclear power", "reactor", "SMR", "power plant"]), ("uranium price", ["uranium", "Uranium"])],
    "defense": [("Russia Ukraine ceasefire", ["ceasefire", "Ceasefire"]), ("NATO defense spending", ["NATO", "defense"])],
    "ship": [("shipbuilding", ["ship", "Ship"]), ("Strait of Hormuz", ["Hormuz"])],
    "valueup": [("South Korea KOSPI", ["KOSPI", "Korea"]), ("South Korea", ["Korea", "Korean"])],
    "robot": [("Tesla Optimus", ["Optimus", "humanoid", "Humanoid", "robot"]), ("humanoid robot", ["robot", "humanoid"])],
    "battery": [("Tesla deliveries", ["Tesla"]), ("EV tax credit", ["EV", "electric vehicle"])],
    "bio": [("FDA approval", ["FDA"]), ("GLP-1 obesity", ["GLP", "Ozempic", "Wegovy", "obesity", "Obesity"])],
    "kculture": [("BTS", ["BTS"]), ("China South Korea", ["Korea"])],
    "auto": [("auto tariffs", ["auto", "Auto", "car"]), ("Tesla robotaxi", ["robotaxi", "Robotaxi"])],
    "digital": [("bitcoin price", ["Bitcoin", "BTC"]), ("stablecoin", ["stablecoin", "Stablecoin"])],
    "infra": [("Ukraine reconstruction", ["Ukraine"]), ("Russia Ukraine ceasefire", ["ceasefire", "Ceasefire"])],
    "software": [("OpenAI", ["OpenAI"]), ("best AI model", ["AI"])],
    "green": [("solar energy", ["solar", "Solar"]), ("renewable energy", ["renewable", "energy"])],
    "materials": [("steel tariff", ["steel", "Steel"]), ("copper price", ["copper", "Copper"]), ("rare earth", ["rare earth", "Rare earth"])],
}
PM_MACRO = [("Fed rate cuts 2026", ["Fed"]), ("US recession 2026", ["recession", "Recession"])]

# 회사 이름 → 영어 검색어 (예측시장에 개별 기업 시장이 있을 때만 걸림)
EN_NAME = [("삼성", "Samsung"), ("SK하이닉스", "SK Hynix"), ("현대", "Hyundai"), ("기아", "Kia"), ("한화", "Hanwha"), ("LG", "LG "),
           ("NAVER", "Naver"), ("카카오", "Kakao"), ("셀트리온", "Celltrion"), ("하이브", "HYBE"), ("두산", "Doosan"), ("포스코", "POSCO")]
