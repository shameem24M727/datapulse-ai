import math
import numpy as np
import pandas as pd
from typing import Dict, Any, List

def sanitize_float(val: Any) -> Any:
    """Ensure floats are JSON serializable (no NaN or Inf)."""
    if val is None or pd.isna(val) or (isinstance(val, float) and (math.isnan(val) or math.isinf(val))):
        return None
    return float(val)

def profile_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """
    Profiles an ingested Pandas DataFrame.
    Returns general stats and per-column profiles.
    """
    row_count = int(len(df))
    column_count = int(len(df.columns))
    duplicate_rows = int(df.duplicated().sum())
    duplicate_percentage = round((duplicate_rows / row_count * 100), 2) if row_count > 0 else 0.0

    columns_profile: List[Dict[str, Any]] = []

    for col_name in df.columns:
        series = df[col_name]
        null_count = int(series.isna().sum())
        null_percentage = round((null_count / row_count * 100), 2) if row_count > 0 else 0.0
        unique_count = int(series.nunique(dropna=True))

        # Check if numeric
        is_num = bool(pd.api.types.is_numeric_dtype(series))

        min_val = None
        max_val = None
        mean_val = None
        median_val = None
        std_val = None

        if is_num and (row_count - null_count) > 0:
            cleaned = series.dropna()
            if not cleaned.empty:
                min_val = sanitize_float(cleaned.min())
                max_val = sanitize_float(cleaned.max())
                mean_val = sanitize_float(cleaned.mean())
                median_val = sanitize_float(cleaned.median())
                std_val = sanitize_float(cleaned.std()) if len(cleaned) > 1 else 0.0

        # Frequency distribution for categorical or low-cardinality values
        top_vals: List[Dict[str, Any]] = []
        try:
            val_counts = series.value_counts(dropna=True).head(5)
            for val, count in val_counts.items():
                top_vals.append({
                    "value": str(val)[:100],  # truncate very long strings
                    "count": int(count),
                    "percentage": round(int(count) / row_count * 100, 2) if row_count > 0 else 0.0
                })
        except Exception:
            pass

        # Data type label
        dtype_str = str(series.dtype)
        if "int" in dtype_str:
            clean_type = "Integer"
        elif "float" in dtype_str:
            clean_type = "Float"
        elif "bool" in dtype_str:
            clean_type = "Boolean"
        elif "datetime" in dtype_str:
            clean_type = "DateTime"
        else:
            clean_type = "String / Categorical"

        columns_profile.append({
            "column_name": str(col_name),
            "data_type": clean_type,
            "total_count": row_count,
            "null_count": null_count,
            "null_percentage": null_percentage,
            "unique_count": unique_count,
            "is_numeric": is_num,
            "min_value": min_val,
            "max_value": max_val,
            "mean_value": mean_val,
            "median_value": median_val,
            "std_value": std_val,
            "top_values": top_vals,
        })

    return {
        "row_count": row_count,
        "column_count": column_count,
        "duplicate_rows": duplicate_rows,
        "duplicate_percentage": duplicate_percentage,
        "columns": columns_profile,
    }
