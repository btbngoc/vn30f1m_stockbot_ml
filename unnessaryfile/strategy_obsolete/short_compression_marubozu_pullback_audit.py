import json
from pathlib import Path
import pandas as pd
from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import PERIODS,_event_start,_metrics
from .short_distribution_audit import load_features
B=Path(__file__).resolve().parents[1];O=B/'models'/'short_compression_marubozu_pullback_raw_audit.json';T=B/'models'/'short_compression_marubozu_pullback_raw_trades.csv';C=['Open','High','Low','Close','ATR']
def signal(df):
 b=df.index.floor('5min');h=df.groupby(b).agg(Open=('Open','first'),High=('High','max'),Low=('Low','min'),Close=('Close','last'),Volume=('Volume','sum'))
 p=h.Close.shift();tr=pd.concat([h.High-h.Low,(h.High-p).abs(),(h.Low-p).abs()],axis=1).max(axis=1);h['ATR']=tr.rolling(14).mean();h['VMA']=h.Volume.rolling(20).mean().shift(1);h['RH']=h.High.rolling(20).max().shift(1);h['RL']=h.Low.rolling(20).min().shift(1);h['PA']=h.ATR.shift(1)
 state='';hi=vol=None;age=0;last=None;base=[];mar=[];pull=[]
 for ts,r in h.iterrows():
  if last is not None and ts-last>pd.Timedelta(minutes=10):state='';age=0
  zone=bool(pd.notna(r.PA) and 1.5*r.PA <= r.RH-r.RL <= 4*r.PA)
  rng=max(r.High-r.Low,1e-9);m=bool(zone and r.Close<r.Open and abs(r.Close-r.Open)/rng>=.8 and (r.Close-r.Low)/rng<=.2 and r.Volume>r.VMA)
  q=False
  if m:state='wait';hi=r.High;vol=r.Volume;age=0
  elif state=='wait':
   age+=1
   if 2<=age<=10:q=bool(r.Close>r.Open and r.Volume<=.75*vol and r.High<=hi)
   if q or age>10:state=''
  base.append(int(zone));mar.append(int(m));pull.append(int(q));last=ts
 done=pd.Series(pull,index=h.index).shift(1).fillna(0).astype(int);mapped=pd.Series(b,index=df.index).map(done).fillna(0).astype(int)
 return _event_start(mapped==1),{'compression_20_bar_zones':int(_event_start(pd.Series(base,index=h.index)==1).sum()),'compression_marubozus':int(_event_start(pd.Series(mar,index=h.index)==1).sum()),'weak_pullbacks':int(_event_start(pd.Series(pull,index=h.index)==1).sum())}
def bt(df,s):
 x=df[C].copy();x['Signal']=-s.astype(int);return BacktestEngine(x).run()
def main():
 df=load_features();s,stage=signal(df);a=bt(df,s)
 if not a.empty:a.to_csv(T,index=False)
 ys=[]
 for n,start,end in PERIODS:
  f=df.loc[df.index>=start];f=f if not end else f.loc[f.index<end];z=bt(f,s.loc[f.index]);ys.append({'period':n,'entry_events':int(s.loc[f.index].sum()),**_metrics(z)})
 r={'execution':'commission=0; prior completed 20-bar 5m base width 1.5-4 ATR; bearish marubozu volume > prior 20 completed 5m volume average; 2-10 bar green pullback <=75% marubozu volume and below marubozu high; Short next actionable 1m bar','stage_counts':stage,'all_history':{'entry_events':int(s.sum()),**_metrics(a)},'years':ys,'trades_csv':str(T)};O.write_text(json.dumps(r,indent=2),encoding='utf8');logger.info('Compression Marubozu audit written to %s',O)
if __name__=='__main__':main()
