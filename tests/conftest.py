import pytest
from ai.resilience import reset_all_circuit_breakers

@pytest.fixture(autouse=True)
def clean_circuit_breaker_state():
    reset_all_circuit_breakers()
    yield
    reset_all_circuit_breakers()
