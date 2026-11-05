import json
from pathlib import Path
import pandas as pd
from ..backtest.engine import BacktestEngine
from ..logging_config import logger
from .setup_audit import PERIODS,_event_start,_metrics
from .short_distribution_audit import load_features
B=Path(__file__).resolve().parents[1];O=B/'models'/'short_utad_failed_reclaim_break_raw_audit.json';T=B/'models'/'short_utad_failed_reclaim_break_raw_trades.csv';C=['Open','High','Low','Close','ATR']
def build(df):
 b=df.index.floor('5min');h=df.groupby(b).agg(Open=('Open','first'),High=('High','max'),Low=('Low','min'),Close=('Close','last'),Volume=('Volume','sum'))
 p=h.Close.shift();tr=pd.concat([h.High-h.Low,(h.High-p).abs(),(h.Low-p).abs()],axis=1).max(axis=1);h['ATR']=tr.rolling(14).mean();h['VMA']=h.Volume.rolling(20).mean();h['EMA20']=h.Close.ewm(span=20,adjust=False).mean();h['RH']=h.High.rolling(24).max().shift(1);h['RL']=h.Low.rolling(24).min().shift(1);h['RW']=h.RH-h.RL
 prior_dist=(h.Close.between(h.RL,h.RH)&(h.RW>=2*h.ATR)&(h.RW<=10*h.ATR)&(h.EMA20.diff(12).abs()<=1.5*h.ATR)).shift(1).fillna(False)
 state='';uh=uv=None;age=0;last=None;u=[];f=[];fl=[]
 for ts,r in h.iterrows():
  if last is not None and ts-last>pd.Timedelta(minutes=10):state='';age=0
  rng=max(r.High-r.Low,1e-9);loc=(r.Close-r.Low)/rng;utad=bool(prior_dist.loc[ts] and r.High>r.RH and r.Close<r.RH and loc<=.4 and r.Volume>=1.3*r.VMA);fail=False
  if utad:state='wait';uh=r.High;uv=r.Volume;age=0
  elif state=='wait':
   age+=1
   if 2<=age<=6:fail=bool(r.High>r.RH and r.Close<=r.RH and loc<=.45 and r.Volume<=.75*uv)
   if fail or age>6:state=''
  u.append(int(utad));f.append(int(fail));fl.append(r.Low if fail else float('nan'));last=ts
 low=pd.Series(fl,index=h.index).shift(1);mapped=pd.Series(b,index=df.index).map(low);trigger=_event_start((mapped.notna())&(df.Close<mapped))
 return trigger,{'utad_events':int(_event_start(pd.Series(u,index=h.index)==1).sum()),'failed_reclaims':int(_event_start(pd.Series(f,index=h.index)==1).sum()),'one_minute_breaks':int(trigger.sum())}
def bt(df,s):x=df[C].copy();x['Signal']=-s.astype(int);return BacktestEngine(x).run()
def main():
 df=load_features();s,st=build(df);a=bt(df,s)
 if not a.empty:a.to_csv(T,index=False)
 y=[]
 for n,start,end in PERIODS:
  f=df.loc[df.index>=start];f=f if not end else f.loc[f.index<end];q=bt(f,s.loc[f.index]);y.append({'period':n,'entry_events':int(s.loc[f.index].sum()),**_metrics(q)})
 O.write_text(json.dumps({'execution':'commission=0; completed 5m Distribution -> UTAD -> failed reclaim; Short only when following 1m closes below failed-reclaim low','stage_counts':st,'all_history':{'entry_events':int(s.sum()),**_metrics(a)},'years':y,'trades_csv':str(T)},indent=2),encoding='utf8')
if __name__=='__main__':main()
