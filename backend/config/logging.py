import logging
import sys
from backend.config.settings import settings

def setup_logging():
    """Configures structured operational logging for WeatherGPT backend."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Silence verbose third-party loggers
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    logger = logging.getLogger("weathergpt.backend")
    logger.info(f"Logging initialized at level {settings.LOG_LEVEL} (Env: {settings.ENVIRONMENT})")
    return logger

logger = setup_logging()
