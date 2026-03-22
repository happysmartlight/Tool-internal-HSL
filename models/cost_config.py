"""
models/cost_config.py
Configuration models for cost parameters and exchange rates.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List


@dataclass
class CostConfig:
    """All configurable cost parameters for an import calculation."""
    import_tax_pct: float = 15.0         # % thuế nhập khẩu
    vat_pct: float = 10.0               # % VAT
    fx_conversion_pct: float = 3.4       # % phí chuyển đổi ngoại tệ
    customs_fee_vnd: float = 1_500_000   # Lệ phí hải quan (VND)
    customs_fee_vat_pct: float = 10.0    # VAT trên lệ phí HQ
    other_costs_vnd: float = 0.0         # Chi phí phát sinh khác (VND)
    margin_pct: float = 40.0            # % margin lợi nhuận


@dataclass
class ExchangeRate:
    """Exchange rate data for a single currency pair (X -> VND)."""
    currency: str = "USD"
    market_rate: float = 0.0
    bank_rate: float = 0.0              # market * (1 + spread%)
    spread_pct: float = 2.0            # bank spread above market
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    @classmethod
    def from_market(cls, currency: str, market_rate: float, spread_pct: float = 2.0) -> "ExchangeRate":
        bank = market_rate * (1 + spread_pct / 100)
        return cls(currency=currency, market_rate=market_rate, bank_rate=bank, spread_pct=spread_pct)


@dataclass
class CostBreakdown:
    """Result of a full import cost calculation."""
    # Input summary
    total_foreign: float = 0.0
    total_vnd_base: float = 0.0          # Trị giá hàng hoá (VND)
    total_discount_vnd: float = 0.0      # Chiết khấu (VND)

    # Cost components
    import_tax_vnd: float = 0.0
    vat_vnd: float = 0.0
    fx_fee_vnd: float = 0.0
    customs_fee_vnd: float = 0.0
    customs_fee_vat_vnd: float = 0.0
    other_costs_vnd: float = 0.0         # Chi phí phát sinh khác

    # Totals
    total_cost_vnd: float = 0.0          # Giá vốn
    selling_price_vnd: float = 0.0       # Giá bán đề xuất
    profit_vnd: float = 0.0              # Lợi nhuận
    margin_pct: float = 0.0

    line_breakdowns: List["LineItemBreakdown"] = field(default_factory=list)


@dataclass
class LineItemBreakdown:
    """Per-line calculated costs and recommended selling price."""
    unit_cost_vnd: float = 0.0          # Giá vốn / 1 đơn vị
    selling_price_vnd: float = 0.0      # Giá bán đề xuất / 1 đơn vị
    total_cost_vnd: float = 0.0         # Tổng giá vốn của cả line
    total_selling_price_vnd: float = 0.0# Tổng giá bán đề xuất của cả line
