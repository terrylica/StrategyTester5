MAX_WORKERS = 4
DEFAULT_BROKER_DATA_PATH = "Default-Broker"

DEFAULT_SYMBOL_INFO_JSON = "SymbolInfo.json"
DEFAULT_ACCOUNT_INFO_JSON = "AccountInfo.json"
DEFAULT_TERMINAL_INFO_JSON = "TerminalInfo.json"

SUPPORTED_TESTER_MODELLING = \
    {
        # 0: "Every tick",
        1: "1 minute OHLC",
        2: "Open price only",
        # 3: "Math calculations",
        4: "Every tick based on real ticks"
    }

REQUIRED_TESTER_CONFIG_KEYS = {
            "bot_name",
            "symbols",
            "timeframe",
            "start_date",
            "end_date",
            "modelling",
            "deposit",
            "leverage",
            "visual_mode"
        }

SUPPORTED_TESTER_MODELLING_REVERSE = {
    v.lower(): k for k, v in SUPPORTED_TESTER_MODELLING.items()
}

EXPERTS_FOLDER = "StrategyTester5 PRO"