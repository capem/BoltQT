"""
Centralized logging module for BoltQT application.

This module provides a unified logging interface for the entire application,
with support for console and file logging, log rotation, and configurable log levels.
"""

import logging
import os
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

# Default log levels
DEFAULT_CONSOLE_LEVEL = logging.INFO
DEFAULT_FILE_LEVEL = logging.DEBUG

# Log format
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Log file settings
MAX_LOG_SIZE = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3  # Keep 3 backup files

# Global logger instance
_logger = None


def get_logger(name: str = "BoltQT") -> logging.Logger:
    """
    Get or create the application logger.
    
    Args:
        name: The logger name (default: "BoltQT")
        
    Returns:
        The configured logger instance
    """
    global _logger
    
    if _logger is None:
        _logger = setup_logger(name)
    
    return _logger


def setup_logger(
    name: str,
    console_level: int = DEFAULT_CONSOLE_LEVEL,
    file_level: int = DEFAULT_FILE_LEVEL,
    log_dir: Optional[str] = None,
    log_filename: Optional[str] = None,
) -> logging.Logger:
    """
    Set up the application logger with console and file handlers.
    
    Args:
        name: The logger name
        console_level: Logging level for console output
        file_level: Logging level for file output
        log_dir: Directory to store log files (default: user's home directory)
        log_filename: Name of the log file (default: "boltqt_{date}.log")
        
    Returns:
        The configured logger instance
    """
    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Capture all logs, handlers will filter
    
    # Clear any existing handlers
    if logger.hasHandlers():
        logger.handlers.clear()
    
    # Create formatters
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # File handler (if enabled)
    if file_level is not None:
        # Determine log directory
        if log_dir is None:
            log_dir = os.path.join(str(Path.home()), "BoltQT", "logs")
        
        # Create log directory if it doesn't exist
        os.makedirs(log_dir, exist_ok=True)
        
        # Determine log filename
        if log_filename is None:
            date_str = datetime.now().strftime("%Y%m%d")
            log_filename = f"boltqt_{date_str}.log"
        
        log_file_path = os.path.join(log_dir, log_filename)
        
        # Create rotating file handler
        file_handler = RotatingFileHandler(
            log_file_path,
            maxBytes=MAX_LOG_SIZE,
            backupCount=BACKUP_COUNT,
            encoding="utf-8",
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Log startup information
    logger.info(f"Logger initialized: {name}")
    logger.info(f"Console logging level: {logging.getLevelName(console_level)}")
    if file_level is not None:
        logger.info(f"File logging level: {logging.getLevelName(file_level)}")
        logger.info(f"Log file: {log_file_path}")
    
    return logger


def update_log_levels(console_level: Optional[int] = None, file_level: Optional[int] = None) -> None:
    """
    Update the logging levels for existing handlers.
    
    Args:
        console_level: New console logging level (None to keep current)
        file_level: New file logging level (None to keep current)
    """
    if _logger is None:
        return
    
    for handler in _logger.handlers:
        if isinstance(handler, logging.StreamHandler) and not isinstance(handler, logging.FileHandler):
            if console_level is not None:
                handler.setLevel(console_level)
                _logger.info(f"Console logging level updated to: {logging.getLevelName(console_level)}")
        elif isinstance(handler, logging.FileHandler):
            if file_level is not None:
                handler.setLevel(file_level)
                _logger.info(f"File logging level updated to: {logging.getLevelName(file_level)}")


# Initialize logger on module import
get_logger()
