"""Data Freshness Evaluation for WeatherGPT.

Evaluates observation and retrieval timestamps according to
docs/01_PS_REQUIREMENTS.md and docs/09_AI_Design.md.
"""

from datetime import datetime, timezone
from typing import Optional, Tuple
from ai.models import FreshnessStatusEnum


def check_data_freshness(timestamp: datetime, current_time: Optional[datetime] = None) -> Tuple[FreshnessStatusEnum, int]:
    """Calculates freshness status and elapsed minutes from the provided timestamp."""
    # Ensure tz-aware or tz-naive alignment
    if current_time is None:
        current_time = datetime.now(timezone.utc) if timestamp.tzinfo else datetime.utcnow()
    elif timestamp.tzinfo and not current_time.tzinfo:
        current_time = current_time.replace(tzinfo=timezone.utc)
    elif not timestamp.tzinfo and current_time.tzinfo:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    delta = current_time - timestamp
    elapsed_minutes = max(0, int(delta.total_seconds() / 60))

    if elapsed_minutes < 60:
        return FreshnessStatusEnum.FRESH, elapsed_minutes
    elif elapsed_minutes <= 180:
        return FreshnessStatusEnum.ACCEPTABLE, elapsed_minutes
    else:
        return FreshnessStatusEnum.STALE, elapsed_minutes
