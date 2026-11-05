import json
from dataclasses import replace
from pathlib import Path
from ..backtest.config import DEFAULT_BACKTEST_CONFIG
from ..backtest.engine import BacktestEngine
from .short_distribution_audit import load_features
from .short_marubozu_failed_reclaim_audit import build,C
from .setup_audit import PERIODS,_metrics
B=Path(__file__).resolve().parents[1];O=B/'models'/'short_marubozu_failed_reclaim_breakeven_1r_audit.json';T=B/'models'/'short_marubozu_failed_reclaim_breakeven_1r_trades.csv'
def run(d,s):
 x=d[C].copy();x['Signal']=-s.astype(int);return BacktestEngine(x,config=replace(DEFAULT_BACKTEST_CONFIG,breakeven_trigger_r=1.0)).run()
d=load_features();s,st=build(d);a=run(d,s)
if not a.empty:a.to_csv(T,index=False)
y=[]
for n,start,end in PERIODS:
 f=d.loc[d.index>=start];f=f if not end else f.loc[f.index<end];q=run(f,s.loc[f.index]);y.append({'period':n,'entry_events':int(s.loc[f.index].sum()),**_metrics(q)})
r={'execution':'commission=0; same failed-reclaim entry and TP=2ATR/trailing; stop moves to entry only after completed candle MFE reaches +1R','stage_counts':st,'all_history':{'entry_events':int(s.sum()),**_metrics(a)},'years':y,'trades_csv':str(T)};O.write_text(json.dumps(r,indent=2),encoding='utf8')
