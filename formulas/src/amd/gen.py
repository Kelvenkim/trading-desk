import random
random.seed(7)
C=[]  # o,h,l,c,v
p=106.0
def bar(o,c,wu=0.3,wd=0.3,v=1.0):
    C.append((o,max(o,c)+wu,min(o,c)-wd,c,v))
# 0) 앞선 하락
for i in range(9):
    o=p; c=p-random.uniform(0.4,1.0); bar(o,c,random.uniform(.1,.4),random.uniform(.1,.4),1.2); p=c
# 1) 매집: 98~102 박스, 100 근처에 몰림
for i in range(28):
    o=p; tgt=100+random.uniform(-1.4,1.4); c=o+(tgt-o)*0.7; c=min(101.6,max(98.4,c))
    bar(o,c,random.uniform(.1,.5),random.uniform(.1,.5),random.uniform(.5,.9)); p=c
lo_box=min(x[2] for x in C[9:37]); hi_box=max(x[1] for x in C[9:37])
# 2) 조작: 박스 아래를 깨고 손절 물량 쓸기 → 긴 아래꼬리로 다시 안으로
bar(p,98.6,.2,.3,1.1); p=98.6
bar(p,97.6,.2,.2,1.6); p=97.6
bar(p,99.2,.3,1.9,2.6); p=99.2      # 스윕 캔들: 저가 ~95.7
bar(p,100.4,.3,.2,1.8); p=100.4     # 박스 안 복귀·POC 위 마감
# 3) POC 되돌림 (진입)
bar(p,100.0,.2,.15,1.0); p=100.0
bar(p,100.9,.3,.2,1.2); p=100.9
# 4) 분산(진짜 방향): 강한 상승
for i in range(18):
    o=p; c=p+random.uniform(0.3,1.1)*(1 if random.random()>0.2 else -0.6); bar(o,c,random.uniform(.1,.5),random.uniform(.1,.4),random.uniform(1.1,1.8)); p=c
print(len(C), lo_box, hi_box, p)
import json; json.dump(dict(C=C,lo=lo_box,hi=hi_box),open('c.json','w'))
