"""
주식시장에 영향을 주는 단어 사전 — 뉴스 탭 '인물이 자주 쓰는 단어'에서 이 목록에 있는 것만 셈
(이름, 영어 패턴(정규식, 소문자), 한국어 포함 단어, 관련 장기 테마)
"""
TERMS = [
    # 기술
    ("AI", [r"\bai\b", r"artificial intelligence"], ["AI", "인공지능", "생성형"], ["software", "ai_chip"]),
    ("양자컴퓨팅", [r"\bquantum\b"], ["양자"], ["software"]),
    ("반도체", [r"\bchips?\b", r"semiconductor", r"\bfabs?\b"], ["반도체", "파운드리", "칩"], ["ai_chip"]),
    ("HBM·메모리", [r"\bhbm\b", r"\bmemory\b", r"\bdram\b"], ["HBM", "메모리", "D램", "낸드"], ["ai_chip"]),
    ("엔비디아", [r"nvidia"], ["엔비디아"], ["ai_chip"]),
    ("데이터센터", [r"data cent(er|re)s?"], ["데이터센터"], ["power", "ai_chip"]),
    ("클라우드·소프트웨어", [r"\bcloud\b", r"software"], ["클라우드", "소프트웨어", "SaaS"], ["software"]),
    ("오픈AI·빅테크", [r"openai", r"\bgoogle\b", r"microsoft", r"\bapple\b", r"\bamazon\b", r"\bmeta\b"], ["오픈AI", "구글", "마이크로소프트", "애플", "아마존", "메타"], ["software"]),
    ("로봇·휴머노이드", [r"\brobots?\b", r"humanoid", r"optimus"], ["로봇", "휴머노이드", "피지컬"], ["robot"]),
    ("자율주행·전기차", [r"self-driving", r"autonomous", r"robotaxi", r"\bevs?\b", r"electric vehicles?"], ["자율주행", "로보택시", "전기차"], ["auto", "battery"]),
    ("배터리·리튬", [r"batter(y|ies)", r"lithium"], ["배터리", "2차전지", "리튬", "전고체"], ["battery"]),
    ("우주·위성", [r"\bspace\b", r"starlink", r"satellites?", r"rockets?"], ["우주", "위성", "스타링크", "스페이스X", "발사체"], ["defense"]),
    ("통신·5G", [r"\b5g\b", r"\b6g\b", r"broadband", r"spectrum"], ["5G", "6G", "통신"], []),
    # 에너지·인프라
    ("전력·전력망", [r"electricity", r"power grid", r"\bgrid\b", r"power plants?"], ["전력", "전력망", "송전", "변압기"], ["power"]),
    ("원전·우라늄", [r"nuclear power", r"nuclear energy", r"reactors?", r"uranium", r"\bsmr"], ["원전", "SMR", "원자력", "우라늄"], ["nuclear"]),
    ("석유·가스", [r"\boil\b", r"drill", r"\blng\b", r"natural gas", r"\bgas\b", r"pipeline"], ["유가", "석유", "원유", "LNG", "가스", "시추"], ["ship"]),
    ("태양광·풍력", [r"\bsolar\b", r"\bwind\b", r"windmills?", r"renewable", r"green new"], ["태양광", "풍력", "재생에너지", "신재생"], ["green"]),
    ("수소", [r"hydrogen"], ["수소"], ["green"]),
    ("조선·해운", [r"shipbuilding", r"\bships?\b", r"shipyards?", r"\bnavy\b", r"shipping"], ["조선", "선박", "해운", "MRO", "마스가"], ["ship"]),
    ("방산·국방", [r"\bdefen[cs]e\b", r"military", r"weapons?", r"\bmissiles?\b", r"\bnato\b", r"pentagon", r"department of war"], ["방산", "국방", "무기", "미사일", "나토"], ["defense"]),
    ("건설·인프라", [r"infrastructure", r"construction", r"\bbridges?\b", r"\bports?\b"], ["건설", "인프라", "재건", "SOC"], ["infra"]),
    # 무역·원자재
    ("관세", [r"tariffs?"], ["관세"], ["auto", "materials"]),
    ("무역·수출", [r"\btrade\b", r"exports?", r"imports?", r"trade deal"], ["무역", "수출", "수입", "통상"], []),
    ("희토류·핵심광물", [r"rare earths?", r"critical minerals", r"\bminerals?\b"], ["희토류", "핵심광물", "광물"], ["materials"]),
    ("철강·금속", [r"\bsteel\b", r"aluminum", r"copper"], ["철강", "알루미늄", "구리", "비철"], ["materials"]),
    ("자동차", [r"\bcars?\b", r"\bautos?\b", r"automakers?", r"auto industry"], ["자동차", "완성차"], ["auto"]),
    ("제약·약값", [r"drug prices?", r"pharmaceutical", r"\bpharma\b", r"\bdrugs?\b", r"\bfda\b", r"vaccines?"], ["제약", "신약", "약가", "약값", "FDA", "바이오", "비만"], ["bio"]),
    # 거시·금융
    ("금리·연준", [r"interest rates?", r"\brates?\b", r"\bfed\b", r"federal reserve", r"powell", r"rate cut"], ["금리", "연준", "기준금리", "FOMC", "인하", "인상"], []),
    ("물가", [r"inflation", r"prices are", r"cost of living", r"affordab"], ["물가", "인플레이션", "CPI"], []),
    ("고용·경기", [r"\bjobs?\b", r"unemployment", r"recession", r"\bgdp\b", r"economy"], ["고용", "일자리", "실업", "경기침체", "GDP", "성장률"], []),
    ("세금·재정", [r"\btax(es)?\b", r"tax cuts?", r"deficit", r"\bdebt\b", r"budget", r"spending bill"], ["세금", "감세", "재정", "부채", "예산", "국채"], []),
    ("규제", [r"regulations?", r"deregulat", r"antitrust"], ["규제", "독점", "반독점"], []),
    ("증시", [r"stock market", r"\bstocks?\b", r"\bdow\b", r"nasdaq", r"s&p", r"401\(?k"], ["증시", "주가", "코스피", "나스닥", "S&P", "다우"], []),
    ("달러·환율", [r"\bdollar\b", r"currency", r"exchange rate"], ["환율", "원화", "강달러", "약달러", "달러 강세", "달러 약세", "달러화", "달러인덱스"], []),
    ("가상자산", [r"bitcoin", r"\bcrypto", r"stablecoins?", r"digital assets?"], ["비트코인", "가상자산", "암호화폐", "스테이블코인", "코인"], ["digital"]),
    ("금·안전자산", [r"\bgold\b"], ["금값", "금 가격", "안전자산"], ["materials"]),
    ("투자·공장", [r"investment", r"invest(ing|ed)? in", r"factor(y|ies)", r"manufactur", r"reshoring"], ["투자", "공장", "제조업", "생산기지"], []),
    # 나라·지정학 (시장에 영향)
    ("중국", [r"\bchina\b", r"chinese", r"\bxi\b"], ["중국", "시진핑"], []),
    ("한국", [r"\bkorea", r"\bsamsung\b", r"hyundai", r"sk hynix"], ["한국", "삼성", "SK", "현대"], ["valueup"]),
    ("일본", [r"\bjapan"], ["일본"], []),
    ("대만", [r"taiwan", r"\btsmc\b"], ["대만", "TSMC"], ["ai_chip"]),
    ("유럽·EU", [r"\beurope", r"\beu\b", r"european union"], ["유럽", "EU"], []),
    ("멕시코·캐나다", [r"mexico", r"canada"], ["멕시코", "캐나다"], ["auto"]),
    ("러시아·우크라이나", [r"russia", r"ukrain", r"putin", r"zelensk", r"ceasefire"], ["러시아", "우크라이나", "푸틴", "젤렌스키", "휴전"], ["defense", "infra"]),
    ("중동·이란", [r"\biran", r"israel", r"middle east", r"hormuz", r"gaza"], ["이란", "이스라엘", "중동", "호르무즈", "가자"], ["defense", "ship"]),
]


# 단어를 셀 때 빼는 글: 선거 후보 지지글처럼 같은 상투 문구가 반복되는 글
EN_SKIP = [r"\bendorse", r"complete and total", r"running for", r"\bcandidate\b", r"\bvote for\b", r"get out and vote", r"\bballot", r"\bsenator\b", r"\bgovernor\b", r"congress(wo)?man", r"true american patriot",
           r"\bhas my\b", r"doing an? \w+ job", r"\bpoll(s|ing)?\b", r"\belection\b", r"\bvoters?\b",
           r"\brepresentative\b", r"congressional", r"\bdistrict\b", r"great people of", r"wisdom and courage", r"\bmayor\b",
           r"attorney general", r"\bsheriff\b", r"let you down", r"america first patriot", r"\bprimary\b", r"re-?elect"]
