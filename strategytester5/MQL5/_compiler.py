"""
Creates an MQL5 trading robot responsible for simulating all trading operations from a simulator into the MetaTrader5 using MQL5 language
"""

from typing import List, Tuple, Dict
from pathlib import Path

def symbol_resources(symbols: List[str], hist_dir: Path) -> str:

    res = ""
    for symbol in symbols:
        res += f"{hist_dir}\\{symbol}\\orders.dat\n"

    return res
