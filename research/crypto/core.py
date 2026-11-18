from ens import *
def core(d, tv=0.6, cap=1.0, f200=False, n_vol=20):
    E=s_ens(d)
    if f200: E=E*(d.Close>sma(d.Close,200)).astype(float)
    return E*vt_size(d,tv,n_vol,cap)
