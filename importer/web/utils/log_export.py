"""Log export utilities for OTLP JSON and human-readable .log formats.

Provides functions to export logs from TerminalOutput or raw text in:
- OTLP JSON format (OpenTelemetry Protocol for logs)
- Human-readable .log format (timestamp + level + message)
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from importer.web.components.terminal_output import LogMessage, LogLevel


# OTLP Severity Number mapping (per OpenTelemetry spec)
# https://opentelemetry.io/docs/specs/otel/logs/data-model/#field-severitynumber
SEVERITY_NUMBER = {
    "debug": 5,     # DEBUG
    "info": 9,      # INFO
    "success": 9,   # INFO (success is a variant of info)
    "warning": 13,  # WARN
    "error": 17,    # ERROR
}

SEVERITY_TEXT = {
    "debug": "DEBUG",
    "info": "INFO",
    "success": "INFO",
    "warning": "WARN",
    "error": "ERROR",
}


def _datetime_to_unix_nano(dt: datetime) -> int:
    """Convert datetime to Unix nanoseconds."""
    return int(dt.timestamp() * 1_000_000_000)


def messages_to_otlp_json(
    messages: list["LogMessage"],
    service_name: str = "dbt-cloud-importer",
    operation_name: str = "terraform",
) -> str:
    """Convert TerminalOutput messages to OTLP JSON format.

    Args:
        messages: List of LogMessage objects from TerminalOutput
        service_name: Service name for the resource attribute
        operation_name: Operation name (e.g., "terraform-plan", "terraform-apply")

    Returns:
        OTLP JSON string conforming to the OpenTelemetry logs data model
    """
    log_records = []

    for msg in messages:
        level_str = msg.level.value if hasattr(msg.level, "value") else str(msg.level)
        timestamp_ns = _datetime_to_unix_nano(msg.timestamp) if msg.timestamp else _datetime_to_unix_nano(datetime.now(timezone.utc))

        log_record = {
            "timeUnixNano": str(timestamp_ns),
            "observedTimeUnixNano": str(timestamp_ns),
            "severityNumber": SEVERITY_NUMBER.get(level_str, 9),
            "severityText": SEVERITY_TEXT.get(level_str, "INFO"),
            "body": {
                "stringValue": msg.text
            },
            "attributes": [],
        }
        log_records.append(log_record)

    otlp_payload = {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": [
                        {
                            "key": "service.name",
                            "value": {"stringValue": service_name}
                        },
                        {
                            "key": "operation.name",
                            "value": {"stringValue": operation_name}
                        }
                    ]
                },
                "scopeLogs": [
                    {
                        "scope": {
                            "name": "dbt-cloud-importer.web",
                            "version": "1.0.0"
                        },
                        "logRecords": log_records
                    }
                ]
            }
        ]
    }

    return json.dumps(otlp_payload, indent=2)


def messages_to_log_text(
    messages: list["LogMessage"],
    include_timestamps: bool = True,
) -> str:
    """Convert TerminalOutput messages to human-readable .log format.

    Args:
        messages: List of LogMessage objects from TerminalOutput
        include_timestamps: Whether to include timestamps in output

    Returns:
        Human-readable log text
    """
    lines = []

    for msg in messages:
        level_str = msg.level.value if hasattr(msg.level, "value") else str(msg.level)
        level_label = SEVERITY_TEXT.get(level_str, "INFO")

        if include_timestamps and msg.timestamp:
            timestamp_str = msg.timestamp.strftime("%Y-%m-%dT%H:%M:%S%z")
            lines.append(f"[{timestamp_str}] [{level_label:7}] {msg.text}")
        else:
            lines.append(f"[{level_label:7}] {msg.text}")

    return "\n".join(lines)


def text_to_otlp_json(
    text: str,
    service_name: str = "dbt-cloud-importer",
    operation_name: str = "terraform",
) -> str:
    """Convert raw text output to OTLP JSON format.

    Infers severity from line content (e.g., "Error:", "Warning:").

    Args:
        text: Raw text output (e.g., terraform plan output)
        service_name: Service name for the resource attribute
        operation_name: Operation name

    Returns:
        OTLP JSON string
    """
    lines = text.split("\n")
    timestamp_ns = _datetime_to_unix_nano(datetime.now(timezone.utc))
    log_records = []

    for line in lines:
        if not line.strip():
            continue

        # Infer severity from content
        line_lower = line.lower()
        if "error" in line_lower or "failed" in line_lower:
            severity_num = SEVERITY_NUMBER["error"]
            severity_text = "ERROR"
        elif "warning" in line_lower or "warn" in line_lower:
            severity_num = SEVERITY_NUMBER["warning"]
            severity_text = "WARN"
        elif "success" in line_lower or "complete" in line_lower:
            severity_num = SEVERITY_NUMBER["success"]
            severity_text = "INFO"
        else:
            severity_num = SEVERITY_NUMBER["info"]
            severity_text = "INFO"

        log_record = {
            "timeUnixNano": str(timestamp_ns),
            "observedTimeUnixNano": str(timestamp_ns),
            "severityNumber": severity_num,
            "severityText": severity_text,
            "body": {
                "stringValue": line
            },
            "attributes": [],
        }
        log_records.append(log_record)

    otlp_payload = {
        "resourceLogs": [
            {
                "resource": {
                    "attributes": [
                        {
                            "key": "service.name",
                            "value": {"stringValue": service_name}
                        },
                        {
                            "key": "operation.name",
                            "value": {"stringValue": operation_name}
                        }
                    ]
                },
                "scopeLogs": [
                    {
                        "scope": {
                            "name": "dbt-cloud-importer.web",
                            "version": "1.0.0"
                        },
                        "logRecords": log_records
                    }
                ]
            }
        ]
    }

    return json.dumps(otlp_payload, indent=2)


def text_to_log_text(text: str) -> str:
    """Convert raw text output to human-readable .log format.

    Adds severity prefixes based on content inference.

    Args:
        text: Raw text output

    Returns:
        Human-readable log text with severity prefixes
    """
    lines = text.split("\n")
    output_lines = []
    timestamp_str = datetime.now().astimezone().strftime("%Y-%m-%dT%H:%M:%S%z")

    for line in lines:
        if not line.strip():
            continue

        # Infer severity from content
        line_lower = line.lower()
        if "error" in line_lower or "failed" in line_lower:
            level_label = "ERROR"
        elif "warning" in line_lower or "warn" in line_lower:
            level_label = "WARN"
        elif "success" in line_lower or "complete" in line_lower:
            level_label = "INFO"
        else:
            level_label = "INFO"

        output_lines.append(f"[{timestamp_str}] [{level_label:7}] {line}")

    return "\n".join(output_lines)


def generate_log_filename(
    prefix: str = "output",
    extension: str = "log",
) -> str:
    """Generate a timestamped log filename.

    Args:
        prefix: Filename prefix (e.g., "terraform-plan", "deploy")
        extension: File extension (e.g., "log", "json")

    Returns:
        Timestamped filename like "terraform-plan-20260115-143022.log"
    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{prefix}-{timestamp}.{extension}"
