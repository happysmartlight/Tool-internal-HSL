"""
services/calculator_service.py
Core import cost calculation logic.

Formula chain:
  FOB (VND) = total_vnd_base
  Import Tax = FOB * import_tax_pct
  VATable amount = FOB + Import Tax
  VAT = VATables * vat_pct
  FX Fee = FOB * fx_conversion_pct
  Customs Fee = customs_fee_vnd * (1 + customs_vat_pct)
  ─────────────────────────────────────────
  Cost (Giá vốn) = FOB + Import Tax + VAT + FX Fee + Customs Fee total
  Selling Price  = Cost / (1 - margin_pct / 100)
  Profit         = Selling Price - Cost
"""
from models.cost_config import CostConfig, CostBreakdown, ExchangeRate, LineItemBreakdown
from models.product import ImportOrder


def calculate(order: ImportOrder, config: CostConfig, rate: ExchangeRate, use_bank_rate: bool = True) -> CostBreakdown:
    """
    Compute a full CostBreakdown for the given order.

    :param order:          The import order with product lines.
    :param config:         Configurable cost parameters (taxes, fees, margin).
    :param rate:           Exchange rate for the order's currency.
    :param use_bank_rate:  If True, use bank_rate; otherwise use market_rate.
    :return:               A populated CostBreakdown dataclass.
    """
    bd = CostBreakdown()
    bd.margin_pct = config.margin_pct
    bd.total_foreign = order.total_foreign

    # Effective exchange rate
    ex_rate = rate.bank_rate if use_bank_rate else rate.market_rate
    bd.total_vnd_base = bd.total_foreign * ex_rate  # FOB in VND
    bd.total_discount_vnd = order.total_discount_foreign * ex_rate

    # Import tax
    bd.import_tax_vnd = bd.total_vnd_base * (config.import_tax_pct / 100)

    # VAT base = FOB + import tax
    vat_base = bd.total_vnd_base + bd.import_tax_vnd
    bd.vat_vnd = vat_base * (config.vat_pct / 100)

    # FX conversion fee (on FOB)
    bd.fx_fee_vnd = bd.total_vnd_base * (config.fx_conversion_pct / 100)

    # Customs fee + its own VAT
    bd.customs_fee_vnd = config.customs_fee_vnd
    bd.customs_fee_vat_vnd = bd.customs_fee_vnd * (config.customs_fee_vat_pct / 100)

    # Other miscellaneous costs (VND, fixed)
    bd.other_costs_vnd = config.other_costs_vnd

    # Total cost (Giá vốn)
    bd.total_cost_vnd = (
        bd.total_vnd_base
        - bd.total_discount_vnd
        + bd.import_tax_vnd
        + bd.vat_vnd
        + bd.fx_fee_vnd
        + bd.customs_fee_vnd
        + bd.customs_fee_vat_vnd
        + bd.other_costs_vnd
    )

    # Selling price & profit
    if config.margin_pct < 100:
        bd.selling_price_vnd = bd.total_cost_vnd / (1 - config.margin_pct / 100)
    else:
        bd.selling_price_vnd = bd.total_cost_vnd * 2  # safe fallback
    bd.profit_vnd = bd.selling_price_vnd - bd.total_cost_vnd

    # ─── Phân bổ chi phí & tính giá bán cho từng sản phẩm ───
    shared_fixed_costs = bd.customs_fee_vnd + bd.customs_fee_vat_vnd + bd.other_costs_vnd

    for line in order.lines:
        line_fob_vnd = line.product.qty * line.product.unit_price_foreign * ex_rate
        
        base_line_total = line.product.qty * line.product.unit_price_foreign
        pct_discount = base_line_total * (line.product.discount_percent_foreign / 100.0)
        line_discount_vnd = (line.product.discount_foreign + pct_discount) * ex_rate

        proportion = (line_fob_vnd / bd.total_vnd_base) if bd.total_vnd_base else 0

        line_import_tax_vnd = line_fob_vnd * (config.import_tax_pct / 100)
        line_vat_vnd = (line_fob_vnd + line_import_tax_vnd) * (config.vat_pct / 100)
        line_fx_fee_vnd = line_fob_vnd * (config.fx_conversion_pct / 100)
        line_shared_costs = shared_fixed_costs * proportion

        line_total_cost = (
            line_fob_vnd
            - line_discount_vnd
            + line_import_tax_vnd
            + line_vat_vnd
            + line_fx_fee_vnd
            + line_shared_costs
        )

        if config.margin_pct < 100:
            line_total_selling_price = line_total_cost / (1 - config.margin_pct / 100)
        else:
            line_total_selling_price = line_total_cost * 2

        qty = line.product.qty if line.product.qty else 1
        bd.line_breakdowns.append(LineItemBreakdown(
            unit_cost_vnd=line_total_cost / qty,
            selling_price_vnd=line_total_selling_price / qty,
            total_cost_vnd=line_total_cost,
            total_selling_price_vnd=line_total_selling_price
        ))

    return bd


def breakdown_to_dict(bd: CostBreakdown) -> dict:
    """Serialize a CostBreakdown to a plain dict (for JSON storage)."""
    return {
        "total_foreign":       bd.total_foreign,
        "total_vnd_base":      bd.total_vnd_base,
        "total_discount_vnd":  bd.total_discount_vnd,
        "import_tax_vnd":      bd.import_tax_vnd,
        "vat_vnd":             bd.vat_vnd,
        "fx_fee_vnd":          bd.fx_fee_vnd,
        "customs_fee_vnd":     bd.customs_fee_vnd,
        "customs_fee_vat_vnd": bd.customs_fee_vat_vnd,
        "other_costs_vnd":     bd.other_costs_vnd,
        "total_cost_vnd":      bd.total_cost_vnd,
        "selling_price_vnd":   bd.selling_price_vnd,
        "profit_vnd":          bd.profit_vnd,
        "margin_pct":          bd.margin_pct,
    }
