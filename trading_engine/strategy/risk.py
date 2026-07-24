import math

class RiskEngine:
    def __init__(self, risk_per_trade=0.01, sl_atr_multiplier=1.5, tp_atr_multiplier=3.0, trailing_sl_atr_multiplier=1.5, point_multiplier=100000):
        self.risk_per_trade = risk_per_trade
        self.sl_atr_multiplier = sl_atr_multiplier
        self.tp_atr_multiplier = tp_atr_multiplier
        self.trailing_sl_atr_multiplier = trailing_sl_atr_multiplier
        self.point_multiplier = point_multiplier

    def calculate_trade_parameters(self, entry_price: float, atr: float, position_type: int, equity: float) -> dict:
        """
        Calculate Position Size, Stop Loss, and Take Profit.
        position_type: 1 for Long, -1 for Short
        """
        if position_type == 1:
            sl_price = entry_price - (atr * self.sl_atr_multiplier)
            tp_price = entry_price + (atr * self.tp_atr_multiplier)
            trailing_offset = atr * self.trailing_sl_atr_multiplier
        elif position_type == -1:
            sl_price = entry_price + (atr * self.sl_atr_multiplier)
            tp_price = entry_price - (atr * self.tp_atr_multiplier)
            trailing_offset = atr * self.trailing_sl_atr_multiplier
        else:
            return {}

        # Position Sizing
        risk_amount = equity * self.risk_per_trade
        distance_to_sl = abs(entry_price - sl_price)
        
        if distance_to_sl == 0:
            contracts = 1
        else:
            value_at_risk_per_contract = distance_to_sl * self.point_multiplier
            # Floor the number of contracts
            contracts = math.floor(risk_amount / value_at_risk_per_contract)
            
        # Ensure at least 1 contract if equity allows (for testing purposes, we can allow fractional or just max(1))
        # VN30F1 requires integer contracts.
        if contracts < 1:
            contracts = 1
            
        return {
            'contracts': contracts,
            'initial_sl': sl_price,
            'tp_price': tp_price,
            'trailing_offset': trailing_offset
        }
