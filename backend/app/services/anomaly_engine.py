import numpy as np
import pandas as pd
from typing import List, Dict, Any

def detect_anomalies(df: pd.DataFrame, profiling_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Performs explainable statistical anomaly detection on numeric columns using Z-score and IQR methods.
    Also flags excessive missing value spikes.
    Returns list of detected anomalies with column name, type, severity, affected count, and rationale.
    """
    anomalies: List[Dict[str, Any]] = []
    row_count = profiling_data["row_count"]

    if row_count < 4:
        return anomalies

    for col in profiling_data["columns"]:
        col_name = col["column_name"]
        series = df[col_name]

        # ── 1. Null Value Spike Anomaly ─────────────────────────────────────────
        null_pct = col["null_percentage"]
        if null_pct >= 25.0:
            severity = "critical" if null_pct >= 50.0 else "high"
            anomalies.append({
                "column_name": col_name,
                "anomaly_type": "null_spike",
                "severity": severity,
                "affected_rows": col["null_count"],
                "description": f"High null rate detected in `{col_name}`: {null_pct}% of values are missing ({col['null_count']:,} of {row_count:,} rows).",
                "details": {
                    "null_count": col["null_count"],
                    "null_percentage": null_pct,
                    "threshold_percentage": 25.0,
                },
            })

        # ── 2. Numeric Outlier Detection (Z-score & IQR) ────────────────────────
        if col["is_numeric"] and (row_count - col["null_count"]) >= 5:
            clean_series = series.dropna().astype(float)
            std = clean_series.std()
            mean = clean_series.mean()

            if std > 0:
                # Z-Score Outliers (|z| > 3.0)
                z_scores = np.abs((clean_series - mean) / std)
                z_outliers = clean_series[z_scores > 3.0]
                z_count = int(len(z_outliers))

                if z_count > 0:
                    max_z = float(z_scores.max())
                    outlier_sample = [round(float(v), 2) for v in z_outliers.head(5).tolist()]
                    severity = "critical" if max_z > 5.0 or (z_count / row_count) > 0.05 else "high" if max_z > 4.0 else "medium"

                    anomalies.append({
                        "column_name": col_name,
                        "anomaly_type": "zscore_outlier",
                        "severity": severity,
                        "affected_rows": z_count,
                        "description": f"Found {z_count} statistical outlier(s) in `{col_name}` exceeding 3 standard deviations (max z-score: {max_z:.2f}σ).",
                        "details": {
                            "method": "Z-score (|z| > 3.0)",
                            "mean": round(float(mean), 2),
                            "std_dev": round(float(std), 2),
                            "max_deviation_sigma": round(max_z, 2),
                            "sample_values": outlier_sample,
                        },
                    })

                # IQR Outliers ([Q1 - 1.5*IQR, Q3 + 1.5*IQR])
                q1 = float(clean_series.quantile(0.25))
                q3 = float(clean_series.quantile(0.75))
                iqr = q3 - q1

                if iqr > 0:
                    lower_bound = q1 - 1.5 * iqr
                    upper_bound = q3 + 1.5 * iqr
                    iqr_outliers = clean_series[(clean_series < lower_bound) | (clean_series > upper_bound)]
                    iqr_count = int(len(iqr_outliers))

                    # Only log if IQR identifies substantial deviations not already fully captured
                    if iqr_count > 0 and (z_count == 0 or iqr_count > z_count):
                        anomalies.append({
                            "column_name": col_name,
                            "anomaly_type": "iqr_outlier",
                            "severity": "medium",
                            "affected_rows": iqr_count,
                            "description": f"Interquartile Range (IQR) filter flagged {iqr_count} values outside expected fence [{lower_bound:.2f}, {upper_bound:.2f}].",
                            "details": {
                                "method": "Tukey IQR Fence (1.5x)",
                                "q1": round(q1, 2),
                                "q3": round(q3, 2),
                                "iqr": round(iqr, 2),
                                "fence_lower": round(lower_bound, 2),
                                "fence_upper": round(upper_bound, 2),
                            },
                        })

    return anomalies
