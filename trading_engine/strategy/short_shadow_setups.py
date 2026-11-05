"""Pre-registered Short candidates for research and shadow paper trading."""

import pandas as pd

from .setup_audit import _event_start
from .short_distribution_audit import one_minute_reject
from .short_lpsy_timing_audit import lpsy_break_confirm, lpsy_break_retest_fail


def build_short_shadow_setups(features: pd.DataFrame) -> dict[str, pd.Series]:
    """Return fixed Short candidates.  No model, fitted threshold or selection."""
    required = ["HTF_15m_TrendDownOK", "HTF_5m_LPSY", "HTF_5m_SOW"]
    missing = [column for column in required if column not in features.columns]
    if missing:
        raise ValueError(f"Missing Short state-machine fields: {missing}")
    downtrend = features["HTF_15m_TrendDownOK"] == 1
    lpsy = _event_start((features["HTF_5m_LPSY"] == 1) & downtrend)
    sow = _event_start((features["HTF_5m_SOW"] == 1) & downtrend)
    return {
        "LPSY_BREAK_CONFIRM": lpsy_break_confirm(lpsy, features),
        # 30 minutes is pre-registered from the behavior audit, which found a
        # failed retest at minute 31; it is not selected from PnL.
        "LPSY_BREAK_RETEST_30M": lpsy_break_retest_fail(lpsy, features, retest_window=30),
        "SOW_BREAK_PULLBACK_REJECT": one_minute_reject(sow, features),
    }
