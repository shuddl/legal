"""Timeout utility for the Perera Lead Scraper.

This module provides a timeout decorator that can be used to limit the execution time
of functions and methods.
"""

import functools
import signal
from typing import Any, Callable, TypeVar, cast, Optional

T = TypeVar('T')

class TimeoutError(Exception):
    """Exception raised when a function execution times out."""
    pass

def timeout_handler(timeout_sec: int) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that raises a TimeoutError if a function takes longer than timeout_sec seconds to execute.
    
    Args:
        timeout_sec: Maximum execution time in seconds
        
    Returns:
        Decorated function that will raise TimeoutError if execution exceeds timeout_sec
        
    Example:
        @timeout_handler(timeout_sec=5)
        def long_running_function():
            # Function that might take too long
            pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            def handle_timeout(signum: int, frame: Optional[Any]) -> None:
                raise TimeoutError(f"Function {func.__name__} timed out after {timeout_sec} seconds")
            
            # Set the timeout handler
            original_handler = signal.signal(signal.SIGALRM, handle_timeout)
            signal.alarm(timeout_sec)
            
            try:
                result = func(*args, **kwargs)
            finally:
                # Reset the alarm and restore the original handler
                signal.alarm(0)
                signal.signal(signal.SIGALRM, original_handler)
                
            return result
        return cast(Callable[..., T], wrapper)
    return decorator