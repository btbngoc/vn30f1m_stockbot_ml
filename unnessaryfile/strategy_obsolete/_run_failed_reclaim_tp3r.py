import json
from dataclasses import replace
from pathlib import Path
from ..backtest.config import DEFAULT_BACKTEST_CONFIG
from ..backtest.engine import BacktestEngine
from .short_distribution_audit import load_features
from .short_marubozu_failed_reclaim_audit import build,C
from .setup_audit import PERIODS,_metrics
B=Path(__file__).resolve().parents[1];O=B/'models'/'short_marubozu_failed_reclaim_tp3r_audit.json'
def run(d,s):
 x=d[C].copy();x['Signal']=-s.astype(int);return BacktestEngine(x,config=replace(DEFAULT_BACKTEST_CONFIG,take_profit_atr=3.0)).run()
d=load_features();s,st=build(d);a=run(d,s);y=[]
for n,start,end in PERIODS:
 f=d.loc[d.index>=start];f=f if not end else f.loc[f.index<end];q=run(f,s.loc[f.index]);y.append({'period':n,'entry_events':int(s.loc[f.index].sum()),**_metrics(q)})
O.write_text(json.dumps({'execution':'commission=0; same failed-reclaim entry, SL=1ATR and TP=3ATR; no breakeven','stage_counts':st,'all_history':{'entry_events':int(s.sum()),**_metrics(a)},'years':y},indent=2),encoding='utf8')
