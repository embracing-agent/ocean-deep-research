"""湾区中餐馆盈利效率模型。"""

from .params import FORMATS, HOTPOT, MACRO, NOODLE, SICHUAN, VARIANTS, FormatSpec, Macro
from .engine import PnL, profit_and_loss, simulate_day, simulate_table_dynamics, unit_economics

__all__ = [
    "FORMATS", "VARIANTS", "SICHUAN", "NOODLE", "HOTPOT", "MACRO",
    "FormatSpec", "Macro", "PnL",
    "profit_and_loss", "simulate_day", "simulate_table_dynamics", "unit_economics",
]
