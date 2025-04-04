# Lead Classification Module Documentation

The Lead Classification module provides comprehensive analysis and categorization of construction leads across multiple dimensions, helping to prioritize opportunities and allocate resources effectively. This document explains how the module works, how to configure it, and how to integrate it with other system components.

## Overview

The LeadClassifier analyzes construction leads and classifies them across several dimensions:

- **Value Category**: Categorizes leads by estimated project value (Small, Medium, Large, Major)
- **Timeline Category**: Determines project timing (Immediate, Short-term, Mid-term, Long-term)
- **Decision Stage**: Identifies where the project stands in the decision process (Conceptual, Planning, Approval, Funding, Implementation)
- **Competition Level**: Assesses the competitive landscape (Low, Medium, High)
- **Win Probability**: Calculates the probability of winning the project (0.0-1.0)
- **Priority Score**: Assigns an overall priority score (1-100) and level (Critical, High, Medium, Low, Minimal)

These classifications help sales and business development teams focus on the most promising leads and develop appropriate pursuit strategies.

## Key Features

- **Sector-Specific Classification**: Applies different thresholds and criteria based on market sector
- **Confidence Scoring**: Provides confidence levels for each classification
- **Evidence-Based Reasoning**: Identifies specific indicators supporting each classification
- **Performance Optimization**: Uses caching and efficient text processing for fast classification
- **Configurable Rules**: Supports custom configuration of thresholds, weights, and indicators

## Classification Categories

### Value Categories

Value classification divides projects into four tiers based on estimated monetary value:

| Category | Default Range | Description |
|----------|---------------|-------------|
| Small | <$2M | Small-scale projects that may be less resource-intensive |
| Medium | $2M-$10M | Mid-sized projects with moderate resource requirements |
| Large | $10M-$50M | Large projects requiring significant resources |
| Major | >$50M | Major projects with highest resource demands and strategic importance |

Different market sectors use different threshold values to account for sector-specific economics.

### Timeline Categories

Timeline classification indicates when a project is likely to move forward:

| Category | Timeframe | Description |
|----------|-----------|-------------|
| Immediate | 0-3 months | Projects already underway or starting within 90 days |
| Short-term | 3-6 months | Projects expected to start within the current/next quarter |
| Mid-term | 6-12 months | Projects planned within the next year |
| Long-term | 12+ months | Projects with timelines extending beyond a year |

The classifier uses both explicit time references (e.g., "next month") and contextual clues (e.g., planning stage indicators) to determine timeline.

### Decision Stages

Decision stage indicates where a project stands in the decision-making process:

| Stage | Description | Key Indicators |
|-------|-------------|----------------|
| Conceptual | Initial concept/vision stage | "concept", "idea", "proposed", "feasibility study" |
| Planning | Active planning/design | "design", "architect", "engineering", "drawings" |
| Approval | Seeking approvals/permits | "permit", "zoning", "review", "commission", "approval" |
| Funding | Securing funding/budget | "funding", "budget", "bonds", "financing", "investment" |
| Implementation | Ready for implementation | "rfp", "bid", "construction", "groundbreaking" |

Each stage has different implications for sales approach and timing.

### Competition Levels

Competition classification estimates the competitive landscape:

| Level | Description | Key Indicators |
|-------|-------------|----------------|
| Low | Few competitors, niche project | "sole source", "specialized", "limited competition", "invited" |
| Medium | Standard competitive field | "competitive", "multiple bidders", "short list", "selected firms" |
| High | Highly competitive project | "highly competitive", "many bidders", "open bid", "public tender" |

The classifier also considers explicit mentions of the number of competitors/bidders when available.

### Priority Levels

Priority classification combines multiple factors to determine overall importance:

| Level | Score Range | Description |
|-------|-------------|-------------|
| Critical | 80-100 | Highest priority, immediate action needed |
| High | 60-79 | High priority, prompt action needed |
| Medium | 40-59 | Standard priority |
| Low | 20-39 | Lower priority, handle when convenient |
| Minimal | 1-19 | Minimal priority, may be deprioritized |

