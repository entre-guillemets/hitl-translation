import logging
import sys
from typing import Optional
from app.core.config import settings

def setup_logging(log_level: Optional[str] = None) -> None:
    """Setup application logging configuration"""
    level = log_level or settings.LOG_LEVEL
    
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Setup console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    
    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))
    root_logger.addHandler(console_handler)
    
    # Setup specific loggers
    loggers = [
        'app',
        'uvicorn',
        'fastapi',
        'prisma'
    ]
    
    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, level.upper()))

def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)
