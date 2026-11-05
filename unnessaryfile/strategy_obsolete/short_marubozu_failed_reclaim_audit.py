import json
from pathlib import Path
import pandas as pd
from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import PERIODS,_event_start,_metrics
from .short_distribution_audit import load_features
B=Path(__file__).resolve().parents[1];O=B/'models'/'short_marubozu_failed_reclaim_raw_audit.json';T=B/'models'/'short_marubozu_failed_reclaim_raw_trades.csv';C=['Open','High','Low','Close','ATR']
def build(df):
 b=df.index.floor('5min');h=df.groupby(b).agg(Open=('Open','first'),High=('High','max'),Low=('Low','min'),Close=('Close','last'),Volume=('Volume','sum'))
 p=h.Close.shift();tr=pd.concat([h.High-h.Low,(h.High-p).abs(),(h.Low-p).abs()],axis=1).max(axis=1);h['ATR']=tr.rolling(14).mean();state='';old=None;age=0;last=None;m=[];f=[]
 for ts,r in h.iterrows():
  if last is not None and ts-last>pd.Timedelta(minutes=10):state='';age=0
  rng=max(r.High-r.Low,1e-9);maru=bool(pd.notna(r.ATR) and r.Close<r.Open and abs(r.Close-r.Open)/rng>=.8 and rng>=r.ATR)
  fail=False
  if maru: state='wait';old=r.High;age=0
  elif state=='wait':
   age+=1
   if 2<=age<=20: fail=bool(r.High>old and r.Close<=old and (r.Close-r.Low)/rng<=.45)
   if fail or age>20:state=''
  m.append(int(maru));f.append(int(fail));last=ts
 done=pd.Series(f,index=h.index).shift(1).fillna(0).astype(int);z=pd.Series(b,index=df.index).map(done).fillna(0).astype(int)
 return _event_start(z==1),{'large_bearish_marubozus':int(_event_start(pd.Series(m,index=h.index)==1).sum()),'failed_reclaims':int(_event_start(pd.Series(f,index=h.index)==1).sum())}
def bt(df,s):
 x=df[C].copy();x['Signal']=-s.astype(int);return BacktestEngine(x).run()
def main():
 df=load_features();s,st=build(df);a=bt(df,s)
 if not a.empty:a.to_csv(T,index=False)
 ys=[]
 for n,start,end in PERIODS:
  x=df.loc[df.index>=start];x=x if not end else x.loc[x.index<end];q=bt(x,s.loc[x.index]);ys.append({'period':n,'entry_events':int(s.loc[x.index].sum()),**_metrics(q)})
 r={'execution':'commission=0; completed 5m bearish marubozu body >=80% range and range >=1 ATR; 2-20 bars later pullback high breaks marubozu high but close returns below it and closes weak; Short next actionable 1m','stage_counts':st,'all_history':{'entry_events':int(s.sum()),**_metrics(a)},'years':ys,'trades_csv':str(T)};O.write_text(json.dumps(r,indent=2),encoding='utf8');logger.info('Failed reclaim audit written to %s',O)
if __name__=='__main__':main()
