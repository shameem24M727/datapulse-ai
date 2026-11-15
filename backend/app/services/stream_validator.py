from typing import Dict, Any, List, Tuple
from datetime import datetime

class RecordValidationResult:
    def __init__(self, is_valid: bool, errors: List[Dict[str, Any]], warnings: List[Dict[str, Any]]):
        self.is_valid = is_valid
        self.errors = errors
        self.warnings = warnings

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_valid": self.is_valid,
            "errors": self.errors,
            "warnings": self.warnings,
        }

def validate_field_type(value: Any, expected_type: str) -> bool:
    """Validates primitive JSON types without unsafe conversions."""
    if value is None:
        return True

    if expected_type == "string":
        return isinstance(value, str)

    if expected_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)

    if expected_type == "float":
        return (isinstance(value, (int, float))) and not isinstance(value, bool)

    if expected_type == "boolean":
        return isinstance(value, bool)

    if expected_type == "datetime":
        if isinstance(value, datetime):
            return True
        if isinstance(value, str):
            try:
                datetime.fromisoformat(value.replace("Z", "+00:00"))
                return True
            except (ValueError, TypeError):
                return False
        return False

    if expected_type == "json":
        return isinstance(value, (dict, list))

    return False

def validate_stream_record(record: Dict[str, Any], schema_definition: Dict[str, Any]) -> RecordValidationResult:
    """
    Validates a single stream JSON record against a pipeline's schema definition.
    Distinguishes hard errors (missing required fields, type mismatches, strict violations)
    from soft warnings (optional nulls).
    """
    if not isinstance(record, dict):
        return RecordValidationResult(
            is_valid=False,
            errors=[{"field": "_root", "code": "malformed_record", "message": "Record must be a valid JSON object."}],
            warnings=[],
        )

    fields_config = schema_definition.get("fields", [])
    strict = bool(schema_definition.get("strict", False))

    declared_fields = {f["name"]: f for f in fields_config}
    errors: List[Dict[str, Any]] = []
    warnings: List[Dict[str, Any]] = []

    # 1. Validate declared fields
    for field_name, f_def in declared_fields.items():
        is_required = f_def.get("required", False)
        expected_type = f_def.get("type", "string")

        if field_name not in record or record[field_name] is None:
            if is_required:
                errors.append({
                    "field": field_name,
                    "code": "missing_required_field",
                    "message": f"Required field '{field_name}' is missing or null.",
                })
            else:
                warnings.append({
                    "field": field_name,
                    "code": "optional_null",
                    "message": f"Optional field '{field_name}' contains null.",
                })
        else:
            val = record[field_name]
            if not validate_field_type(val, expected_type):
                errors.append({
                    "field": field_name,
                    "code": "type_mismatch",
                    "message": f"Field '{field_name}' expected type '{expected_type}', got '{type(val).__name__}'.",
                    "value": str(val)[:100],
                })

    # 2. Strict policy check (flag undeclared fields, ignoring internal metadata)
    if strict:
        ignored_keys = {"is_simulated", "simulator_timestamp", "_id", "_timestamp"}
        for k in record.keys():
            if k not in declared_fields and k not in ignored_keys:
                errors.append({
                    "field": k,
                    "code": "unexpected_field",
                    "message": f"Undeclared field '{k}' rejected under strict schema policy.",
                })

    is_valid = len(errors) == 0
    return RecordValidationResult(is_valid=is_valid, errors=errors, warnings=warnings)
