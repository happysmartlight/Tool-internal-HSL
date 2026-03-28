"""
models/domestic_product.py
Data models for domestic (VND-only) product pricing.
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class DomesticProduct:
    """A single domestic product to be priced."""
    name: str = ""
    unit: str = "cái"
    qty: float = 1.0
    purchase_price_vnd: float = 0.0       # Giá mua vào (VND/đơn vị)
    shipping_per_unit_vnd: float = 0.0    # Phí vận chuyển / đơn vị
    other_cost_per_unit_vnd: float = 0.0  # Chi phí khác / đơn vị
    discount_pct: float = 0.0             # Chiết khấu %
    discount_vnd: float = 0.0             # Chiết khấu số tiền VND / đơn vị
    margin_pct: float = 40.0              # Biên lợi nhuận % (per-product override)


@dataclass
class DomesticOrder:
    """An order containing one or more domestic products."""
    products: List[DomesticProduct] = field(default_factory=list)


@dataclass
class DomesticCostConfig:
    """Global cost configuration for a domestic pricing session."""
    vat_on_sale_pct: float = 10.0          # % VAT trên giá bán
    shipping_total_vnd: float = 0.0        # Phí vận chuyển tổng đơn hàng (phân bổ)
    other_fixed_costs_vnd: float = 0.0     # Chi phí cố định khác (phân bổ)
    default_margin_pct: float = 40.0       # Biên lợi nhuận mặc định


@dataclass
class DomesticLineBreakdown:
    """Per-product calculation results."""
    product_name: str = ""
    unit: str = "cái"
    qty: float = 1.0
    purchase_price_vnd: float = 0.0        # Giá mua / đơn vị
    allocated_ship_vnd: float = 0.0        # Ship (per-unit + allocated share)
    allocated_other_vnd: float = 0.0       # CP khác (per-unit + allocated share)
    discount_applied_vnd: float = 0.0      # Chiết khấu áp dụng / đơn vị
    unit_cost_vnd: float = 0.0             # Giá vốn / đơn vị
    margin_pct_used: float = 0.0
    unit_sell_before_vat_vnd: float = 0.0  # Giá bán chưa VAT / đơn vị
    unit_sell_with_vat_vnd: float = 0.0    # Giá bán có VAT / đơn vị
    profit_per_unit_vnd: float = 0.0
    total_cost_vnd: float = 0.0
    total_sell_before_vat_vnd: float = 0.0
    total_sell_with_vat_vnd: float = 0.0
    total_profit_vnd: float = 0.0


@dataclass
class DomesticBreakdown:
    """Full result of a domestic pricing calculation."""
    lines: List[DomesticLineBreakdown] = field(default_factory=list)
    total_cost_vnd: float = 0.0
    total_revenue_before_vat: float = 0.0
    total_revenue_with_vat: float = 0.0
    total_profit_vnd: float = 0.0
    avg_margin_pct: float = 0.0
    vat_amount_vnd: float = 0.0
