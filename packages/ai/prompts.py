"""
LLM prompt templates for property enrichment.

All prompts are designed to work with Amazon Bedrock models (Titan, Nova).
"""

SYSTEM_PROMPT = """You are an expert Irish property market analyst and real estate advisor.
You analyze property listings and provide concise, actionable insights for buyers.
Always focus on the Irish market context. Be specific about locations, pricing, and value.
Respond in JSON format when requested."""

PROPERTY_SUMMARY_PROMPT = """Analyze this Irish property listing and provide a comprehensive assessment.

Property Details:
- Title: {title}
- Address: {address}
- County: {county}
- Asking Price: {price}
- Type: {property_type}
- Bedrooms: {bedrooms}
- Bathrooms: {bathrooms}
- Floor Area: {floor_area_sqm} sq m
- BER Rating: {ber_rating}
- Description: {description}

Nearby Sold Prices (last 2 years):
{nearby_sold}

Respond in JSON with these fields:
{{
    "summary": "2-3 sentence overview of the property",
    "value_score": <float 1-10, where 10 is excellent value>,
    "value_reasoning": "Why this score, referencing comparable sales",
    "pros": ["list of positive aspects"],
    "cons": ["list of concerns or negatives"],
    "extracted_features": {{
        "parking": <bool or null>,
        "garden": <bool or null>,
        "garage": <bool or null>,
        "renovated": <bool or null>,
        "period_features": <bool or null>,
        "south_facing": <bool or null>,
        "sea_view": <bool or null>
    }},
    "neighbourhood_notes": "Brief notes about the area if inferable",
    "investment_potential": "Assessment of investment/resale potential"
}}"""

MARKET_TREND_PROMPT = """Analyze these Irish property market trends and provide insights.

Market Data:
- County: {county}
- Average Asking Price: {avg_price}
- Median Asking Price: {median_price}
- Active Listings: {listing_count}
- Price Trend (12 months): {price_trend}
- New Listings This Week: {new_listings}
- BER Distribution: {ber_distribution}

Provide a market analysis in JSON:
{{
    "market_summary": "Overview of the market",
    "price_outlook": "Expected price direction",
    "buyer_advice": "Advice for buyers in this market",
    "key_indicators": ["list of important signals"],
    "risk_factors": ["potential risks"]
}}"""

COMPARISON_PROMPT = """Compare these Irish properties and help a buyer decide.

Property A:
{property_a}

Property B:
{property_b}

Respond in JSON:
{{
    "recommendation": "A or B with reasoning",
    "comparison_table": {{
        "value": {{"a": <score>, "b": <score>}},
        "location": {{"a": <score>, "b": <score>}},
        "condition": {{"a": <score>, "b": <score>}},
        "potential": {{"a": <score>, "b": <score>}}
    }},
    "key_differences": ["list of important differences"],
    "overall_verdict": "Final recommendation for a buyer"
}}"""
