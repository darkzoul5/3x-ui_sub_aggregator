import logging
import logging.handlers
import sys

from settings import LOG_LEVEL


def _resolve_log_level(level_name: str) -> int:
    return getattr(logging, level_name, logging.INFO)


class HealthCheckFilter(logging.Filter):
    """Filter out /health endpoint requests from access logs."""

    def filter(self, record):
        return '/health' not in record.getMessage()


def configure_logging() -> logging.Logger:
    logger_file = logging.handlers.TimedRotatingFileHandler(
        filename="py.log",
        when="midnight",
        interval=3,
        backupCount=5,
    )
    logger_console = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        fmt='[{asctime}] #{levelname:8} {filename}:{lineno} - {message}',
        style='{'
    )
    logger_file.setFormatter(formatter)
    logger_console.setFormatter(formatter)

    logger = logging.getLogger()
    logger.handlers.clear()
    logger.setLevel(_resolve_log_level(LOG_LEVEL))
    logger_file.setLevel(_resolve_log_level(LOG_LEVEL))
    logger_console.setLevel(_resolve_log_level(LOG_LEVEL))
    logger.addHandler(logger_file)
    logger.addHandler(logger_console)

    logging.getLogger("uvicorn.access").addFilter(HealthCheckFilter())
    return logger


logger = configure_logging()
