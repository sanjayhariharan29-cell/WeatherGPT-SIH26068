"""Lightweight Resilience & Fault-Tolerance Module for WeatherGPT.

Provides circuit breaker protection, safe timeout execution, and failure isolation
without heavy external dependencies. Aligned with Phase 16 specs.
"""

import time
import threading
from enum import Enum
from typing import Any, Callable, Dict, Optional
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError


class CircuitState(str, Enum):
    """States for the lightweight circuit breaker."""
    CLOSED = "CLOSED"        # Normal operation: requests pass through
    OPEN = "OPEN"            # Provider failing: fast-fail, bypass execution
    HALF_OPEN = "HALF_OPEN"  # Recovery probe: single attempt allowed to test recovery


class CircuitBreakerOpenError(Exception):
    """Raised when an operation is attempted while the circuit breaker is OPEN."""
    def __init__(self, breaker_name: str, remaining_cooldown: float):
        super().__init__(
            f"Circuit breaker '{breaker_name}' is OPEN. "
            f"Fast-failing. Cooldown remaining: {remaining_cooldown:.1f}s"
        )
        self.breaker_name = breaker_name
        self.remaining_cooldown = remaining_cooldown


class CircuitBreaker:
    """Thread-safe, lightweight circuit breaker with fast-fail and probe recovery."""

    def __init__(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_timeout: float = 30.0
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state = CircuitState.CLOSED
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._last_failure_time: Optional[float] = None
        self._lock = threading.RLock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN and self._last_failure_time:
                elapsed = time.time() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
            return self._state

    @property
    def consecutive_failures(self) -> int:
        with self._lock:
            return self._consecutive_failures

    @property
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def can_execute(self) -> bool:
        """Determines if a request can proceed through the circuit."""
        with self._lock:
            curr = self.state
            if curr == CircuitState.CLOSED:
                return True
            if curr == CircuitState.HALF_OPEN:
                return True
            return False

    def remaining_cooldown(self) -> float:
        """Returns the seconds remaining until half-open recovery probe."""
        with self._lock:
            if self._state != CircuitState.OPEN or not self._last_failure_time:
                return 0.0
            elapsed = time.time() - self._last_failure_time
            return max(0.0, self.recovery_timeout - elapsed)

    def record_success(self) -> None:
        """Records a successful operation and recovers the circuit to CLOSED."""
        with self._lock:
            self._consecutive_successes += 1
            self._consecutive_failures = 0
            if self._state != CircuitState.CLOSED:
                self._state = CircuitState.CLOSED

    def record_failure(self, exc: Optional[Exception] = None) -> None:
        """Records a failed operation and trips the circuit to OPEN if threshold reached."""
        with self._lock:
            self._consecutive_failures += 1
            self._consecutive_successes = 0
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # A probe failed: trip immediately back to OPEN
                self._state = CircuitState.OPEN
            elif self._consecutive_failures >= self.failure_threshold:
                self._state = CircuitState.OPEN

    def reset(self) -> None:
        """Forces circuit breaker back to CLOSED state and clears failure counters."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._consecutive_failures = 0
            self._consecutive_successes = 0
            self._last_failure_time = None

    def trip(self) -> None:
        """Forces circuit breaker into OPEN state (useful for simulations and testing)."""
        with self._lock:
            self._state = CircuitState.OPEN
            self._consecutive_failures = self.failure_threshold
            self._last_failure_time = time.time()

    def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        fallback_func: Optional[Callable[..., Any]] = None,
        timeout_seconds: Optional[float] = None,
        **kwargs: Any
    ) -> Any:
        """Executes the function with circuit breaker check and optional timeout."""
        with self._lock:
            if not self.can_execute():
                rem = self.remaining_cooldown()
                if fallback_func is not None:
                    return fallback_func(*args, **kwargs)
                raise CircuitBreakerOpenError(self.name, rem)

        # Execute call (with timeout if specified)
        try:
            if timeout_seconds and timeout_seconds > 0:
                result = run_with_timeout(func, timeout_seconds, *args, **kwargs)
            else:
                result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure(exc)
            if fallback_func is not None:
                return fallback_func(*args, **kwargs)
            raise


def run_with_timeout(
    func: Callable[..., Any],
    timeout_seconds: float,
    *args: Any,
    **kwargs: Any
) -> Any:
    """Runs a callable in a worker thread and enforces a hard timeout."""
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(func, *args, **kwargs)
        try:
            return future.result(timeout=timeout_seconds)
        except FuturesTimeoutError:
            raise TimeoutError(
                f"Operation timed out after {timeout_seconds:.2f} seconds"
            )


# Global Circuit Breaker Registry
_breakers_lock = threading.RLock()
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 3,
    recovery_timeout: float = 30.0
) -> CircuitBreaker:
    """Returns or creates a named singleton circuit breaker."""
    with _breakers_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout
            )
        return _circuit_breakers[name]


def reset_all_circuit_breakers() -> None:
    """Resets all registered circuit breakers to CLOSED (useful between test runs)."""
    with _breakers_lock:
        for breaker in _circuit_breakers.values():
            breaker.reset()
