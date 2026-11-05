"""AmiX (DNSE / Entrade X) REST API Client.

Interfaces with the local AmiX bridge listening on http://localhost:7979
to place derivative orders for VN30F1M.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
import requests

from .order_types import OrderResult

logger = logging.getLogger("AmiXClient")


class AmiXClient:
    """Client for local AmiX bridge (DNSE broker automation)."""

    def __init__(
        self,
        base_url: str = "http://localhost:7979",
        account: str = "",
        loan_id: str = "2403",
        default_symbol: str = "VN30F1M",
        default_volume: int = 1,
        price_mode: str = "MTL",  # "MTL" or "LO"
        dry_run: bool = False,
        timeout: float = 3.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.account = account
        self.loan_id = loan_id
        self.default_symbol = default_symbol
        self.default_volume = default_volume
        self.price_mode = price_mode
        self.dry_run = dry_run
        self.timeout = timeout

    def health_check(self) -> Dict[str, Any]:
        """Check if AmiX local server is responsive."""
        if self.dry_run:
            return {"status": "OK", "mode": "DRY_RUN", "connected": True}
        try:
            resp = requests.get(f"{self.base_url}/", timeout=self.timeout)
            return {
                "status": "OK",
                "connected": True,
                "status_code": resp.status_code,
                "response": resp.text[:120],
            }
        except requests.exceptions.RequestException as e:
            return {
                "status": "UNAVAILABLE",
                "connected": False,
                "error": str(e),
                "hint": "Ensure AmiX software is open and running on localhost:7979",
            }

    def send_order(
        self,
        side: str,  # "NB" (Net Buy / Long) or "NS" (Net Sell / Short)
        symbol: Optional[str] = None,
        price: Optional[str | float] = None,
        volume: Optional[int] = None,
        account: Optional[str] = None,
        loan_id: Optional[str] = None,
    ) -> OrderResult:
        """Send an order to AmiX."""
        symbol = symbol or self.default_symbol
        volume = volume or self.default_volume
        account = account or self.account
        loan_id = loan_id or self.loan_id

        # Determine price string: MTL for market order or float string for LO
        if self.price_mode == "MTL" or price is None or price == "MTL":
            price_str = "MTL"
        else:
            price_str = f"{float(price):.1f}"

        action_name = "BUY_LONG" if side == "NB" else "SELL_SHORT"

        if self.dry_run:
            logger.info(
                "[DRY_RUN] AmiX simulated order: %s %d %s @ %s (Account: %s, Loan: %s)",
                action_name, volume, symbol, price_str, account, loan_id
            )
            return OrderResult(
                success=True,
                status="SENT",
                action=action_name,
                symbol=symbol,
                price=price_str,
                volume=volume,
                message=f"DRY RUN simulated {action_name} executed successfully",
                order_id=f"MOCK-{side}-{volume}",
            )

        url = f"{self.base_url}/trade"
        params = {
            "side": side,
            "symbol": symbol,
            "price": price_str,
            "volume": volume,
        }
        if account:
            params["account"] = account
        if loan_id:
            params["loan"] = loan_id

        try:
            logger.info("Sending AmiX order: GET %s with params %s", url, params)
            resp = requests.get(url, params=params, timeout=self.timeout)
            success = resp.status_code in [200, 201, 202]
            return OrderResult(
                success=success,
                status="SENT" if success else "REJECTED",
                action=action_name,
                symbol=symbol,
                price=price_str,
                volume=volume,
                message=resp.text[:200],
                order_id=str(resp.status_code),
            )
        except requests.exceptions.RequestException as e:
            logger.error("Failed to communicate with AmiX on %s: %s", url, e)
            return OrderResult(
                success=False,
                status="ERROR",
                action=action_name,
                symbol=symbol,
                price=price_str,
                volume=volume,
                message=f"AmiX Connection Error: {e}",
            )

    def close_all_deals(self, all_account: bool = False) -> OrderResult:
        """Close all open deals/positions immediately."""
        if self.dry_run:
            logger.info("[DRY_RUN] AmiX simulated CLOSE ALL DEALS (all_account=%s)", all_account)
            return OrderResult(
                success=True,
                status="SENT",
                action="CLOSE_ALL",
                symbol=self.default_symbol,
                price="MTL",
                volume=0,
                message="DRY RUN simulated close all deals executed",
            )

        url = f"{self.base_url}/closedeals"
        params = {"all_account": "true" if all_account else "false"}
        try:
            logger.info("Closing all deals via AmiX: GET %s", url)
            resp = requests.get(url, params=params, timeout=self.timeout)
            success = resp.status_code in [200, 201, 202]
            return OrderResult(
                success=success,
                status="SENT" if success else "REJECTED",
                action="CLOSE_ALL",
                symbol=self.default_symbol,
                price="MTL",
                volume=0,
                message=resp.text[:200],
            )
        except requests.exceptions.RequestException as e:
            logger.error("Failed to close deals via AmiX: %s", e)
            return OrderResult(
                success=False,
                status="ERROR",
                action="CLOSE_ALL",
                symbol=self.default_symbol,
                price="MTL",
                volume=0,
                message=f"AmiX Close Error: {e}",
            )

    def cancel_all_orders(self, all_account: bool = True) -> OrderResult:
        """Cancel all pending orders in queue."""
        if self.dry_run:
            return OrderResult(
                success=True,
                status="SENT",
                action="CANCEL_ALL",
                symbol=self.default_symbol,
                price="N/A",
                volume=0,
                message="DRY RUN simulated cancel all orders",
            )

        url = f"{self.base_url}/closeorders"
        params = {"all_account": "true" if all_account else "false"}
        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            return OrderResult(
                success=resp.status_code in [200, 201, 202],
                status="SENT",
                action="CANCEL_ALL",
                symbol=self.default_symbol,
                price="N/A",
                volume=0,
                message=resp.text[:200],
            )
        except requests.exceptions.RequestException as e:
            return OrderResult(
                success=False,
                status="ERROR",
                action="CANCEL_ALL",
                symbol=self.default_symbol,
                price="N/A",
                volume=0,
                message=str(e),
            )
