"""LLM usage policy: narrative and reasoning only; numbers must be tool- or pipeline-backed."""

# Shown in API payloads so clients never treat model prose as authoritative for figures.
NUMERIC_GROUNDING_POLICY = (
    "The model explains and synthesizes; it does not compute prices, returns, Greeks, or "
    "fundamental ratios. Treat all numeric claims as provisional unless they match tool "
    "outputs or deterministic pipeline results included in the response."
)
