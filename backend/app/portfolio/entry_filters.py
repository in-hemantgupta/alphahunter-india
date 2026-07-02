import numpy as np
from app.services.audit_logger import AuditLogger


def get_sma(price_list, period):
    if len(price_list) < period:
        return None
    return float(np.mean(price_list[-period:]))


def compute_volume_ratio(prices, volumes, lookback=20):
    if not volumes or len(volumes) < lookback + 1:
        return None
    current_vol = volumes[-1]
    avg_vol = np.mean(volumes[-(lookback + 1):-1])
    if avg_vol <= 0:
        return None
    return float(current_vol / avg_vol)


def compute_relative_strength(symbol_returns, sector_returns_dict):
    if not sector_returns_dict:
        return 0, 0
    peer_rets = [v for v in sector_returns_dict.values() if v is not None]
    if not peer_rets:
        return 0, 0
    avg_peer = np.mean(peer_rets)
    return float(symbol_returns - avg_peer), len(peer_rets)


def check_entry(symbol, score_rank, price_data, sector,
                volume_ratio=None, relative_strength=None, sector_peer_count=0):
    reasons = []

    if score_rank is None or score_rank >= 50:
        reasons.append("score_rank>=50")
        _log_rejection(symbol, reasons)
        return False, reasons

    prices = [p for p in price_data if p is not None and p > 0] if price_data else []
    if len(prices) < 50:
        reasons.append("insufficient_price_data")
        _log_rejection(symbol, reasons)
        return False, reasons

    current_price = prices[-1]
    sma_50 = get_sma(prices, 50)
    if sma_50 is None:
        reasons.append("no_50dma")
        _log_rejection(symbol, reasons)
        return False, reasons
    if current_price <= sma_50:
        reasons.append("price<=50dma")
        _log_rejection(symbol, reasons)
        return False, reasons

    if volume_ratio is not None and volume_ratio <= 1.0:
        reasons.append(f"vol_ratio={volume_ratio:.2f}<=1.0")
        _log_rejection(symbol, reasons)
        return False, reasons

    if sector and sector != "Unknown" and relative_strength is not None and sector_peer_count >= 3:
        if relative_strength <= 0:
            reasons.append(f"rs<={relative_strength:.4f}")
            _log_rejection(symbol, reasons)
            return False, reasons

    return True, reasons


def _log_rejection(symbol, reasons):
    audit = AuditLogger()
    audit.log("entry_rejected", "portfolio", "INFO", details=f"{symbol}: {','.join(reasons)}", source="entry_filters", symbol=symbol)
    audit.close()
