"""
models/product.py
Dataclasses for product/order line items.
"""
from dataclasses import dataclass, field
from typing import List


@dataclass
class Product:
    """Represents a single product in an import order."""
    name: str = ""
    qty: float = 1.0
    unit_price_foreign: float = 0.0
    currency: str = "USD"

    @property
    def total_foreign(self) -> float:
        return self.qty * self.unit_price_foreign


@dataclass
class OrderLine:
    """A product with computed VND values after exchange rate applied."""
    product: Product
    exchange_rate: float = 0.0  # VND per 1 unit of currency

    @property
    def total_foreign(self) -> float:
        return self.product.total_foreign

    @property
    def total_vnd(self) -> float:
        return self.total_foreign * self.exchange_rate


@dataclass
class ImportOrder:
    """A full import order with multiple products."""
    lines: List[OrderLine] = field(default_factory=list)
    currency: str = "USD"

    @property
    def total_foreign(self) -> float:
        return sum(l.total_foreign for l in self.lines)

    @property
    def total_vnd(self) -> float:
        return sum(l.total_vnd for l in self.lines)
