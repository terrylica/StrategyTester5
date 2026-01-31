from strategytester5 import AccountInfo, SymbolInfo
import json
import os
import logging

ACCOUNT_INFO_FILE = "account_info.json"
SYMBOL_INFO_FILE = "symbol_info.json"

class Importers:
    def __init__(self, broker_path: str, logger: logging.Logger):
        self.broker_path = broker_path
        self.logger = logger

        if not os.path.exists(self.broker_path):
            err = "Broker path does not exist"
            self.logger.error(err)
            raise RuntimeError(err)

    def account_info(self) -> AccountInfo:

        file = os.path.join(self.broker_path, ACCOUNT_INFO_FILE)
        if not os.path.exists(file):
            self.logger.error(f"Failed to import account info, {file} not found")
            return None

        try:
            with open(file) as json_file:
                data = json.load(json_file)
        except Exception as e:
            self.logger.error(e)
            return None

        return AccountInfo(**data["account_info"])

    def all_symbol_info(self) -> tuple:

        file = os.path.join(self.broker_path, ACCOUNT_INFO_FILE)
        if not os.path.exists(file):
            self.logger.error(f"Failed to import account info, {file} not found")
            return None

        try:
            with open(file) as json_file:
                data = json.load(json_file)
        except Exception as e:
            self.logger.error(e)

        all_symbol_info = []

        for s in data["all_symbols_info"]:
            all_symbol_info.append(SymbolInfo(**s))

        return tuple(all_symbol_info)

class Exporters:
    def __init__(self, broker_path: str, logger: logging.Logger):
        self.broker_path = broker_path
        self.logger = logger

        try:
            os.makedirs(self.broker_path, exist_ok=True)
        except Exception as e:
            self.logger.error(f"Failed to create broker path: {e}")
            raise

    def account_info(self, ac_info: AccountInfo | dict) -> bool:

        file = os.path.join(self.broker_path, ACCOUNT_INFO_FILE)

        try:
            payload = {
                "account_info": ac_info._asdict() if hasattr(ac_info, "_asdict") else dict(ac_info),
            }
            with open(file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(e)
            return False

        return True

    def all_symbol_info(self, all_symbol_info: tuple | list) -> bool:

        file = os.path.join(self.broker_path, SYMBOL_INFO_FILE)

        try:
            exported = []
            for s in all_symbol_info:
                exported.append(s._asdict() if hasattr(s, "_asdict") else dict(s))

            payload = {
                "all_symbols_info": exported,
            }
            with open(file, "w", encoding="utf-8") as f:
                json.dump(payload, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.error(e)
            return False

        return True
