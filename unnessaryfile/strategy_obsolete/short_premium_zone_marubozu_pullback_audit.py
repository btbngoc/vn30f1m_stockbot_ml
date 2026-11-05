"""Raw audit: premium 30-bar zone -> high-volume bearish marubozu -> weak pullback."""
import json
from pathlib import Path
import pandas as pd
from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import PERIODS,_event_start,_metrics
from .short_distribution_audit import load_features
B=Path(__file__).resolve().parents[1];O=B/'models'/'short_premium_zone_marubozu_pullback_raw_audit.json';T=B/'models'/'short_premium_zone_marubozu_pullback_raw_trades.csv';COL=['Open','High','Low','Close','ATR']
def sig(df):
 b=df.index.floor('5min');h=df.groupby(b).agg(Open=('Open','first'),High=('High','max'),Low=('Low','min'),Close=('Close','last'),Volume=('Volume','sum'))
 p=h.Close.shift();tr=pd.concat([h.High-h.Low,(h.High-p).abs(),(h.Low-p).abs()],axis=1).max(axis=1);h['ATR']=tr.rolling(14).mean();h['EMA20']=h.Close.ewm(span=20,adjust=False).mean();h['PriorVMA20']=h.Volume.rolling(20).mean().shift(1);h['PriorZoneMean']=h.Close.rolling(30).mean().shift(1);h['PriorEMA20']=h.EMA20.shift(1);h['PriorATR']=h.ATR.shift(1)
 state='';hi=vol=None;age=0;last=None;ms=[];ps=[];zones=[]
 for ts,r in h.iterrows():
  if last is not None and ts-last>pd.Timedelta(minutes=10):state='';age=0
  zone=bool(pd.notna(r.PriorATR) and r.PriorZoneMean>=r.PriorEMA20+r.PriorATR)
  rng=max(r.High-r.Low,1e-9);m=bool(zone and r.Close<r.Open and abs(r.Close-r.Open)/rng>=.8 and (r.Close-r.Low)/rng<=.2 and r.Volume>r.PriorVMA20)
  q=False
  if m:state='wait';hi=r.High;vol=r.Volume;age=0
  elif state=='wait':
   age+=1
   if 2<=age<=10:q=bool(r.Close>r.Open and r.Volume<=.75*vol and r.High<=hi)
   if q or age>10:state=''
  zones.append(int(zone));ms.append(int(m));ps.append(int(q));last=ts
 done=pd.Series(ps,index=h.index).shift(1).fillna(0).astype(int);mapped=pd.Series(b,index=df.index).map(done).fillna(0).astype(int)
 return _event_start(mapped==1),{'premium_30_bar_zones':int(_event_start(pd.Series(zones,index=h.index)==1).sum()),'premium_zone_marubozus':int(_event_start(pd.Series(ms,index=h.index)==1).sum()),'weak_pullbacks':int(_event_start(pd.Series(ps,index=h.index)==1).sum())}
def bt(df,s):
 x=df[COL].copy();x['Signal']=-s.astype(int);return BacktestEngine(x).run()
def main():
 df=load_features();s,stage=sig(df);a=bt(df,s)
 if not a.empty:a.to_csv(T,index=False)
 ys=[]
 for n,start,end in PERIODS:
  f=df.loc[df.index>=start];f=f if not end else f.loc[f.index<end];z=bt(f,s.loc[f.index]);ys.append({'period':n,'entry_events':int(s.loc[f.index].sum()),**_metrics(z)})
 r={'execution':'commission=0; prior completed 30-bar 5m zone mean >= prior EMA20 + 1 ATR; bearish marubozu volume > prior 20 completed 5m volume average; 2-10 bar green weak-volume pullback below marubozu high; Short next actionable 1m bar','stage_counts':stage,'all_history':{'entry_events':int(s.sum()),**_metrics(a)},'years':ys,'trades_csv':str(T)};O.write_text(json.dumps(r,indent=2),encoding='utf8');logger.info('Premium-zone Marubozu audit written to %s',O)
if __name__=='__main__':main()
