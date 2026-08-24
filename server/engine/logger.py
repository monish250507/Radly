import json
import logging
from datetime import datetime
from .config import config

class JsonFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname.lower(),
            "service": config.Service.NAME,
            "env": config.ENV,
            "msg": record.getMessage()
        }
        if hasattr(record, "meta"):
            log_entry.update(record.meta)
        return json.dumps(log_entry)

logger = logging.getLogger("paperblast")
logger.setLevel(logging.INFO if config.IS_PRODUCTION else logging.DEBUG)
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logger.addHandler(handler)

class LoggerProxy:
    @staticmethod
    def _log(level, msg, meta=None):
        extra = {"meta": meta} if meta else {}
        if level == "debug": logger.debug(msg, extra=extra)
        elif level == "info": logger.info(msg, extra=extra)
        elif level == "warn": logger.warning(msg, extra=extra)
        elif level == "error": logger.error(msg, extra=extra)

    @classmethod
    def debug(cls, msg, meta=None): cls._log("debug", msg, meta)
    
    @classmethod
    def info(cls, msg, meta=None): cls._log("info", msg, meta)
    
    @classmethod
    def warn(cls, msg, meta=None): cls._log("warn", msg, meta)
    
    @classmethod
    def error(cls, msg, meta=None): cls._log("error", msg, meta)

paperblast_logger = LoggerProxy()
