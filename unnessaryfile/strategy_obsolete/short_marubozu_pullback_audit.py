import json
from pathlib import Path
import pandas as pd
from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import PERIODS, _event_start, _metrics
from .short_distribution_audit import load_features
B=Path(__file__).resolve().parents[1]; O=B/'models'/'short_marubozu_pullback_raw_audit.json'; T=B/'models'/'short_marubozu_pullback_raw_trades.csv'; C=['Open','High','Low','Close','ATR']
def make_signal(df):
 b=df.index.floor('5min'); h=df.groupby(b).agg(Open=('Open','first'),High=('High','max'),Low=('Low','min'),Close=('Close','last'),Volume=('Volume','sum'))
 h['VMA20']=h.Volume.rolling(20).mean(); state=''; hi=vol=None; age=0; last=None; pull=[]; maru=[]
 for ts,r in h.iterrows():
  if last is not None and ts-last>pd.Timedelta(minutes=10): state=''; age=0
  rng=max(r.High-r.Low,1e-9); body=abs(r.Close-r.Open); loc=(r.Close-r.Low)/rng
  m=bool(r.Close<r.Open and body/rng>=.8 and loc<=.2 and r.Volume>r.VMA20)
  p=False
  if m: state='wait'; hi=r.High; vol=r.Volume; age=0
  elif state=='wait':
   age+=1
   if 2<=age<=10: p=bool(r.Close>r.Open and r.Volume<=.75*vol and r.High<=hi)
   if p or age>10: state=''
  maru.append(int(m)); pull.append(int(p)); last=ts
 completed=pd.Series(pull,index=h.index).shift(1).fillna(0).astype(int)
 mapped=pd.Series(b,index=df.index).map(completed).fillna(0).astype(int)
 return _event_start(mapped==1), {'marubozu_down_volume_gt_ma20':int(_event_start(pd.Series(maru,index=h.index)==1).sum()),'low_volume_pullbacks':int(_event_start(pd.Series(pull,index=h.index)==1).sum())}
def bt(df,s):
 x=df[C].copy(); x['Signal']=-s.astype(int); return BacktestEngine(x).run()
def main():
 df=load_features(); s,st=make_signal(df); a=bt(df,s)
 if not a.empty:a.to_csv(T,index=False)
 ys=[]
 for n,start,end in PERIODS:
  f=df.loc[df.index>=start]; f=f if not end else f.loc[f.index<end]; z=bt(f,s.loc[f.index]); ys.append({'period':n,'entry_events':int(s.loc[f.index].sum()),**_metrics(z)})
 r={'execution':'commission=0; completed 5m bearish marubozu (body >=80%, close near low) with volume > previous 20 completed 5m average; 2-10 bars later green pullback volume <=75% marubozu and below its high; Short on next actionable 1m bar','stage_counts':st,'all_history':{'entry_events':int(s.sum()),**_metrics(a)},'years':ys,'trades_csv':str(T)}
 O.write_text(json.dumps(r,indent=2),encoding='utf-8');logger.info('Marubozu audit written to %s',O)
if __name__=='__main__':main()
