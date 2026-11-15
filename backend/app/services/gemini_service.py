import logging
import asyncio
from typing import Dict, Any, List, Optional, Tuple
from app.core.config import settings
from app.services.copilot_context import (
    build_dataset_context,
    build_system_prompt,
    build_copilot_prompt,
)

logger = logging.getLogger("datapulse.gemini")

class GeminiCopilotService:
    def __init__(self):
        self.api_key = settings.GEMINI_API_KEY
        self.model = settings.GEMINI_MODEL
        self.timeout = settings.GEMINI_REQUEST_TIMEOUT_SECONDS
        self._client = None

    def _get_client(self):
        if not self.api_key:
            return None
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception as e:
                logger.error(f"Failed to initialize google-genai Client: {e}")
                return None
        return self._client

    def is_api_configured(self) -> bool:
        return bool(self.api_key and self.api_key.strip())

    async def generate_copilot_response(
        self,
        dataset_context: Dict[str, Any],
        user_question: str,
    ) -> Dict[str, Any]:
        """
        Generates an AI response using Gemini if configured,
        otherwise gracefully falls back to a deterministic, fully-grounded response.
        """
        client = self._get_client()

        if client and self.is_api_configured():
            try:
                # Build context-grounded prompt
                system_instruction = build_system_prompt()
                prompt = build_copilot_prompt(dataset_context, user_question)

                # Execute call in thread pool with timeout protection
                from google.genai import types
                config = types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    temperature=0.2,  # Low temperature for strict factual accuracy
                    max_output_tokens=1500,
                )

                loop = asyncio.get_event_loop()
                response = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda: client.models.generate_content(
                            model=self.model,
                            contents=prompt,
                            config=config,
                        ),
                    ),
                    timeout=self.timeout,
                )

                if response and response.text:
                    metrics, recommendations = self._extract_metrics_and_recommendations(
                        dataset_context, response.text
                    )
                    return {
                        "answer": response.text.strip(),
                        "metrics": metrics,
                        "recommendations": recommendations,
                        "model": self.model,
                        "is_fallback": False,
                        "evidence_used": dataset_context["quality"].get("evidence", []),
                    }

            except asyncio.TimeoutError:
                logger.warning(f"Gemini API request timed out after {self.timeout}s. Using grounded fallback.")
            except Exception as exc:
                logger.warning(f"Gemini API invocation error ({type(exc).__name__}: {exc}). Using grounded fallback.")

        # Grounded Deterministic Fallback Generator
        return self._generate_grounded_fallback(dataset_context, user_question)

    def _generate_grounded_fallback(
        self,
        dataset_context: Dict[str, Any],
        user_question: str,
    ) -> Dict[str, Any]:
        """
        Deterministic, 100% grounded responses based on actual database findings.
        Used when GEMINI_API_KEY is not configured or when an external API error occurs.
        """
        ds = dataset_context["dataset"]
        q = dataset_context["quality"]
        nulls = dataset_context.get("columns_with_nulls", [])
        anoms = dataset_context.get("anomalies", [])
        q_score = ds["overall_quality_score"]

        q_lower = user_question.lower()

        metrics: List[Dict[str, str]] = [
            {"label": "Quality Score", "value": f"{q_score}%", "status": "good" if q_score >= 85 else "warn" if q_score >= 60 else "bad"},
            {"label": "Volume Profile", "value": f"{ds['row_count']:,} rows", "status": "good"},
            {"label": "Completeness", "value": f"{q.get('completeness_score', 100)}%", "status": "good" if q.get("completeness_score", 100) >= 90 else "warn"},
        ]

        recommendations: List[str] = []

        # 1. Missing values / Completeness queries
        if any(w in q_lower for w in ["missing", "null", "completeness", "empty"]):
            if nulls:
                top_null_col, top_null_cnt, top_null_pct = nulls[0]
                answer = (
                    f"### Completeness Analysis for **{ds['name']}**\n\n"
                    f"The dataset received a **Completeness score of {q.get('completeness_score')}%**. "
                    f"A total of **{q.get('null_cells', 0):,} null cells** were detected across {ds['row_count']:,} rows.\n\n"
                    f"**Most Affected Columns:**\n"
                    + "\n".join(f"- `{col[0]}`: **{col[1]:,} missing values** ({col[2]}% null rate)" for col in nulls[:4])
                    + "\n\n*Hypothesis*: High null ratios often point to upstream ingestion timeouts, optional form fields, or schema migration mismatches. "
                    "Review extraction query filters before downstream transformations."
                )
                recommendations = [
                    f"Investigate upstream ETL extraction job for column `{top_null_col}`.",
                    "Implement a schema validation constraint enforcing non-null fields on mandatory keys.",
                    "Quarantine rows with missing primary identifiers before joining with analytics warehouse.",
                ]
            else:
                answer = (
                    f"### Completeness Analysis for **{ds['name']}**\n\n"
                    f"Excellent news: **{ds['name']} is 100% complete**. "
                    f"Zero null values were detected across all {q.get('total_cells', 0):,} cells."
                )
                recommendations = [
                    "Maintain continuous data contract validation to guard against future ingestion regressions."
                ]

        # 2. Duplicate / Uniqueness queries
        elif any(w in q_lower for w in ["duplicate", "uniqueness", "redundant", "dedup"]):
            dups = q.get("duplicate_rows", 0)
            dup_pct = q.get("duplicate_percentage", 0.0)
            if dups > 0:
                answer = (
                    f"### Uniqueness & Duplicate Analysis\n\n"
                    f"Found **{dups:,} exact duplicate rows** ({dup_pct}% redundancy) in **{ds['name']}**. "
                    f"This reduces the Uniqueness score to **{q.get('uniqueness_score')}%**.\n\n"
                    f"*Root Cause Potential*: Duplicates frequently arise from message broker retry logic, idempotent pipeline replay failures, or unconstrained database joins."
                )
                recommendations = [
                    f"Review ingestion deduplication key across `{ds['name']}` primary columns.",
                    "Audit message broker consumer idempotency settings.",
                    "Execute deduplication transform before downstream staging warehouse loads.",
                ]
            else:
                answer = (
                    f"### Uniqueness Analysis\n\n"
                    f"All **{ds['row_count']:,} records are unique** (100% uniqueness). "
                    f"No exact duplicate rows were identified in **{ds['name']}**."
                )

        # 3. Anomaly / Outlier queries
        elif any(w in q_lower for w in ["anomaly", "anomalies", "outlier", "outliers", "z-score", "iqr"]):
            if anoms:
                answer = (
                    f"### Anomaly Detection Findings for **{ds['name']}** (`{ds['filename']}`)\n\n"
                    f"DataPulse statistical profiling identified **{len(anoms)} anomaly incident(s)**:\n\n"
                    + "\n".join(
                        f"- **[{a['severity'].upper()}]** Column `{a['column']}` ({a['type'].replace('_', ' ')}): "
                        f"{a['description']}"
                        for a in anoms
                    )
                    + "\n\n*Confirmed Evidence*: These statistical deviations exceed expected variance fences (Z-score $|z| > 3.0$ or Tukey IQR 1.5x)."
                )
                top_anom = anoms[0]
                recommendations = [
                    f"Inspect `{top_anom['column']}` values to isolate whether deviation represents legitimate business spikes or telemetry error.",
                    "Set dynamic threshold alerts on extreme standard deviation boundaries.",
                ]
            else:
                answer = (
                    f"### Anomaly Detection Summary\n\n"
                    f"Zero statistical outliers or null spikes were detected in **{ds['name']}** (`{ds['filename']}`). "
                    f"All numerical distributions fall safely within normal 3-sigma and IQR fences."
                )

        # 4. Root Cause / Remediation / Problem / Issue queries
        elif any(w in q_lower for w in ["problem", "issue", "fix", "remed", "recommend", "improve", "why", "cause", "action"]):
            evidence_summary = q.get("evidence", [])
            answer = (
                f"### Root-Cause & Quality Audit Findings for **{ds['name']}** (`{ds['filename']}`)\n\n"
                f"- **Overall Health Score**: **{q_score}%** (Status: **{ds['status'].upper()}**)\n"
                f"- **Completeness**: {q.get('completeness_score', 'N/A')}%\n"
                f"- **Uniqueness**: {q.get('uniqueness_score', 'N/A')}%\n\n"
                f"**Quality Audit Findings:**\n"
                + ("\n".join(f"* {ev}" for ev in evidence_summary) if evidence_summary else "* No quality deductions recorded.")
                + "\n\n### Actionable Recommendations:\n"
            )
            if nulls:
                recommendations.append(f"Investigate {nulls[0][2]}% missing values in column `{nulls[0][0]}`.")
                answer += f"1. **Missing Data**: Investigate column `{nulls[0][0]}` ({nulls[0][2]}% null rate). Review upstream producer extraction logic.\n"
            if q.get("duplicate_rows", 0) > 0:
                recommendations.append(f"Resolve {q.get('duplicate_rows')} duplicate records.")
                answer += f"2. **Deduplication**: Apply primary key deduplication to eliminate {q.get('duplicate_rows')} duplicate records.\n"
            if anoms:
                recommendations.append(f"Review statistical outliers flagged in `{anoms[0]['column']}`.")
                answer += f"3. **Anomalies**: Review extreme value outliers detected in `{anoms[0]['column']}`.\n"
            if not recommendations:
                recommendations.append("Apply automated DataPulse regression contracts for ongoing ingestion.")
                answer += "1. **Continuous Monitoring**: Apply automated DataPulse regression contracts to maintain 100% quality.\n"

        # 5. General explanation / Overview / Recommendations
        else:
            evidence_summary = q.get("evidence", [])
            answer = (
                f"### Observability Summary for **{ds['name']}** (`{ds['filename']}`)\n\n"
                f"- **Overall Health Score**: **{q_score}%** (Status: **{ds['status'].upper()}**)\n"
                f"- **Dimensions Profiled**: {ds['row_count']:,} rows across {ds['column_count']} columns ({ds['file_type']} file)\n"
                f"- **Completeness**: {q.get('completeness_score', 'N/A')}%\n"
                f"- **Uniqueness**: {q.get('uniqueness_score', 'N/A')}%\n"
                f"- **Validity**: {q.get('validity_score', 'N/A')}%\n"
                f"- **Consistency**: {q.get('consistency_score', 'N/A')}%\n\n"
                f"**Quality Audit Evidence:**\n"
                + ("\n".join(f"* {ev}" for ev in evidence_summary) if evidence_summary else "* No negative deviations recorded.")
            )
            if nulls:
                recommendations.append(f"Investigate {nulls[0][2]}% missing values in column `{nulls[0][0]}`.")
            if q.get("duplicate_rows", 0) > 0:
                recommendations.append(f"Resolve {q.get('duplicate_rows')} duplicate records.")
            if anoms:
                recommendations.append(f"Review statistical outliers flagged in `{anoms[0]['column']}`.")
            if not recommendations:
                recommendations.append("Apply automated DataPulse regression contracts for ongoing ingestion.")

        notice = ""
        if not self.is_api_configured():
            notice = "\n\n> ℹ️ *Note: Gemini API key is not configured in `.env`. Answering via DataPulse deterministic intelligence engine based on verified database findings.*"

        return {
            "answer": answer + notice,
            "metrics": metrics,
            "recommendations": recommendations,
            "model": "DataPulse-Grounded-Engine" if not self.is_api_configured() else self.model,
            "is_fallback": True,
            "evidence_used": q.get("evidence", []),
        }

    def _extract_metrics_and_recommendations(
        self,
        dataset_context: Dict[str, Any],
        response_text: str,
    ) -> Tuple[List[Dict[str, str]], List[str]]:
        ds = dataset_context["dataset"]
        q = dataset_context["quality"]
        q_score = ds["overall_quality_score"]

        metrics: List[Dict[str, str]] = [
            {"label": "Health Score", "value": f"{q_score}%", "status": "good" if q_score >= 85 else "warn" if q_score >= 60 else "bad"},
            {"label": "Total Rows", "value": f"{ds['row_count']:,}", "status": "good"},
            {"label": "Completeness", "value": f"{q.get('completeness_score', 100)}%", "status": "good" if q.get("completeness_score", 100) >= 90 else "warn"},
        ]

        # Extract markdown bullet list recommendations if Gemini output formatted them
        recs: List[str] = []
        for line in response_text.split("\n"):
            line_s = line.strip()
            if line_s.startswith(("- ", "* ", "1. ", "2. ", "3. ")) and len(line_s) > 10:
                clean_rec = line_s.lstrip("-*0123456789. ")
                if any(w in clean_rec.lower() for w in ["investigate", "review", "validate", "check", "ensure", "clean", "quarantine", "recommend"]):
                    recs.append(clean_rec)
                    if len(recs) >= 3:
                        break

        # Fallback to smart dataset recs if none parsed
        if not recs:
            nulls = dataset_context.get("columns_with_nulls", [])
            anoms = dataset_context.get("anomalies", [])
            if nulls:
                recs.append(f"Investigate high null occurrence in `{nulls[0][0]}` ({nulls[0][2]}% missing).")
            if anoms:
                recs.append(f"Examine `{anoms[0]['column']}` for anomalous values exceeding 3-sigma variance.")
            if q.get("duplicate_rows", 0) > 0:
                recs.append(f"Deduplicate {q.get('duplicate_rows')} redundant records.")

        return metrics, recs[:3]

gemini_copilot_service = GeminiCopilotService()

