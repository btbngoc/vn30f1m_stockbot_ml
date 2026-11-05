import json,pandas as pd
from pathlib import Path
from ..backtest.engine import BacktestEngine
from .short_distribution_audit import load_features
from .setup_audit import _event_start,_metrics
B=Path(__file__).resolve().parents[1];O=B/'models'/'short_v4_benchmark.json';C=['Open','High','Low','Close','ATR']
def main():
 d=load_features();d=d.dropna(subset=['ATR','RVOL','VWAP','Volume_MA20']).copy();d['MA20']=d.Close.rolling(20).mean();d['MA50']=d.Close.rolling(50).mean();hh=d.High.rolling(20).max().shift(1);weak=(d.Close<=(d.High+d.Low)/2);supply=(d.get('HTF_5m_SupplyZone',0)==1)|(d.Close>=d.High.rolling(60).max().shift(1)*.995);sweep=(d.High>hh)&(d.Close<hh)&weak;down=(d.MA20<d.MA50)&(d.MA50.diff(10)<0)
 raw={'LIQUIDITY_SWEEP':sweep&supply,'UPTHRUST':(d.get('HTF_5m_UTAD',0)==1)&supply,'FAILED_BREAKOUT':sweep,'VWAP_REJECT':(d.High>=d.VWAP)&(d.Close<d.VWAP)&weak,'TREND_CONTINUATION':down&(d.High.shift(1)>=d.MA20.shift(1))&(d.Close<d.MA20)&weak}
 out=[]
 for name,e in raw.items():
  for layer,s in [('RAW',e),('VOLUME',e&(d.RVOL>=1.5)),('CONFIRM',e.shift(1,fill_value=False)&(d.Close<d.Low.shift(1)))]:
   x=d[C].copy();x['Signal']=-_event_start(s).astype(int);t=BacktestEngine(x).run();yrs=[]
   for y in [2024,2025,2026]:
    z=t[pd.to_datetime(t['Entry Date']).dt.year==y] if not t.empty else t;yrs.append({'period':str(y),**_metrics(z)})
   out.append({'setup':name,'layer':layer,'events':int(_event_start(s).sum()),'all_history':_metrics(t),'years':yrs})
 O.write_text(json.dumps({'execution':'commission=0; SMA V4 raw/volume/1m confirmation benchmark','results':out},indent=2),encoding='utf8')
if __name__=='__main__':main()