Priority takes into account value, timeline, win probability, and strategic alignment.

## Win Probability Model

The win probability model analyzes multiple factors to estimate the likelihood of winning a project:

| Factor | Weight | Description |
|--------|--------|-------------|
| Market Sector Fit | 20% | Match between project sector and company expertise |
| Geographical Proximity | 15% | Location relevance to company's service area |
| Project Size Fit | 15% | Match between project size and company capabilities |
| Competition Level | 20% | Estimated level of competition |
| Relationship Strength | 15% | Existing relationship with client/owner |
| Timeline Alignment | 15% | Match between project timeline and company capacity |

Each factor is scored from 0.0 to 1.0 and then combined using the weights above to calculate an overall probability.

## Configuration

The classifier can be configured by providing a configuration dictionary during initialization or by creating a configuration file at `config/classification_config.json`.

### Configuration Parameters

#### Value Tiers
```json
"value_tiers": {
    "default": {
        "small": 2000000,      // $2M
        "medium": 10000000,    // $10M
        "large": 50000000      // $50M
    },
    "healthcare": {
        "small": 5000000,      // $5M
        "medium": 20000000,    // $20M
        "large": 100000000     // $100M
    }
}
```

#### Timeline Indicators
```json
"timeline_indicators": {
    "immediate": [
        "immediate", "urgent", "asap", "this month", "next month",
        "within 30 days", "within 60 days", "within 90 days"
    ],
    "short_term": [
        "short-term", "soon", "this quarter", "next quarter",
        "within 6 months", "3-6 months", "coming months"
    ]
}
```

#### Decision Stage Indicators
```json
"decision_stage_indicators": {
    "conceptual": [
        "concept", "vision", "idea", "proposed", "preliminary",
        "exploring", "feasibility study", "initial planning"
    ],
    "planning": [
        "planning", "design", "architect", "engineering",
        "drawings", "blueprint", "schematics"
    ]
}
```

#### Win Probability Factors
```json
"win_probability_factors": {
    "market_sector_fit": 0.20,
    "geographical_proximity": 0.15,
    "project_size_fit": 0.15,
    "competition_level": 0.20,
    "relationship_strength": 0.15,
    "timeline_alignment": 0.15
}
```

#### Priority Scoring
```json
"priority_scoring": {
    "value_weight": 0.30,
    "timeline_weight": 0.25,
    "win_probability_weight": 0.30,
    "strategic_alignment_weight": 0.15
}
```

### Environment Variable Overrides

Configuration can also be adjusted at runtime using environment variables:

- `PERERA_CLASSIFICATION_MODEL_VERSION`: Override model version
- `PERERA_VALUE_TIER_DEFAULT_SMALL`: Override default small value threshold
- `PERERA_WIN_PROB_MARKET_SECTOR_FIT`: Override market sector fit weight

## Integration with Other Components

### Integration with NLP Processor

The classification module uses the NLPProcessor for text analysis. Pass an NLPProcessor instance during initialization:

```python
from perera_lead_scraper.nlp.nlp_processor import NLPProcessor
from perera_lead_scraper.classification.classifier import LeadClassifier

nlp_processor = NLPProcessor()
classifier = LeadClassifier(nlp_processor=nlp_processor)
```

### Integration with Enrichment

Classification works best with enriched lead data. Apply enrichment before classification:

```python
from perera_lead_scraper.enrichment.enrichment import LeadEnricher
from perera_lead_scraper.classification.classifier import LeadClassifier

enricher = LeadEnricher()
classifier = LeadClassifier()

# Process a lead
enriched_lead = enricher.enrich_lead(lead)
classified_lead = classifier.classify_lead(enriched_lead)
```

### Integration with Pipeline

Integrate classification into the extraction pipeline:

```python
from perera_lead_scraper.pipeline.extraction_pipeline import LeadExtractionPipeline
from perera_lead_scraper.classification.classifier import LeadClassifier

classifier = LeadClassifier()

def custom_classify_leads(leads):
    return [classifier.classify_lead(lead) for lead in leads]

# Create pipeline
pipeline = LeadExtractionPipeline()

# Register custom classification function
pipeline.classify_leads = custom_classify_leads
```

