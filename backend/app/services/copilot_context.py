from typing import Dict, Any, List
from app.models.dataset import DatasetModel

def build_dataset_context(dataset: DatasetModel) -> Dict[str, Any]:
    """
    Extracts structured, privacy-safe metadata from actual profiling,
    quality scoring, and anomaly detection models.
    NEVER sends raw rows or PII to external LLMs.
    """
    # 1. Dataset metadata
    ds_info = {
        "name": dataset.name,
        "filename": dataset.original_filename,
        "file_type": dataset.file_type.upper(),
        "row_count": dataset.row_count,
        "column_count": dataset.column_count,
        "status": dataset.status,
        "overall_quality_score": round(dataset.quality_score, 1),
    }

    # 2. Quality dimensions and evidence
    qr = dataset.quality_report
    quality_info = {}
    if qr:
        quality_info = {
            "overall_score": round(qr.overall_score, 1),
            "completeness_score": round(qr.completeness_score, 1),
            "uniqueness_score": round(qr.uniqueness_score, 1),
            "validity_score": round(qr.validity_score, 1),
            "consistency_score": round(qr.consistency_score, 1),
            "duplicate_rows": qr.duplicate_rows_count,
            "duplicate_percentage": round(qr.duplicate_rows_percentage, 2),
            "total_cells": qr.total_cells,
            "null_cells": qr.null_cells,
            "evidence": [ev.get("message", "") for ev in (qr.deductions_evidence or [])],
        }

    # 3. Column profiles (aggregates only, no row-level PII)
    columns_info = []
    columns_with_nulls = []
    for col in dataset.column_profiles:
        c_dict = {
            "name": col.column_name,
            "type": col.data_type,
            "null_count": col.null_count,
            "null_percentage": col.null_percentage,
            "unique_count": col.unique_count,
        }
        if col.null_count > 0:
            columns_with_nulls.append((col.column_name, col.null_count, col.null_percentage))

        if col.is_numeric:
            c_dict["min"] = col.min_value
            c_dict["max"] = col.max_value
            c_dict["mean"] = round(col.mean_value, 2) if col.mean_value is not None else None
            c_dict["median"] = round(col.median_value, 2) if col.median_value is not None else None
        columns_info.append(c_dict)

    # 4. Detected anomalies
    anomalies_info = []
    for anom in dataset.anomalies:
        anomalies_info.append({
            "column": anom.column_name,
            "type": anom.anomaly_type,
            "severity": anom.severity,
            "affected_rows": anom.affected_rows,
            "description": anom.description,
            "statistical_details": anom.details,
        })

    # Sort columns with nulls descending
    columns_with_nulls.sort(key=lambda x: x[2], reverse=True)

    return {
        "dataset": ds_info,
        "quality": quality_info,
        "columns": columns_info,
        "columns_with_nulls": columns_with_nulls,
        "anomalies": anomalies_info,
    }

def build_system_prompt() -> str:
    return """You are the DataPulse AI Copilot — an expert data observability and data quality intelligence assistant.
Your job is to help data engineers understand their datasets, investigate root causes, and provide actionable remediation advice.

CRITICAL RULES:
1. GROUNDED IN TRUTH: Base all answers strictly on the verified profiling, data-quality metrics, and anomaly detection results provided in the context.
2. NEVER FABRICATE: Never invent statistics, non-existent columns, fake anomalies, or hallucinated record values.
3. ADMIT UNKNOWN: If information cannot be determined from the available metadata, clearly say so instead of guessing.
4. EVIDENCE VS HYPOTHESIS: Clearly distinguish confirmed evidence (e.g. "Column X has 34% nulls") from possible hypotheses (e.g. "This could be caused by an upstream ETL timeout or misconfigured CSV delimiter"). Never claim certainty for root causes that the data alone cannot prove.
5. ACTIONABLE RECOMMENDATIONS: Whenever relevant, provide specific recommendations with:
   - What issue was detected.
   - Which column or metric is involved.
   - Why it matters for downstream pipelines.
   - What concrete action the user should take.
6. NO DATA MODIFICATION: Do not offer or claim to automatically delete, mutate, or alter user records.
"""

def build_copilot_prompt(dataset_context: Dict[str, Any], user_question: str) -> str:
    ds = dataset_context["dataset"]
    q = dataset_context["quality"]
    cols = dataset_context["columns"]
    anoms = dataset_context["anomalies"]

    context_text = f"""### Verified Dataset Metadata
- Dataset Name: {ds['name']} (File: {ds['filename']}, Format: {ds['file_type']})
- Volume: {ds['row_count']:,} rows, {ds['column_count']} columns
- Status: {ds['status'].upper()}
- Overall Data Quality Score: {ds['overall_quality_score']}%

### Quality Dimensions Breakdown
- Completeness Score: {q.get('completeness_score', 'N/A')}% (Null cells: {q.get('null_cells', 0):,} of {q.get('total_cells', 0):,})
- Uniqueness Score: {q.get('uniqueness_score', 'N/A')}% (Duplicate rows: {q.get('duplicate_rows', 0):,} or {q.get('duplicate_percentage', 0)}%)
- Validity Score: {q.get('validity_score', 'N/A')}%
- Consistency Score: {q.get('consistency_score', 'N/A')}%
- Quality Audit Evidence:
{chr(10).join(f'  * {ev}' for ev in q.get('evidence', [])) if q.get('evidence') else '  * No deductions recorded.'}

### Schema & Column Profiling ({len(cols)} columns)
{chr(10).join(f"- {c['name']} ({c['type']}): {c['null_count']} nulls ({c['null_percentage']}%), {c['unique_count']} unique values" + (f", min={c['min']}, max={c['max']}, mean={c['mean']}, median={c['median']}" if 'min' in c and c['min'] is not None else "") for c in cols)}

### Statistical Outliers & Anomalies ({len(anoms)} detected)
{chr(10).join(f"- [{a['severity'].upper()}] {a['column']} ({a['type']}): {a['description']}" for a in anoms) if anoms else "- No anomalies detected."}
"""

    return f"""{context_text}

### User Question:
{user_question}

Answer the question thoroughly, professionally, and concisely in markdown format. If specific actions are needed, list them clearly."""

def generate_dataset_suggestions(dataset_context: Dict[str, Any]) -> List[str]:
    """Generates 4 dynamic, highly relevant questions tailored to the dataset's actual issues."""
    suggestions = []
    ds = dataset_context["dataset"]
    nulls = dataset_context.get("columns_with_nulls", [])
    anoms = dataset_context.get("anomalies", [])
    q = dataset_context.get("quality", {})

    # 1. Overview
    suggestions.append(f"What is the overall data quality of {ds['name']}?")

    # 2. Nulls
    if nulls:
        worst_null = nulls[0]
        suggestions.append(f"Why does column `{worst_null[0]}` have {worst_null[2]}% missing values?")
    else:
        suggestions.append("Which columns have the lowest distinct value ratio?")

    # 3. Anomalies or Duplicates
    if anoms:
        worst_anom = anoms[0]
        suggestions.append(f"What caused the anomaly detected in `{worst_anom['column']}`?")
    elif q.get("duplicate_rows", 0) > 0:
        suggestions.append(f"How can I resolve the {q.get('duplicate_rows')} duplicate records?")
    else:
        suggestions.append("What data contracts should I apply to prevent future regression?")

    # 4. Actionable recommendations
    suggestions.append("What are the top 3 data quality recommendations for this dataset?")

    return suggestions[:4]
