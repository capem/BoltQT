"""Performance profiling utilities for identifying bottlenecks in the application."""

import time
import functools
from typing import Dict, List, Optional, Any, Callable
from contextlib import contextmanager

from .logger import get_logger


class PerformanceProfiler:
    """A utility class for profiling performance of operations."""
    
    def __init__(self):
        self.timings: Dict[str, List[float]] = {}
        self.current_operations: Dict[str, float] = {}
        self.logger = get_logger()
        
    def start_operation(self, operation_name: str) -> None:
        """Start timing an operation."""
        self.current_operations[operation_name] = time.perf_counter()
        self.logger.debug(f"⏱️ Started timing: {operation_name}")
        
    def end_operation(self, operation_name: str) -> float:
        """End timing an operation and return the duration."""
        if operation_name not in self.current_operations:
            self.logger.warning(f"Operation '{operation_name}' was not started")
            return 0.0
            
        start_time = self.current_operations.pop(operation_name)
        duration = time.perf_counter() - start_time
        
        if operation_name not in self.timings:
            self.timings[operation_name] = []
        self.timings[operation_name].append(duration)
        
        self.logger.info(f"⏱️ {operation_name}: {duration:.3f}s")
        return duration
        
    @contextmanager
    def time_operation(self, operation_name: str):
        """Context manager for timing operations."""
        self.start_operation(operation_name)
        try:
            yield
        finally:
            self.end_operation(operation_name)
            
    def get_stats(self, operation_name: str) -> Dict[str, float]:
        """Get statistics for an operation."""
        if operation_name not in self.timings or not self.timings[operation_name]:
            return {}
            
        times = self.timings[operation_name]
        return {
            'count': len(times),
            'total': sum(times),
            'average': sum(times) / len(times),
            'min': min(times),
            'max': max(times),
            'last': times[-1]
        }
        
    def get_all_stats(self) -> Dict[str, Dict[str, float]]:
        """Get statistics for all operations."""
        return {op: self.get_stats(op) for op in self.timings.keys()}
        
    def print_summary(self) -> None:
        """Print a summary of all timing statistics."""
        self.logger.info("=== PERFORMANCE SUMMARY ===")
        for operation_name, stats in self.get_all_stats().items():
            if stats:
                self.logger.info(
                    f"{operation_name}: "
                    f"avg={stats['average']:.3f}s, "
                    f"last={stats['last']:.3f}s, "
                    f"count={stats['count']}, "
                    f"total={stats['total']:.3f}s"
                )
        self.logger.info("=== END PERFORMANCE SUMMARY ===")
        
    def reset(self) -> None:
        """Reset all timing data."""
        self.timings.clear()
        self.current_operations.clear()
        self.logger.debug("Performance profiler reset")


def profile_method(operation_name: Optional[str] = None):
    """Decorator to profile method execution time."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            # Get the profiler from the instance if it exists
            profiler = getattr(self, '_profiler', None)
            if not profiler:
                # Create a profiler if it doesn't exist
                profiler = PerformanceProfiler()
                setattr(self, '_profiler', profiler)
                
            op_name = operation_name or f"{self.__class__.__name__}.{func.__name__}"
            
            with profiler.time_operation(op_name):
                return func(self, *args, **kwargs)
        return wrapper
    return decorator


def profile_function(operation_name: Optional[str] = None):
    """Decorator to profile function execution time."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Use a global profiler for functions
            if not hasattr(wrapper, '_profiler'):
                wrapper._profiler = PerformanceProfiler()
                
            op_name = operation_name or func.__name__
            
            with wrapper._profiler.time_operation(op_name):
                return func(*args, **kwargs)
        return wrapper
    return decorator


# Global profiler instance for easy access
global_profiler = PerformanceProfiler()
