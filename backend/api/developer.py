"""Developer API Endpoints.

Provides developer-only capabilities, including:
- Manual CPCB AQI station data ingestion from CSV/XLSX
- Strict column and data validation (station, timestamp, pollutant values)
- Provenance tagging with source='CPCB_MANUAL' and upload/export timestamps
- Deterministic freshness evaluation (LIVE, AGING, STALE, UNAVAILABLE)
"""

import os
import io
import csv
import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
import openpyxl

from backend.db.session import get_db
from backend.db.models import User, AirQualityRecord
from backend.core.security import require_developer_role
from backend.services.weather_reliability import evaluate_weather_freshness, FreshnessClassification

logger = logging.getLogger("weathergpt.api.developer")

router = APIRouter(prefix="/developer", tags=["developer"])


def parse_flexible_timestamp(val: Any) -> Optional[datetime]:
    """Safely parses timestamp from multiple standard formats (ISO 8601, CPCB format, etc.)."""
    if val is None:
        return None
    if isinstance(val, datetime):
        if val.tzinfo is None:
            return val.replace(tzinfo=timezone.utc)
        return val.astimezone(timezone.utc)

    s = str(val).strip()
    if not s:
        return None

    # Handle Z suffix
    s_clean = s.replace("Z", "+00:00")

    common_formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%d",
        "%d-%m-%Y %H:%M:%S",
        "%d/%m/%Y %H:%M:%S",
        "%d-%m-%Y %H:%M",
        "%d/%m/%Y %H:%M",
        "%d-%m-%Y",
        "%d/%m/%Y",
    ]

    for fmt in common_formats:
        try:
            dt = datetime.strptime(s_clean, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass

    try:
        dt = datetime.fromisoformat(s_clean)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def normalize_header(col_name: str) -> str:
    """Normalizes header string for consistent matching."""
    return str(col_name).strip().lower().replace(" ", "_").replace("-", "_").replace(".", "_")


def resolve_column_mappings(headers: List[str]) -> Dict[str, str]:
    """Maps recognized standard keys to actual header names present in the file."""
    normalized = {normalize_header(h): h for h in headers if h is not None}

    # Station column candidates
    station_candidates = [
        "station", "station_name", "stationname", "monitoring_station",
        "station_location", "location", "city", "station_id"
    ]
    station_col = None
    for cand in station_candidates:
        if cand in normalized:
            station_col = normalized[cand]
            break

    # Timestamp column candidates
    timestamp_candidates = [
        "timestamp", "datetime", "date_time", "observed_at",
        "observation_time", "date_and_time", "export_timestamp",
        "observed_timestamp", "date"
    ]
    timestamp_col = None
    for cand in timestamp_candidates:
        if cand in normalized:
            timestamp_col = normalized[cand]
            break

    # Pollutant columns
    pollutant_map = {}
    mappings = {
        "pm2_5": ["pm2_5", "pm25", "pm2_5_ug_m3", "pm2_5_concentrations"],
        "pm10": ["pm10", "pm_10", "pm10_ug_m3", "pm10_concentrations"],
        "no2": ["no2", "nitrogen_dioxide"],
        "so2": ["so2", "sulphur_dioxide", "sulfur_dioxide"],
        "co": ["co", "carbon_monoxide"],
        "o3": ["o3", "ozone"],
        "aqi": ["aqi", "air_quality_index", "cpcb_aqi", "index_value", "us_aqi"]
    }

    for norm_key, orig_col in normalized.items():
        for standard_key, variants in mappings.items():
            if norm_key in variants or norm_key.startswith(standard_key):
                pollutant_map[standard_key] = orig_col
                break

    return {
        "station": station_col,
        "timestamp": timestamp_col,
        "pollutants": pollutant_map
    }


def parse_numeric_pollutant(val: Any, pollutant_name: str, row_num: int) -> Optional[float]:
    """Parses and validates a pollutant concentration value. Rejects non-numeric/negative values."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        if val < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Row {row_num}: Negative value {val} is not valid for pollutant '{pollutant_name}'."
            )
        return float(val)

    s = str(val).strip()
    if not s or s.lower() in ("null", "none", "nan", "-", "na", "n/a"):
        return None

    try:
        f_val = float(s)
        if f_val < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Row {row_num}: Negative value {f_val} is not valid for pollutant '{pollutant_name}'."
            )
        return f_val
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Row {row_num}: Invalid numeric value '{val}' for pollutant '{pollutant_name}'."
        )


@router.post(
    "/aqi/upload",
    summary="Upload Manual CPCB AQI Data (CSV or XLSX)",
    status_code=status.HTTP_200_OK
)
async def upload_manual_cpcb_aqi(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_developer_role)
) -> Dict[str, Any]:
    """Developer-only endpoint to ingest manually exported CPCB AQI station records.
    
    Requirements enforced:
    - Only CSV and XLSX formats accepted
    - Strict column validation: 'station', 'timestamp', and at least one pollutant column
    - Rejects uploads if required columns or fields are missing (no silent guessing)
    - Records tagged with source='CPCB_MANUAL' and actual upload/observation timestamps
    - Evaluates and returns verified data freshness state (LIVE, AGING, STALE, UNAVAILABLE)
    """
    filename = (file.filename or "").lower()
    if not (filename.endswith(".csv") or filename.endswith(".xlsx") or filename.endswith(".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Only .csv and .xlsx files are supported."
        )

    content = await file.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty."
        )

    # 1. Parse rows based on file format
    rows: List[Dict[str, Any]] = []
    headers: List[str] = []

    if filename.endswith(".csv"):
        try:
            text_stream = io.StringIO(content.decode("utf-8-sig"))
            reader = csv.DictReader(text_stream)
            headers = [h.strip() for h in (reader.fieldnames or []) if h]
            for row in reader:
                rows.append(row)
        except UnicodeDecodeError:
            try:
                text_stream = io.StringIO(content.decode("latin-1"))
                reader = csv.DictReader(text_stream)
                headers = [h.strip() for h in (reader.fieldnames or []) if h]
                for row in reader:
                    rows.append(row)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to decode CSV content: {str(e)}"
                )
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse CSV file: {str(e)}"
            )
    else:
        # XLSX parsing using openpyxl
        try:
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True, data_only=True)
            sheet = wb.active
            iter_rows = sheet.iter_rows(values_only=True)
            first_row = next(iter_rows, None)
            if first_row:
                headers = [str(h).strip() for h in first_row if h is not None]
                for r_idx, row_values in enumerate(iter_rows, start=2):
                    # Check if row is completely empty
                    if not any(v is not None and str(v).strip() for v in row_values):
                        continue
                    row_dict = {}
                    for col_idx, h in enumerate(headers):
                        val = row_values[col_idx] if col_idx < len(row_values) else None
                        row_dict[h] = val
                    rows.append(row_dict)
            wb.close()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Failed to parse XLSX file: {str(e)}"
            )

    # 2. Header and Required Column Validation
    if not headers:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File has no header row."
        )

    mappings = resolve_column_mappings(headers)
    station_col = mappings["station"]
    timestamp_col = mappings["timestamp"]
    pollutants_map = mappings["pollutants"]

    if not station_col:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required column: 'station' (or 'station_name'). Available columns: " + ", ".join(headers)
        )

    if not timestamp_col:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required column: 'timestamp' (or 'datetime', 'observed_at'). Available columns: " + ", ".join(headers)
        )

    if not pollutants_map:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing required pollutant columns. File must contain at least one recognized pollutant column (pm2_5, pm10, no2, so2, co, o3, or aqi)."
        )

    if not rows:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File contains headers but zero data rows."
        )

    # 3. Row-by-Row Strict Validation & Model Construction
    now_utc = datetime.now(timezone.utc)
    records_to_insert: List[AirQualityRecord] = []
    stations_seen = set()
    earliest_ts: Optional[datetime] = None
    latest_ts: Optional[datetime] = None

    for i, row in enumerate(rows, start=2):
        # Station validation
        station_val = row.get(station_col)
        if station_val is None or not str(station_val).strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Row {i}: Missing required value for station column '{station_col}'. Empty station values are forbidden."
            )
        station_name = str(station_val).strip()

        # Timestamp validation
        ts_val = row.get(timestamp_col)
        if ts_val is None or (isinstance(ts_val, str) and not ts_val.strip()):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Row {i}: Missing required value for timestamp column '{timestamp_col}'. Empty timestamp values are forbidden."
            )
        parsed_dt = parse_flexible_timestamp(ts_val)
        if parsed_dt is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Row {i}: Unparseable timestamp value '{ts_val}' in column '{timestamp_col}'."
            )

        # Pollutant parsing & verification
        pollutant_values = {}
        has_any_pollutant = False

        for standard_pollutant, col_name in pollutants_map.items():
            val = row.get(col_name)
            parsed_num = parse_numeric_pollutant(val, standard_pollutant, i)
            pollutant_values[standard_pollutant] = parsed_num
            if parsed_num is not None:
                has_any_pollutant = True

        if not has_any_pollutant:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Row {i}: All pollutant fields are empty. At least one valid pollutant reading is required per row."
            )

        # Determine dominant pollutant
        dominant = None
        if pollutant_values.get("pm2_5") is not None and pollutant_values.get("pm10") is not None:
            dominant = "PM2.5" if pollutant_values["pm2_5"] >= (pollutant_values["pm10"] / 2.0) else "PM10"
        elif pollutant_values.get("pm2_5") is not None:
            dominant = "PM2.5"
        elif pollutant_values.get("pm10") is not None:
            dominant = "PM10"
        elif pollutant_values.get("aqi") is not None:
            dominant = "AQI"

        record = AirQualityRecord(
            station=station_name,
            timestamp=parsed_dt,
            source="CPCB_MANUAL",
            uploaded_at=now_utc,
            uploaded_by_id=current_user.id,
            aqi=pollutant_values.get("aqi"),
            pm2_5=pollutant_values.get("pm2_5"),
            pm10=pollutant_values.get("pm10"),
            no2=pollutant_values.get("no2"),
            so2=pollutant_values.get("so2"),
            co=pollutant_values.get("co"),
            o3=pollutant_values.get("o3"),
            dominant_pollutant=dominant,
            raw_payload=json.dumps({k: str(v) for k, v in row.items() if v is not None})
        )
        records_to_insert.append(record)
        stations_seen.add(station_name)

        if earliest_ts is None or parsed_dt < earliest_ts:
            earliest_ts = parsed_dt
        if latest_ts is None or parsed_dt > latest_ts:
            latest_ts = parsed_dt

    # 4. Commit to database
    db.add_all(records_to_insert)
    db.commit()

    # 5. Evaluate overall freshness state for the batch
    batch_freshness = "UNAVAILABLE"
    is_real_time = False
    if latest_ts:
        freshness_enum, age_mins, _ = evaluate_weather_freshness(latest_ts, now_utc)
        # Deterministic freshness labeling:
        # Never label manual data as automatic, live, or real-time unless genuinely recent (<15 min)
        if age_mins < 15 and freshness_enum == FreshnessClassification.FRESH:
            batch_freshness = "LIVE"
            is_real_time = True
        else:
            batch_freshness = freshness_enum.value
            is_real_time = False

    return {
        "success": True,
        "message": f"Successfully ingested {len(records_to_insert)} manual CPCB AQI records across {len(stations_seen)} station(s).",
        "records_ingested": len(records_to_insert),
        "stations": sorted(list(stations_seen)),
        "source": "CPCB_MANUAL",
        "uploaded_at": now_utc.isoformat(),
        "timestamp_range": {
            "earliest": earliest_ts.isoformat() if earliest_ts else None,
            "latest": latest_ts.isoformat() if latest_ts else None
        },
        "freshness_state": batch_freshness,
        "is_real_time": is_real_time,
        "is_manual": True
    }


@router.get(
    "/aqi/records",
    summary="List Ingested Manual CPCB Records",
    status_code=status.HTTP_200_OK
)
def get_manual_cpcb_records(
    station: Optional[str] = Query(None, description="Optional station name filter"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_developer_role)
) -> Dict[str, Any]:
    """Retrieves uploaded CPCB manual records with verified freshness classifications."""
    query = db.query(AirQualityRecord).filter(AirQualityRecord.source == "CPCB_MANUAL")
    if station:
        query = query.filter(AirQualityRecord.station.ilike(f"%{station.strip()}%"))

    records = query.order_by(AirQualityRecord.timestamp.desc()).limit(limit).all()

    now_utc = datetime.now(timezone.utc)
    results = []
    for r in records:
        freshness_enum, age_mins, meta = evaluate_weather_freshness(r.timestamp, r.uploaded_at, current_time=now_utc)
        # Only marked LIVE if observation is genuinely recent (< 15 mins)
        is_recent = (age_mins < 15 and freshness_enum == FreshnessClassification.FRESH)
        freshness_state = "LIVE" if is_recent else freshness_enum.value

        results.append({
            "id": r.id,
            "station": r.station,
            "timestamp": r.timestamp.isoformat(),
            "source": r.source,
            "uploaded_at": r.uploaded_at.isoformat(),
            "aqi": r.aqi,
            "pm2_5": r.pm2_5,
            "pm10": r.pm10,
            "no2": r.no2,
            "so2": r.so2,
            "co": r.co,
            "o3": r.o3,
            "dominant_pollutant": r.dominant_pollutant,
            "observation_age_minutes": age_mins,
            "freshness_state": freshness_state,
            "is_real_time": is_recent,
            "is_manual": True
        })

    return {
        "count": len(results),
        "records": results
    }


@router.get(
    "",
    summary="Developer Dashboard Root",
    response_class=HTMLResponse
)
@router.get(
    "/dashboard",
    summary="Developer Dashboard HTML Page",
    response_class=HTMLResponse
)
def get_developer_dashboard(
    current_user: User = Depends(require_developer_role)
):
    """Developer-only dashboard page. Returns 401 for unauthenticated and 403 for normal users."""
    html_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "developer.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Developer Dashboard</h1>", status_code=200)
