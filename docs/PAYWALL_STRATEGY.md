# Paywall Handling Strategy

This document outlines the strategy for handling paywalled content in the news scraper.

## Overview

Many financial news sources implement paywalls that restrict access to their content. This document describes how the scraper detects, handles, and processes paywalled content while respecting publishers' rights and terms of service.

## Paywall Types

The system recognizes four types of paywalls:

### 1. Hard Paywall
- **Description**: No content accessible without a paid subscription
- **Examples**: Wall Street Journal, Financial Times, Barron's
- **Strategy**: Extract only publicly available metadata (title, summary from meta tags)

### 2. Soft Paywall
- **Description**: Some content available (e.g., first few paragraphs)
- **Examples**: Seeking Alpha, The Street
- **Strategy**: Extract available content, flag as partial

### 3. Metered Paywall
- **Description**: Limited free articles per time period
- **Examples**: Bloomberg, New York Times
- **Strategy**: Extract available content while accessible, track article limits

### 4. Registration Wall
- **Description**: Requires free account to access
- **Examples**: Some industry publications
- **Strategy**: Extract publicly visible content, flag registration requirement

## Detection Methods

### CSS/HTML Pattern Matching
The system scans for common paywall-related patterns:
- CSS classes: `paywall`, `subscribe`, `premium-content`, `members-only`
- IDs: `paywall-modal`, `subscription-prompt`
- Vendor-specific: `piano-id`, `tp-modal` (TinyPass/Piano)

### Text Pattern Detection
Searches for subscription prompts:
- "Subscribe to continue reading"
- "This article is for subscribers only"
- "You've reached your free article limit"
- "Unlock this article"

### Meta Tag Analysis
Checks for premium content indicators:
- `<meta name="article:content_tier" content="premium">`
- `<meta property="article:is_free" content="false">`
- `<meta name="og:restrictions:content" content="metered">`

### Content Truncation Detection
- Compares content length against expected article length
- Detects truncation markers: "...", "Read more", "Continue reading"
- Flags unusually short articles

### Domain-Specific Rules
Pre-configured rules for known paywalled sites:
- WSJ, FT, Bloomberg, NYT, etc.
- Custom content selectors per domain
- Known paywall types

## Data Model Changes

### Event Metadata Fields

```json
{
  "metadata": {
    "paywall": {
      "is_paywalled": true,
      "paywall_type": "soft",
      "confidence": 0.85,
      "available_content": "First paragraph text...",
      "extracted_title": "Article Title",
      "extracted_summary": "Meta description...",
      "indicators_found": ["css_class:paywall", "text_pattern:subscribe"]
    },
    "is_partial_content": true,
    "content_completeness": "partial"
  }
}
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `is_paywalled` | boolean | Whether content is behind a paywall |
| `paywall_type` | enum | Type of paywall (none, hard, soft, metered, registration) |
| `confidence` | float | Detection confidence (0.0 to 1.0) |
| `available_content` | string | Content that was accessible |
| `extracted_title` | string | Article title from meta tags |
| `extracted_summary` | string | Summary/description if available |
| `indicators_found` | array | List of detected paywall indicators |
| `is_partial_content` | boolean | Whether content is incomplete |
| `content_completeness` | enum | Content status (full, partial, minimal) |

## Implementation Details

### Paywall Detector Class

Located at: `backend/ingestion/scrapers/paywall_detector.py`

Key methods:
- `detect(html, url, expected_length)`: Main detection method
- `_check_css_patterns()`: CSS pattern matching
- `_check_text_patterns()`: Text pattern matching
- `_check_meta_tags()`: Meta tag analysis
- `_check_truncation()`: Content length analysis
- `_extract_main_content()`: Content extraction
- `_extract_title()`: Title extraction
- `_extract_summary()`: Summary extraction

### Integration with Scrapers

```python
# In base_scraper.py
async def fetch_with_paywall_detection(self, url, expected_length=None):
    response = await self.fetch(url)
    detector = PaywallDetector()
    paywall_result = detector.detect(
        html=response.text,
        url=url,
        expected_length=expected_length,
    )
    return response, paywall_result
```

### Usage in Scrapers

```python
from backend.ingestion.scrapers import PaywallDetector, normalize_event_with_paywall

# Detect paywall
response, paywall_result = await self.fetch_with_paywall_detection(url)

# Normalize event with paywall info
event = normalize_event_with_paywall(raw_data, paywall_result)
```

## Ethical Considerations

### Respect for Publishers

1. **No Circumvention**: The system does not attempt to bypass paywalls
2. **Public Data Only**: Only extracts publicly visible content
3. **Rate Limiting**: Respects robots.txt and rate limits
4. **Attribution**: Always includes source attribution

### Data Usage

1. **Transparency**: Events are flagged as partial content
2. **User Awareness**: Frontend displays paywall indicators
3. **Source Links**: Always provides links to original content

## Configuration

### Adding New Paywalled Domains

Edit `DOMAIN_CONFIGS` in `paywall_detector.py`:

```python
DOMAIN_CONFIGS = {
    "example.com": {
        "paywall_type": PaywallType.SOFT,
        "content_selector": "article.content",
        "truncation_marker": "Read more",
    },
}
```

### Adjusting Detection Sensitivity

```python
# In PaywallDetector class
MIN_FULL_ARTICLE_LENGTH = 500  # Minimum chars for "full" article
TRUNCATION_THRESHOLD = 0.3     # Visible/expected content ratio
```

## Frontend Display

### Paywall Indicators

Events with paywalled content should display:
- Visual badge indicating partial content
- Link to full article at source
- Note about subscription requirement

### Example UI Component

```jsx
{event.metadata?.is_partial_content && (
  <Badge variant="warning">
    Partial Content - {event.metadata.paywall?.paywall_type} paywall
  </Badge>
)}
```

## Monitoring and Metrics

### Recommended Metrics

1. **Paywall Detection Rate**: % of articles detected as paywalled
2. **Detection Accuracy**: Manual verification sampling
3. **Content Completeness**: Average content length by source
4. **False Positive Rate**: Articles incorrectly flagged

### Logging

All paywall detections are logged:
```
INFO: Paywall detected url=https://wsj.com/... paywall_type=hard confidence=0.85
```

## Future Improvements

1. **Machine Learning Detection**: Train classifier on labeled data
2. **Dynamic Rule Updates**: Auto-learn new paywall patterns
3. **Content Quality Scoring**: Rate partial content usefulness
4. **Archive Integration**: Link to archived versions when available
5. **RSS Enhancement**: Prefer RSS feeds which often have full content

## Related Documentation

- [Data Labeling Guidelines](./DATA_LABELING_GUIDELINES.md)
- [Fine-tuning Documentation](./FINETUNING.md)
- [Scraper Architecture](./ARCHITECTURE.md)
