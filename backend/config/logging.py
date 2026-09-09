import logging
import re
import sys
from backend.config.settings import settings

REDACTION_PATTERNS = [
    (re.compile(r'AIzaSy[A-Za-z0-9_-]{33}', re.IGNORECASE), '[REDACTED_GEMINI_KEY]'),
    (re.compile(r'sk-[A-Za-z0-9_-]{20,}', re.IGNORECASE), '[REDACTED_OPENAI_KEY]'),
    (re.compile(r'Bearer\s+[A-Za-z0-9\._-]+', re.IGNORECASE), 'Bearer [REDACTED_TOKEN]'),
    (re.compile(r'(password|token|secret|api_key|access_token)=([^\s&]+)', re.IGNORECASE), r'\1=[REDACTED]'),
    (re.compile(r'("password"|"token"|"secret"|"api_key"|"access_token")\s*:\s*"[^"]+"', re.IGNORECASE), r'\1: "[REDACTED]"'),
]

class RedactFilter(logging.Filter):
    """Logging filter to automatically sanitize passwords, tokens, and API keys from log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str):
            record.msg = self.redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: self.redact(str(v)) if isinstance(v, str) else v for k, v in record.args.items()}
            elif isinstance(record.args, tuple):
                record.args = tuple(self.redact(str(arg)) if isinstance(arg, str) else arg for arg in record.args)
        return True

    @staticmethod
    def redact(text: str) -> str:
        if not text:
            return text
        for pattern, replacement in REDACTION_PATTERNS:
            text = pattern.sub(replacement, text)
        return text

def setup_logging():
    """Configures structured operational logging for WeatherGPT backend with automated redaction."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.addFilter(RedactFilter())

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
        handlers=[stream_handler],
        force=True
    )

    # Silence verbose third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger = logging.getLogger("weathergpt.backend")
    logger.addFilter(RedactFilter())
    logger.info(f"Logging initialized at level {settings.LOG_LEVEL} (Env: {settings.ENVIRONMENT})")
    return logger

logger = setup_logging()
