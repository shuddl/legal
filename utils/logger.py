#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Advanced Logging Configuration Module

Provides a robust, configurable logging system for the Construction Lead Scraper.
Supports multiple handlers, log levels, and formatting options.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pathlib import Path
from typing import Optional, Dict, Any, Union
import json

# Default log levels
DEFAULT_CONSOLE_LEVEL = logging.INFO
DEFAULT_FILE_LEVEL = logging.DEBUG

# Environment variable names
ENV_LOG_LEVEL = "LOG_LEVEL"
ENV_LOG_FILE_PATH = "LOG_FILE_PATH"

# Log level mapping
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

# Get the root directory of the project
ROOT_DIR = Path(__file__).parent.parent.absolute()

# Ensure logs directory exists
LOGS_DIR = ROOT_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Global logger registry to avoid duplicate handlers
_loggers: Dict[str, logging.Logger] = {}


class LoggerConfig:
    """Configuration class for logger settings."""

    def __init__(
        self,
        name: str = "app",
        console_level: Optional[Union[int, str]] = None,
        file_level: Optional[Union[int, str]] = None,
        log_file: Optional[str] = None,
        rotating: bool = True,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
        daily_rotation: bool = False,
        format_string: Optional[str] = None,
        json_logs: bool = False,
        propagate: bool = False,
    ):
        """
        Initialize logger configuration.

        Args:
            name: Logger name
            console_level: Console logging level (int or string)
            file_level: File logging level (int or string)
            log_file: Path to log file (None for no file logging)
            rotating: Whether to use rotating file handler
            max_bytes: Maximum file size for rotating handler
            backup_count: Number of backup files to keep
            daily_rotation: Whether to rotate logs daily instead of by size
            format_string: Custom log format string
            json_logs: Whether to format logs as JSON
            propagate: Whether to propagate to parent loggers
        """
        self.name = name
        
        # Get log level from environment or use default
        env_level = os.environ.get(ENV_LOG_LEVEL)
        if env_level:
            try:
                env_level = LOG_LEVELS.get(env_level.upper(), int(env_level))
            except ValueError:
                env_level = None
        
        # Set console level
        if console_level is not None:
            if isinstance(console_level, str):
                self.console_level = LOG_LEVELS.get(console_level.upper(), DEFAULT_CONSOLE_LEVEL)
            else:
                self.console_level = console_level
        elif env_level is not None:
            self.console_level = env_level
        else:
            self.console_level = DEFAULT_CONSOLE_LEVEL
        
        # Set file level
        if file_level is not None:
            if isinstance(file_level, str):
                self.file_level = LOG_LEVELS.get(file_level.upper(), DEFAULT_FILE_LEVEL)
            else:
                self.file_level = file_level
        elif env_level is not None:
            self.file_level = env_level
        else:
            self.file_level = DEFAULT_FILE_LEVEL
        
        # Get log file path from environment or use default
        env_file_path = os.environ.get(ENV_LOG_FILE_PATH)
        if log_file:
            self.log_file = log_file
        elif env_file_path:
            self.log_file = env_file_path
        else:
            self.log_file = str(LOGS_DIR / f"{name}.log")
        
        self.rotating = rotating
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.daily_rotation = daily_rotation
        
        # Use custom format or default
        if format_string:
            self.format_string = format_string
        else:
            self.format_string = "%(asctime)s | %(levelname)s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
        
        self.json_logs = json_logs
        self.propagate = propagate


class JsonFormatter(logging.Formatter):
    """
    Formatter that outputs JSON strings after parsing the log record.
    
    Ensures all log records are converted to a consistent JSON format,
    which is more machine-readable and easier to parse in log aggregation systems.
    """
    
    def __init__(
        self,
        fmt_dict: Optional[Dict[str, Any]] = None,
        time_format: str = "%Y-%m-%d %H:%M:%S",
    ):
        """
        Initialize JSON formatter.
        
        Args:
            fmt_dict: Dictionary to use as base for formatting
            time_format: Format string for timestamps
        """
        super().__init__()
        self.fmt_dict = fmt_dict or {
            "timestamp": "asctime",
            "level": "levelname",
            "name": "name",
            "module": "module",
            "function": "funcName",
            "line": "lineno",
            "message": "message",
        }
        self.time_format = time_format
    
    def format(self, record: logging.LogRecord) -> str:
        """
        Format the specified record as JSON.
        
        Args:
            record: Log record to format
        
        Returns:
            JSON string representation of the log record
        """
        record.asctime = self.formatTime(record, self.time_format)
        
        # Create a dictionary for the log record
        log_record = {}
        for key, value in self.fmt_dict.items():
            if hasattr(record, value):
                log_record[key] = getattr(record, value)
        
        # Add exception info if present
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        
        # Convert to JSON
        return json.dumps(log_record)


