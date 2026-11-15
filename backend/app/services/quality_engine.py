import pandas as pd
from typing import Dict, Any, List

def compute_data_quality(df: pd.DataFrame, profiling_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes deterministic, explainable data quality scores across 4 dimensions:
    1. Completeness (Weight: 35%)
    2. Uniqueness (Weight: 25%)
    3. Validity (Weight: 20%)
    4. Consistency (Weight: 20%)

    Returns overall score, dimension scores, and specific evidence of deductions.
    """
    row_count = profiling_data["row_count"]
    col_count = profiling_data["column_count"]
    total_cells = row_count * col_count
    evidence: List[Dict[str, Any]] = []

    if total_cells == 0:
        return {
            "overall_score": 0.0,
            "completeness_score": 0.0,
            "uniqueness_score": 0.0,
            "validity_score": 0.0,
            "consistency_score": 0.0,
            "duplicate_rows_count": 0,
            "duplicate_rows_percentage": 0.0,
            "total_cells": 0,
            "null_cells": 0,
            "evidence": [{"dimension": "General", "impact": "negative", "message": "Dataset contains 0 cells."}],
            "status": "critical",
        }

    # ── 1. Completeness Check ──────────────────────────────────────────────────
    total_null_cells = sum(col["null_count"] for col in profiling_data["columns"])
    null_rate = total_null_cells / total_cells
    completeness_score = round(max(0.0, (1.0 - null_rate) * 100.0), 1)

    if total_null_cells == 0:
        evidence.append({
            "dimension": "Completeness",
            "impact": "positive",
            "score_effect": "+0 pts deducted",
            "message": f"Zero missing values detected across all {total_cells:,} cells (100% complete).",
        })
    else:
        columns_with_nulls = [
            f"{c['column_name']} ({c['null_percentage']}%)"
            for c in profiling_data["columns"]
            if c["null_count"] > 0
        ]
        evidence.append({
            "dimension": "Completeness",
            "impact": "negative",
            "score_effect": f"-{round(null_rate * 100, 1)} pts",
            "message": f"Found {total_null_cells:,} null cells ({round(null_rate * 100, 2)}% of total). Affected columns: {', '.join(columns_with_nulls[:4])}{'...' if len(columns_with_nulls) > 4 else ''}.",
        })

    # ── 2. Uniqueness Check ────────────────────────────────────────────────────
    duplicate_rows = profiling_data["duplicate_rows"]
    dup_rate = duplicate_rows / row_count if row_count > 0 else 0.0
    uniqueness_score = round(max(0.0, (1.0 - dup_rate) * 100.0), 1)

    if duplicate_rows == 0:
        evidence.append({
            "dimension": "Uniqueness",
            "impact": "positive",
            "score_effect": "+0 pts deducted",
            "message": f"All {row_count:,} records are distinct. No duplicate rows detected.",
        })
    else:
        evidence.append({
            "dimension": "Uniqueness",
            "impact": "negative",
            "score_effect": f"-{round(dup_rate * 100, 1)} pts",
            "message": f"Found {duplicate_rows:,} exact duplicate rows ({round(dup_rate * 100, 2)}% redundancy rate).",
        })

    # ── 3. Validity Check ──────────────────────────────────────────────────────
    # Check for invalid values: infinite floats, mixed unparseable representations, extreme empty strings
    validity_penalty = 0.0
    invalid_findings = []

    for col in profiling_data["columns"]:
        col_name = col["column_name"]
        series = df[col_name]

        # Check for empty strings in object columns
        if not col["is_numeric"]:
            empty_string_count = int((series.astype(str).str.strip() == "").sum())
            # Don't double count if already counted as null
            unaccounted_empty = max(0, empty_string_count - col["null_count"])
            if unaccounted_empty > 0:
                col_penalty = round((unaccounted_empty / row_count) * 20.0, 1)
                validity_penalty += col_penalty
                invalid_findings.append(f"{col_name} has {unaccounted_empty} blank string values")

        # Check for inf in numeric columns
        if col["is_numeric"]:
            inf_count = int(series.isin([float("inf"), float("-inf")]).sum())
            if inf_count > 0:
                validity_penalty += min(25.0, inf_count * 2.0)
                invalid_findings.append(f"{col_name} has {inf_count} infinite values")

    validity_score = round(max(0.0, min(100.0, 100.0 - validity_penalty)), 1)
    if not invalid_findings:
        evidence.append({
            "dimension": "Validity",
            "impact": "positive",
            "score_effect": "+0 pts deducted",
            "message": "All populated cell values conform to expected primitive data formats.",
        })
    else:
        evidence.append({
            "dimension": "Validity",
            "impact": "negative",
            "score_effect": f"-{round(validity_penalty, 1)} pts",
            "message": f"Format validity anomalies identified: {'; '.join(invalid_findings[:3])}.",
        })

    # ── 4. Consistency Check ───────────────────────────────────────────────────
    # Evaluates schema balance and unexpected column naming or high standard deviation instability
    consistency_penalty = 0.0
    consistency_findings = []

    # Check for trailing whitespace in column names
    messy_columns = [c for c in df.columns if c != c.strip() or "  " in c]
    if messy_columns:
        consistency_penalty += min(15.0, len(messy_columns) * 3.0)
        consistency_findings.append(f"{len(messy_columns)} columns have irregular whitespace in headers")

    # Check for single-value columns (zero variance constant columns)
    single_value_cols = [c["column_name"] for c in profiling_data["columns"] if c["unique_count"] == 1 and row_count > 10]
    if single_value_cols:
        consistency_penalty += min(10.0, len(single_value_cols) * 2.5)
        consistency_findings.append(f"{len(single_value_cols)} constant columns with zero informational entropy ({', '.join(single_value_cols[:2])})")

    consistency_score = round(max(0.0, min(100.0, 100.0 - consistency_penalty)), 1)
    if not consistency_findings:
        evidence.append({
            "dimension": "Consistency",
            "impact": "positive",
            "score_effect": "+0 pts deducted",
            "message": "High schema uniformity: Consistent column headers and healthy value distribution.",
        })
    else:
        evidence.append({
            "dimension": "Consistency",
            "impact": "negative",
            "score_effect": f"-{round(consistency_penalty, 1)} pts",
            "message": f"Schema consistency observations: {'; '.join(consistency_findings)}.",
        })

    # ── Weighted Overall Score ─────────────────────────────────────────────────
    # Weights: Completeness (35%), Uniqueness (25%), Validity (20%), Consistency (20%)
    overall = (
        0.35 * completeness_score
        + 0.25 * uniqueness_score
        + 0.20 * validity_score
        + 0.20 * consistency_score
    )
    overall_score = round(overall, 1)

    # Determine status
    if overall_score >= 85.0:
        status = "healthy"
    elif overall_score >= 60.0:
        status = "warning"
    else:
        status = "critical"

    return {
        "overall_score": overall_score,
        "completeness_score": completeness_score,
        "uniqueness_score": uniqueness_score,
        "validity_score": validity_score,
        "consistency_score": consistency_score,
        "duplicate_rows_count": duplicate_rows,
        "duplicate_rows_percentage": profiling_data["duplicate_percentage"],
        "total_cells": total_cells,
        "null_cells": total_null_cells,
        "evidence": evidence,
        "status": status,
    }
