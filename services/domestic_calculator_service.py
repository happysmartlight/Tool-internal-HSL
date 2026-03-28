"""
services/domestic_calculator_service.py
Core domestic product pricing calculation logic (pure VND, no exchange rates).

Formula per product:
  discount_per_unit  = discount_vnd + (purchase_price * discount_pct / 100)
  allocated_ship     = shipping_per_unit + (shipping_total * proportion / qty)
  allocated_other    = other_per_unit   + (other_fixed   * proportion / qty)
  unit_cost          = purchase_price + allocated_ship + allocated_other - discount_per_unit
  unit_sell_bv       = unit_cost / (1 - margin_pct / 100)
  unit_sell_av       = unit_sell_bv * (1 + vat / 100)
  profit_per_unit    = unit_sell_bv - unit_cost
"""
from models.domestic_product import (
    DomesticOrder, DomesticCostConfig,
    DomesticBreakdown, DomesticLineBreakdown,
)


def calculate(order: DomesticOrder, config: DomesticCostConfig) -> DomesticBreakdown:
    """
    Compute a full DomesticBreakdown for the given order.

    Fixed costs (config.shipping_total_vnd, config.other_fixed_costs_vnd) are
    distributed to each product proportionally by (purchase_price * qty).
    """
    bd = DomesticBreakdown()

    # Total purchase cost base for proportional allocation
    total_purchase_base = sum(
        p.purchase_price_vnd * (p.qty if p.qty > 0 else 1)
        for p in order.products
    )

    for p in order.products:
        qty = p.qty if p.qty > 0 else 1

        # Proportional share for fixed costs (per-unit)
        if total_purchase_base > 0:
            proportion = (p.purchase_price_vnd * qty) / total_purchase_base
        else:
            proportion = 0.0

        allocated_ship_fixed = (config.shipping_total_vnd * proportion) / qty
        allocated_other_fixed = (config.other_fixed_costs_vnd * proportion) / qty

        total_allocated_ship = p.shipping_per_unit_vnd + allocated_ship_fixed
        total_allocated_other = p.other_cost_per_unit_vnd + allocated_other_fixed

        # Discount per unit
        discount_per_unit = p.discount_vnd + (p.purchase_price_vnd * p.discount_pct / 100)

        # Unit cost (Giá vốn / đơn vị)
        unit_cost = (
            p.purchase_price_vnd
            + total_allocated_ship
            + total_allocated_other
            - discount_per_unit
        )
        if unit_cost < 0:
            unit_cost = 0.0

        # Selling price
        margin = p.margin_pct if 0 < p.margin_pct < 100 else config.default_margin_pct
        if margin < 100:
            unit_sell_bv = unit_cost / (1 - margin / 100)
        else:
            unit_sell_bv = unit_cost * 2  # safe fallback

        unit_sell_av = unit_sell_bv * (1 + config.vat_on_sale_pct / 100)
        profit_per_unit = unit_sell_bv - unit_cost

        # Line totals
        line = DomesticLineBreakdown(
            product_name=p.name,
            unit=p.unit,
            qty=qty,
            purchase_price_vnd=p.purchase_price_vnd,
            allocated_ship_vnd=total_allocated_ship,
            allocated_other_vnd=total_allocated_other,
            discount_applied_vnd=discount_per_unit,
            unit_cost_vnd=unit_cost,
            margin_pct_used=margin,
            unit_sell_before_vat_vnd=unit_sell_bv,
            unit_sell_with_vat_vnd=unit_sell_av,
            profit_per_unit_vnd=profit_per_unit,
            total_cost_vnd=unit_cost * qty,
            total_sell_before_vat_vnd=unit_sell_bv * qty,
            total_sell_with_vat_vnd=unit_sell_av * qty,
            total_profit_vnd=profit_per_unit * qty,
        )
        bd.lines.append(line)

    # Aggregate totals
    bd.total_cost_vnd = sum(l.total_cost_vnd for l in bd.lines)
    bd.total_revenue_before_vat = sum(l.total_sell_before_vat_vnd for l in bd.lines)
    bd.total_revenue_with_vat = sum(l.total_sell_with_vat_vnd for l in bd.lines)
    bd.total_profit_vnd = sum(l.total_profit_vnd for l in bd.lines)
    bd.vat_amount_vnd = bd.total_revenue_with_vat - bd.total_revenue_before_vat
    bd.avg_margin_pct = (
        (bd.total_profit_vnd / bd.total_revenue_before_vat * 100)
        if bd.total_revenue_before_vat > 0
        else 0.0
    )

    return bd


def breakdown_to_dict(bd: DomesticBreakdown) -> dict:
    """Serialize a DomesticBreakdown to a plain dict (for JSON storage)."""
    return {
        "total_cost_vnd": bd.total_cost_vnd,
        "total_revenue_before_vat": bd.total_revenue_before_vat,
        "total_revenue_with_vat": bd.total_revenue_with_vat,
        "total_profit_vnd": bd.total_profit_vnd,
        "avg_margin_pct": bd.avg_margin_pct,
        "vat_amount_vnd": bd.vat_amount_vnd,
        "lines": [
            {
                "product_name": l.product_name,
                "unit": l.unit,
                "qty": l.qty,
                "purchase_price_vnd": l.purchase_price_vnd,
                "allocated_ship_vnd": l.allocated_ship_vnd,
                "allocated_other_vnd": l.allocated_other_vnd,
                "discount_applied_vnd": l.discount_applied_vnd,
                "unit_cost_vnd": l.unit_cost_vnd,
                "margin_pct_used": l.margin_pct_used,
                "unit_sell_before_vat_vnd": l.unit_sell_before_vat_vnd,
                "unit_sell_with_vat_vnd": l.unit_sell_with_vat_vnd,
                "profit_per_unit_vnd": l.profit_per_unit_vnd,
                "total_cost_vnd": l.total_cost_vnd,
                "total_sell_before_vat_vnd": l.total_sell_before_vat_vnd,
                "total_sell_with_vat_vnd": l.total_sell_with_vat_vnd,
                "total_profit_vnd": l.total_profit_vnd,
            }
            for l in bd.lines
        ],
    }