def configure_logger(config: LoggerConfig = None) -> logging.Logger:
    """
    Configure a logger with the specified settings.
    
    Args:
        config: Logger configuration (or None for default)
    
    Returns:
        Configured logger
    """
    if config is None:
        config = LoggerConfig()
    
    # Check if logger already exists in registry
    if config.name in _loggers:
        return _loggers[config.name]
    
    # Create logger
    logger = logging.getLogger(config.name)
    logger.setLevel(min(config.console_level, config.file_level))
    logger.propagate = config.propagate
    
    # Clear existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
    
    # Create formatters
    if config.json_logs:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(config.format_string)
    
    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(config.console_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # Create file handler if specified
    if config.log_file:
        os.makedirs(os.path.dirname(os.path.abspath(config.log_file)), exist_ok=True)
        
        if config.daily_rotation:
            # Use time-based rotation
            file_handler = TimedRotatingFileHandler(
                config.log_file,
                when="midnight",
                backupCount=config.backup_count,
                encoding="utf-8"
            )
        elif config.rotating:
            # Use size-based rotation
            file_handler = RotatingFileHandler(
                config.log_file,
                maxBytes=config.max_bytes,
                backupCount=config.backup_count,
                encoding="utf-8"
            )
        else:
            # Use standard file handler
            file_handler = logging.FileHandler(config.log_file, encoding="utf-8")
        
        file_handler.setLevel(config.file_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    
    # Store in registry
    _loggers[config.name] = logger
    
    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger by name, creating it if it doesn't exist.
    
    Args:
        name: Logger name
    
    Returns:
        Logger instance
    """
    if name in _loggers:
        return _loggers[name]
    
    # Create a new logger with default config
    config = LoggerConfig(name=name)
    return configure_logger(config)


def configure_logging(
    level: Optional[Union[int, str]] = None,
    log_file: Optional[str] = None,
    json_logs: bool = False
) -> logging.Logger:
    """
    Configure the root logger.
    
    This is a simplified version of configure_logger for backward compatibility.
    
    Args:
        level: Logging level (int or string)
        log_file: Path to log file
        json_logs: Whether to format logs as JSON
    
    Returns:
        Configured root logger
    """
    config = LoggerConfig(
        name="",  # Root logger
        console_level=level,
        file_level=level,
        log_file=log_file,
        json_logs=json_logs,
    )
    return configure_logger(config)


# Configure a default logger when module is imported
root_logger = configure_logging()


# Specialized logging functions
def log_scraping_event(source: str, event_type: str, message: str, level: int = logging.INFO) -> None:
    """
    Log a scraping event.
    
    Args:
        source: Source being scraped
        event_type: Type of event (start, error, complete, etc.)
        message: Event description
        level: Logging level
    """
    logger = get_logger("scraping")
    logger.log(level, f"[{source}] [{event_type}] {message}")


def log_processing_event(processor: str, event_type: str, message: str, level: int = logging.INFO) -> None:
    """
    Log a processing event.
    
    Args:
        processor: Processor name
        event_type: Type of event (start, error, complete, etc.)
        message: Event description
        level: Logging level
    """
    logger = get_logger("processing")
    logger.log(level, f"[{processor}] [{event_type}] {message}")


def log_integration_event(integration: str, event_type: str, message: str, level: int = logging.INFO) -> None:
    """
    Log an integration event.
    
    Args:
        integration: Integration name
        event_type: Type of event (start, error, complete, etc.)
        message: Event description
        level: Logging level
    """
    logger = get_logger("integration")
    logger.log(level, f"[{integration}] [{event_type}] {message}")


def log_sensitive(logger: logging.Logger, level: int, message: str, **sensitive_data) -> None:
    """
    Log a message while masking sensitive data.
    
    Args:
        logger: Logger to use
        level: Logging level
        message: Message to log
        sensitive_data: Keys and values to mask in the message
    """
    # Mask sensitive data in the message
    masked_message = message
    for key, value in sensitive_data.items():
        if value and isinstance(value, str):
            # Mask all but first and last character
            if len(value) > 6:
                masked = value[0] + "*" * (len(value) - 2) + value[-1]
            else:
                masked = "*" * len(value)
            masked_message = masked_message.replace(value, masked)
    
    # Log the masked message
    logger.log(level, masked_message)