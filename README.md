### StrategyTester5

StrategyTester is a Python-based backtesting and strategy testing framework built specifically for the MetaTrader5 (MT5) Python API.


### Getting started

Ensure you have the MetaTrader 5 desktop application then proceeed to install the dependencies used in this project in your Python virtual environment

**On Windows:**
```bash
pip install strategytester5["mt5"]
```

**On Linux/MacOS:**

```bash
pip install strategytester5
# optional:
pip install "strategytester5[mt5]"
```
> Note: The MetaTrader5 Python package is primarily distributed for Windows; on Linux/macOS it often requires Wine or a VM depending on user setup. (Your core package can still work without the MT5 bindings if you have offline history / tester-mode.)

### Making your First MetaTrader5 Trading Robot in The Strategy Tester

**Step 1: Initialize the desired MetaTrader 5 terminal right after importing its module, alongside other useful Python modules for this project.**

```python
import logging
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT)  # insert(0) so it wins over other paths

from strategytester5.tester import StrategyTester, MetaTrader5 as mt5
from strategytester5.trade_classes.Trade import CTrade
import json


if not mt5.initialize():
    raise RuntimeError("Failed to initialize mt5.")
```

See examples the examples [https://github.com/MegaJoctan/StrategyTester5/tree/main/examples](https://github.com/MegaJoctan/StrategyTester5/tree/main/examples)

**Step 2: Load configurations from a JSON file. *In this case configs/tester.json file*.**

```python

# Get path to the folder where this script lives
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    with open(os.path.join(BASE_DIR, "tester.json"), 'r', encoding='utf-8') as file: # reading a JSON file
        # Deserialize the file data into a Python object
        tester_configs = json.load(file)
except Exception as e:
    raise RuntimeError(e)
```

**Step 3: Initialize the Tester class, giving it configurations and an initialized MetaTrader 5 instance.**

```python
tester = StrategyTester(tester_config=tester_configs["tester"],
                        mt5_instance=mt5,
                        logging_level=logging.DEBUG,
                        broker_data_dir="ICMarketsSC-Demo") 
```

**Optionally, instantiate the CTrade class to make life much easier.**

```python
m_trade = CTrade(simulator=tester, magic_number=magic_number, filling_type_symbol=symbol, deviation_points=slippage)
```

**Step 4: Write some trading strategy**

```python
# ---------------------- inputs ----------------------------

symbol = "EURUSD"
timeframe = "PERIOD_H1"
magic_number = 10012026
slippage = 100
sl = 1000
tp = 100

# ---------------------------------------------------------

symbol_info = tester.symbol_info(symbol=symbol) # symbol information

def pos_exists(magic: int, type: int) -> bool:

    for position in tester.positions_get():
        if position.type == type and position.magic == magic:
            return True
    
    return False

def on_tick():
    
    tick_info = tester.symbol_info_tick(symbol=symbol)
    
    ask = tick_info.ask
    bid = tick_info.bid
    
    pts = symbol_info.point
    
    if not pos_exists(magic=magic_number, type=mt5.POSITION_TYPE_BUY): # If a position of such kind doesn't exist
        m_trade.buy(volume=0.1, symbol=symbol, price=ask, sl=ask-sl*pts, tp=ask+tp*pts, comment="Tester buy") # we open a buy position
    
    if not pos_exists(magic=magic_number, type=mt5.POSITION_TYPE_SELL): # If a position of such kind doesn't exist
        m_trade.sell(volume=0.1, symbol=symbol, price=bid, sl=bid+sl*pts, tp=bid-tp*pts, comment="Tester sell") # we open a sell position
```

**Step 5: Call the main trading function into action on every tick, similarly to the [OnTick function in MQL5](https://www.mql5.com/en/docs/event_handlers/ontick)**

```python
tester.OnTick(ontick_func=on_tick) # very important!
```
**Step 6: Running your Systems**

On Windows you have two options:
**A: Running your robot(s) in a simulated environment using information stored in custom broker's directory and a specified history folder 'history_dir''**
```bash
python example_bot.py
```

**B: Running your robot(s) in a simulated environment but relying on the MetaTrader5-API for all information and history**
```bash
python example_bot.py --mt5
```
> Note: To run a script/robot in MetaTrader 5 mode, the platform must be installed and initialized before assigned to the StrategyTester class*

**More information about the project**

- [https://www.mql5.com/en/articles/18971](https://www.mql5.com/en/articles/18971)
- [https://www.mql5.com/en/articles/20455](https://www.mql5.com/en/articles/20455)
- [https://www.mql5.com/en/articles/20782](https://www.mql5.com/en/articles/20782)
- [https://www.mql5.com/en/articles/20917](https://www.mql5.com/en/articles/20917)