## Usage Examples

### Basic Classification

```python
from perera_lead_scraper.classification.classifier import LeadClassifier

# Initialize the classifier
classifier = LeadClassifier()

# Classify a lead
classified_lead = classifier.classify_lead(lead)

# Access classification results
classification = classified_lead.extra_data["classification"]
value_category = classification["value_category"]
timeline_category = classification["timeline_category"]
win_probability = classification["win_probability"]
priority_score = classification["priority_score"]
priority_level = classification["priority_level"]
```

### Extracting Specific Classifications

```python
# Categorize by value
value_category, confidence = classifier.categorize_by_value(lead.estimated_value, lead.market_sector)

# Determine timeline
timeline, confidence, indicators = classifier.categorize_by_timeline(lead.description)

# Determine decision stage
stage, confidence, indicators = classifier.determine_decision_stage(lead.description)

# Assess competition
level, confidence, indicators = classifier.assess_competition(lead.description)

# Calculate win probability
probability, factors = classifier.calculate_win_probability(lead)

# Assign priority
score, level, factors = classifier.assign_priority_score(lead)
```

### Performance Monitoring

```python
# Get performance metrics
metrics = classifier.get_performance_metrics()

# Log metrics
avg_time = metrics["avg_classification_time"]
success_rate = metrics["success_rate"]
confidence_scores = metrics["confidence_scores"]

print(f"Average classification time: {avg_time:.3f}s")
print(f"Classification success rate: {success_rate:.2%}")
```

## Calibration and Validation

To ensure accurate and useful classifications, periodic validation and calibration is recommended:

1. **Win Probability Calibration**: Compare predicted win probabilities with actual win rates every quarter and adjust the model accordingly.

2. **Priority Score Validation**: Track lead outcomes by priority level to confirm that higher-priority leads convert at higher rates.

3. **Confidence Threshold Tuning**: Adjust confidence thresholds based on observed classification accuracy.

4. **Indicator Updates**: Regularly update keyword indicators to match current terminology in the industry and project documentation.

## Troubleshooting

### Common Issues

1. **Low Confidence Scores**
   - Cause: Insufficient or ambiguous information in lead description
   - Solution: Enhance lead data through enrichment before classification

2. **Incorrect Timeline Classification**
   - Cause: Date references may be ambiguous or contradictory
   - Solution: Check timeline indicators and adjust threshold sensitivity

3. **Inaccurate Win Probability**
   - Cause: Missing relationship or competitive information
   - Solution: Ensure lead enrichment captures client relationship data

4. **Slow Classification Performance**
   - Cause: Large text content or inefficient NLP processing
   - Solution: Enable caching and optimize NLP processor configuration

### Logging and Debugging

Classification errors and warnings are logged using the standard logging system. To enable detailed debugging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("perera_lead_scraper.classification")
```

## Advanced Configuration

### Custom Indicator Keywords

You can customize classification indicators by updating the configuration:

```python
config_override = {
    "timeline_indicators": {
        "immediate": [
            "immediate", "urgent", "asap", "current", "active",
            # Add your custom keywords here
        ]
    }
}

classifier = LeadClassifier(config_override=config_override)
```

### Sector-Specific Rules

Configure different rules for each market sector:

```python
config_override = {
    "sector_expertise_levels": {
        "healthcare": 0.9,  # High expertise
        "education": 0.85,
        "commercial": 0.8,
        "industrial": 0.6,  # Lower expertise
    }
}

classifier = LeadClassifier(config_override=config_override)
```

## Future Extensions

The classification module is designed to be extended in the following ways:

1. **Machine Learning Models**: Replace rule-based classifiers with ML models for increased accuracy

2. **Multi-dimensional Classification**: Add more classification dimensions like complexity, risk level, etc.

3. **Historical Data Analysis**: Incorporate past project outcomes to improve win probability prediction

4. **Dynamic Rule Learning**: Automatically adjust rules based on feedback and outcomes