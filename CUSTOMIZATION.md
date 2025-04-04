# Perera Construction Lead Scraper - Customization Guide

This document provides detailed instructions for extending and customizing the Perera Construction Lead Scraper to meet your specific requirements.

## Table of Contents

- [Data Source Customization](#data-source-customization)
- [Keyword Dictionary Customization](#keyword-dictionary-customization)
- [Sector-Specific Configuration](#sector-specific-configuration)
- [Selector Maintenance](#selector-maintenance)
- [HubSpot Field Mapping](#hubspot-field-mapping)
- [Extension Points](#extension-points)

## Data Source Customization

The Lead Scraper is designed to be extensible with new data sources. This section explains how to add and customize data sources.

### Adding a New Data Source

1. **Create a new Python module** in the `src/perera_lead_scraper/sources` directory:

```python
# src/perera_lead_scraper/sources/my_custom_source.py

from typing import List, Dict, Any, Optional
from datetime import datetime

from perera_lead_scraper.sources.base import BaseDataSource
from perera_lead_scraper.models import Lead

class MyCustomSource(BaseDataSource):
    """
    Custom data source implementation for [description].
    """
    
    source_type = "my_custom_source"  # Unique identifier for this source type
    source_name = "My Custom Source"  # Human-readable name
    
    def __init__(self, config: Dict[str, Any] = None):
        """
        Initialize the data source with configuration.
        
        Args:
            config: Configuration dictionary with source-specific settings
        """
        super().__init__(config or {})
        
        # Initialize source-specific attributes
        self.url = config.get("url", "https://example.com")
        self.credentials = config.get("credentials", {})
        
        # Set up any additional required attributes
        self.session = None
    
    def connect(self) -> bool:
        """
        Establish connection to the data source.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            # Implement connection logic (e.g., create session, authenticate)
            import requests
            
            self.session = requests.Session()
            
            # Handle authentication if needed
            if self.credentials:
                username = self.credentials.get("username")
                password = self.credentials.get("password")
                
                if username and password:
                    # Example authentication - adjust for your source
                    auth_url = f"{self.url}/auth"
                    resp = self.session.post(auth_url, json={
                        "username": username,
                        "password": password
                    })
                    resp.raise_for_status()
            
            return True
        
        except Exception as e:
            self.logger.error(f"Failed to connect to {self.source_name}: {str(e)}")
            return False
    
    def fetch_data(self) -> List[Dict[str, Any]]:
        """
        Fetch raw lead data from the source.
        
        Returns:
            List[Dict[str, Any]]: List of raw lead data dictionaries
        """
        if not self.session:
            if not self.connect():
                return []
        
        try:
            # Implement data fetching logic
            leads_url = f"{self.url}/api/leads"
            
            # Add any required query parameters
            params = {
                "region": self.config.get("region", "all"),
                "limit": self.config.get("max_leads", 100)
            }
            
            resp = self.session.get(leads_url, params=params)
            resp.raise_for_status()
            
            # Process the response into a list of dictionaries
            data = resp.json()
            
            # Map response data to our expected format
            # This is source-specific and will vary
            raw_leads = []
            for item in data.get("items", []):
                raw_lead = {
                    "name": item.get("title"),
                    "company": item.get("company_name"),
                    "email": item.get("contact_email"),
                    "phone": item.get("contact_phone"),
                    "address": item.get("location"),
                    "project_type": item.get("type"),
                    "project_value": item.get("estimated_value"),
                    "project_description": item.get("description"),
                    "source_url": item.get("url"),
                    "raw_data": item  # Store the complete raw data for reference
                }
                raw_leads.append(raw_lead)
            
            return raw_leads
        
        except Exception as e:
            self.logger.error(f"Failed to fetch data from {self.source_name}: {str(e)}")
            return []
    
    def process_lead(self, raw_lead: Dict[str, Any]) -> Optional[Lead]:
        """
        Process a raw lead dictionary into a Lead object.
        
        Args:
            raw_lead: Dictionary containing raw lead data
        
        Returns:
            Optional[Lead]: Processed Lead object or None if invalid
        """
        try:
            # Create a Lead object from the raw data
            lead = Lead(
                name=raw_lead.get("name", ""),
                company=raw_lead.get("company"),
                email=raw_lead.get("email"),
                phone=raw_lead.get("phone"),
                address=raw_lead.get("address"),
                project_type=raw_lead.get("project_type"),
                project_value=float(raw_lead.get("project_value", 0)) if raw_lead.get("project_value") else None,
                project_description=raw_lead.get("project_description"),
                source=self.source_type,
                source_url=raw_lead.get("source_url"),
                timestamp=datetime.now()
            )
            
            # Apply any source-specific processing or enrichment
            self._enrich_lead(lead, raw_lead)
            
            # Calculate quality score
            lead.quality_score = self._calculate_quality_score(lead)
            
            return lead
        
        except Exception as e:
            self.logger.error(f"Failed to process lead: {str(e)}")
            return None
    
    def _enrich_lead(self, lead: Lead, raw_lead: Dict[str, Any]) -> None:
        """
        Enrich a lead with additional information.
        
        Args:
            lead: Lead object to enrich
            raw_lead: Raw lead data dictionary
        """
        # Implement lead enrichment logic
        # This could include:
        # - Extracting additional fields
        # - Normalizing data
        # - Looking up additional information
        pass
    
    def _calculate_quality_score(self, lead: Lead) -> float:
        """
        Calculate a quality score for the lead.
        
        Args:
            lead: Lead object to score
        
        Returns:
            float: Quality score between 0 and 100
        """
        # Implement quality scoring logic
        score = 50.0  # Default score
        
        # Add points for various factors
        if lead.project_value and lead.project_value > 1000000:
            score += 20
        
        if lead.email:
            score += 10
        
        if lead.phone:
            score += 10
        
        if lead.project_description and len(lead.project_description) > 100:
            score += 10
        
        # Cap at 100
        return min(score, 100.0)
```

2. **Register the new source** in `src/perera_lead_scraper/sources/__init__.py`:

```python
from perera_lead_scraper.sources.base import BaseDataSource
from perera_lead_scraper.sources.government_bids import GovernmentBidsSource
from perera_lead_scraper.sources.permit_data import PermitDataSource
from perera_lead_scraper.sources.my_custom_source import MyCustomSource  # Import your new source

# Register all available sources
AVAILABLE_SOURCES = {
    GovernmentBidsSource.source_type: GovernmentBidsSource,
    PermitDataSource.source_type: PermitDataSource,
    MyCustomSource.source_type: MyCustomSource,  # Add your new source
}

def get_available_sources():
    """Get a list of available source types."""
    return list(AVAILABLE_SOURCES.keys())

def get_source_class(source_type):
    """Get the class for a specific source type."""
    return AVAILABLE_SOURCES.get(source_type)
```

3. **Configure your new source** via the API or configuration file:

```json
{
  "sources": [
    {
      "name": "My Custom Source",
      "type": "my_custom_source",
      "url": "https://example.com",
      "credentials": {
        "username": "your_username",
        "password": "your_password"
      },
      "schedule": "0 */6 * * *",
      "config": {
        "region": "Northeast",
        "max_leads": 200
      },
      "is_active": true
    }
  ]
}
```

### Data Source Configuration Options

Each data source can be configured with the following common options:

| Option | Description | Default |
|--------|-------------|---------|
| name | Human-readable name for the source | Source type name |
| type | Source type identifier | Required |
| url | Base URL for the source | Source-specific default |
| credentials | Authentication credentials | {} |
| schedule | Cron expression for scheduling | Required |
| config | Source-specific configuration | {} |
| is_active | Whether the source is active | true |

Each source type may have additional specific configuration options in the `config` object.

### Customizing Data Extraction

To customize how data is extracted from a specific source, you can override the following methods in your source class:

- `fetch_data()`: Change how raw data is fetched from the source
- `process_lead()`: Customize how raw data is processed into leads
- `_enrich_lead()`: Add source-specific enrichment logic
- `_calculate_quality_score()`: Customize quality scoring for this source

## Keyword Dictionary Customization

The Lead Scraper uses keyword dictionaries to categorize and score leads. You can customize these dictionaries to improve lead processing for your specific industry focus.

### Project Type Keywords

To customize project type detection, edit the keyword dictionary in `src/perera_lead_scraper/processing/dictionaries.py`:

```python
PROJECT_TYPE_KEYWORDS = {
    "commercial": [
        "office building", "retail", "shopping center", "mall", "restaurant",
        "hotel", "motel", "store", "warehouse", "industrial", "manufacturing"
    ],
    "residential": [
        "housing", "apartment", "condominium", "condo", "house", "home",
        "residential", "multifamily", "single family", "townhouse", "townhome"
    ],
    "healthcare": [
        "hospital", "medical", "clinic", "healthcare", "nursing home",
        "assisted living", "doctor", "dental", "pharmacy"
    ],
    "education": [
        "school", "university", "college", "campus", "education",
        "classroom", "dormitory", "dorm", "academic", "kindergarten", "k-12"
    ],
    "infrastructure": [
        "road", "highway", "bridge", "infrastructure", "utility",
        "pipeline", "water", "sewer", "drainage", "transportation"
    ],
    # Add your custom project type
    "data_center": [
        "data center", "server", "computing", "it infrastructure", "colocation",
        "hosting facility", "telecommunications", "network"
    ]
}
```

### Relevance Score Keywords

Similarly, you can customize the keywords used for relevance scoring:

```python
RELEVANCE_SCORE_KEYWORDS = {
    "high_relevance": [
        "new construction", "development", "build", "breaking ground",
        "construction project", "general contractor", "construction management"
    ],
    "medium_relevance": [
        "renovation", "remodel", "expansion", "addition", "upgrade",
        "improvement", "retrofit", "modernization"
    ],
    "low_relevance": [
        "repair", "maintenance", "service", "inspection", "study",
        "assessment", "survey", "consulting"
    ]
}
```

### Region-Specific Keywords

You can add region-specific keywords for better geographical targeting:

```python
REGION_KEYWORDS = {
    "northeast": [
        "new york", "boston", "philadelphia", "maine", "new hampshire",
        "vermont", "massachusetts", "rhode island", "connecticut",
        "new jersey", "pennsylvania"
    ],
    "southeast": [
        "florida", "georgia", "alabama", "mississippi", "louisiana",
        "south carolina", "north carolina", "tennessee", "kentucky",
        "virginia", "west virginia", "arkansas"
    ],
    # Add your custom region
    "pacific_northwest": [
        "washington", "oregon", "idaho", "montana", "seattle",
        "portland", "spokane", "tacoma", "olympia", "boise"
    ]
}
```

## Sector-Specific Configuration

You can customize the lead scraper to focus on specific construction sectors by adjusting the sector configuration.

### Sector Configuration File

Create or edit `src/perera_lead_scraper/config/sectors.yml`:

```yaml
sectors:
  healthcare:
    enabled: true
    priority: 10
    min_project_value: 1000000
    keywords:
      - hospital
      - medical center
      - clinic
      - healthcare facility
      - nursing home
      - assisted living
    excluded_keywords:
      - residential healthcare
      - home healthcare
    quality_boost: 15

  data_centers:
    enabled: true
    priority: 8
    min_project_value: 5000000
    keywords:
      - data center
      - server facility
      - co-location
      - network operations center
      - telecom center
    quality_boost: 10

  education:
    enabled: true
    priority: 6
    min_project_value: 500000
    keywords:
      - school
      - university
      - college
      - campus
      - education center
      - classroom building
    quality_boost: 5
```

### Applying Sector Configuration

The system will automatically load sector configurations from the file. To customize how sectors are applied, you can modify the sector detection logic in `src/perera_lead_scraper/processing/sector_analyzer.py`:

```python
def detect_sector(lead, sectors_config):
    """
    Detect the sector for a lead based on keywords and project attributes.
    
    Args:
        lead: The lead object to analyze
        sectors_config: Dictionary of sector configurations
    
    Returns:
        tuple: (sector_name, confidence_score)
    """
    best_match = (None, 0)
    
    for sector_name, config in sectors_config.items():
        if not config.get('enabled', True):
            continue
            
        # Skip if project value is below sector minimum
        if (lead.project_value and config.get('min_project_value') and
                lead.project_value < config.get('min_project_value')):
            continue
            
        # Check for keywords in project description
        score = 0
        if lead.project_description:
            desc_lower = lead.project_description.lower()
            
            # Add points for each keyword match
            for keyword in config.get('keywords', []):
                if keyword.lower() in desc_lower:
                    score += 1
                    
            # Subtract points for excluded keywords
            for keyword in config.get('excluded_keywords', []):
                if keyword.lower() in desc_lower:
                    score -= 2
        
        # Check for keywords in name
        if lead.name:
            name_lower = lead.name.lower()
            for keyword in config.get('keywords', []):
                if keyword.lower() in name_lower:
                    score += 2  # Higher weight for name matches
        
        # Factor in sector priority
        score *= config.get('priority', 1)
        
        # Update best match if this sector scored higher
        if score > best_match[1]:
            best_match = (sector_name, score)
    
    # Calculate confidence (normalize score)
    sector, score = best_match
    if sector and score > 0:
        # Apply quality boost to the lead
        boost = sectors_config[sector].get('quality_boost', 0)
        lead.quality_score = min(100, (lead.quality_score or 50) + boost)
        
        # Return detected sector and confidence
        confidence = min(100, score * 10)
        return (sector, confidence)
    
    return (None, 0)  # No sector detected
```

## Selector Maintenance

Data sources that scrape web pages often rely on CSS or XPath selectors to extract data. These selectors may need to be updated as websites change.

### Selector Configuration

Selectors are typically defined in source-specific configuration files or within the source class. Here's how to update selectors for a web scraping source:

1. **Locate the selector configuration** in the source class:

```python
class GovernmentBidsSource(BaseDataSource):
    # ...
    
    def __init__(self, config=None):
        super().__init__(config or {})
        
        # Default selectors - can be overridden in config
        self.selectors = {
            "bid_items": ".bid-listing .bid-item",
            "title": ".bid-title",
            "description": ".bid-description",
            "value": ".bid-value",
            "deadline": ".bid-deadline",
            "contact": ".contact-info"
        }
        
        # Override defaults with any provided in config
        if config and "selectors" in config:
            self.selectors.update(config["selectors"])
```

2. **Update selectors** in your source configuration:

```json
{
  "sources": [
    {
      "name": "Government Bids",
      "type": "government_bids",
      "url": "https://example.com/bids",
      "config": {
        "selectors": {
          "bid_items": ".listings .bid-card",  # Updated selector
          "title": "h3.card-title",            # Updated selector
          "description": ".card-description p",
          "value": ".card-details .value-text",
          "deadline": ".card-details .deadline-text",
          "contact": ".card-footer .contact"
        }
      }
    }
  ]
}
```

### Testing Selectors

To test if your selectors are working correctly:

1. Use the built-in selector testing utility:

```bash
python -m src.perera_lead_scraper.cli test-selectors --source-id SOURCE_ID
```

2. Or programmatically:

```python
from perera_lead_scraper.utils.selector_tester import test_selectors

results = test_selectors("government_bids", {
    "bid_items": ".listings .bid-card",
    "title": "h3.card-title"
})

for selector, result in results.items():
    print(f"Selector: {selector}")
    print(f"  Found: {result['count']} matches")
    print(f"  Sample: {result['sample']}")
    print()
```

### Selector Recommendations

For robust web scraping:

1. **Use specific selectors** that target unique elements or combinations of classes
2. **Avoid relying on position-based selectors** (like `:nth-child`) which are brittle
3. **Prefer CSS selectors** over XPath when possible for readability
4. **Include fallback selectors** for critical data points
5. **Consider using data attributes** if you can work with the website owner

## HubSpot Field Mapping

The lead scraper integrates with HubSpot CRM for lead export. You can customize the field mapping to match your HubSpot instance.

### Default Field Mapping

The default mapping is defined in `src/perera_lead_scraper/export/hubspot.py`:

```python
DEFAULT_FIELD_MAPPING = {
    # Contact properties
    "email": "email",
    "name": "firstname",  # We'll split the name if possible
    "company": "company",
    "phone": "phone",
    
    # Deal properties
    "name": "dealname",
    "project_type": "pipeline",  # Maps to pipeline in HubSpot
    "project_value": "amount",
    "project_description": "description",
    "address": "address",
    "quality_score": "lead_quality_score",  # Custom property
    "source": "lead_source",
    "source_url": "source_url"  # Custom property
}
```

### Custom Field Mapping

To customize the field mapping, create a custom mapping in your configuration:

```json
{
  "hubspot": {
    "api_key": "your_hubspot_api_key",
    "field_mapping": {
      "email": "email",
      "name": "firstname", 
      "company": "company",
      "phone": "mobilephone",  # Changed from phone to mobilephone
      "name": "dealname",
      "project_type": "project_type_custom",  # Custom property
      "project_value": "project_budget",      # Custom property
      "project_description": "project_notes",  # Custom property
      "address": "project_location",          # Custom property
      "quality_score": "lead_score",          # Custom property
      "source": "lead_source",
      "source_url": "source_website"          # Custom property
    },
    "deal_stage": "appointmentscheduled",
    "deal_pipeline": "default"
  }
}
```

### Creating Custom Properties in HubSpot

Before using custom properties, you need to create them in your HubSpot account:

1. Log in to your HubSpot account
2. Go to Settings > Properties
3. Click "Create property"
4. Fill in the details:
   - Object type: Contact or Deal
   - Group: Lead Information (or create a custom group)
   - Label: Your custom property name (e.g., "Project Budget")
   - Field type: Choose appropriate type (text, number, etc.)
5. Save the property

### Pipeline and Stage Mapping

You can also customize how project types map to HubSpot pipelines and stages:

```json
{
  "hubspot": {
    "pipeline_mapping": {
      "commercial": {
        "pipeline": "commercial_projects",
        "stage": "qualificationready"
      },
      "residential": {
        "pipeline": "residential_projects",
        "stage": "appointmentscheduled"
      },
      "healthcare": {
        "pipeline": "healthcare_projects",
        "stage": "qualificationready"
      },
      "default": {
        "pipeline": "default",
        "stage": "appointmentscheduled"
      }
    }
  }
}
```

## Extension Points

The Lead Scraper is designed with several extension points that allow you to customize behavior without modifying core code.

### Custom Lead Processor

You can create a custom lead processor to add specialized processing logic:

1. Create a processor class in `src/perera_lead_scraper/processing/custom_processor.py`:

```python
from perera_lead_scraper.processing.base_processor import BaseProcessor

class CustomProcessor(BaseProcessor):
    """
    Custom lead processor with specialized logic.
    """
    
    def process(self, lead):
        """
        Apply custom processing to a lead.
        
        Args:
            lead: The lead to process
            
        Returns:
            The processed lead
        """
        # Your custom processing logic
        
        # Example: Extract company size from description
        if lead.project_description:
            desc_lower = lead.project_description.lower()
            
            if "large corporation" in desc_lower or "fortune 500" in desc_lower:
                lead.add_metadata("company_size", "large")
            elif "small business" in desc_lower or "startup" in desc_lower:
                lead.add_metadata("company_size", "small")
            elif "mid-size" in desc_lower or "medium size" in desc_lower:
                lead.add_metadata("company_size", "medium")
        
        # Example: Categorize by budget tier
        if lead.project_value:
            if lead.project_value < 100000:
                lead.add_metadata("budget_tier", "small")
            elif lead.project_value < 1000000:
                lead.add_metadata("budget_tier", "medium")
            else:
                lead.add_metadata("budget_tier", "large")
        
        return lead
```

2. Register your processor in `src/perera_lead_scraper/processing/__init__.py`:

```python
from perera_lead_scraper.processing.base_processor import BaseProcessor
from perera_lead_scraper.processing.quality_processor import QualityProcessor
from perera_lead_scraper.processing.enrichment_processor import EnrichmentProcessor
from perera_lead_scraper.processing.custom_processor import CustomProcessor

DEFAULT_PROCESSORS = [
    EnrichmentProcessor,
    QualityProcessor,
    CustomProcessor  # Add your custom processor
]
```

### Custom Export Format

You can add support for a custom export format:

1. Create an exporter class in `src/perera_lead_scraper/export/custom_format.py`:

```python
from typing import List, Dict, Any
import json

from perera_lead_scraper.export.base_exporter import BaseExporter
from perera_lead_scraper.models import Lead

class CustomFormatExporter(BaseExporter):
    """
    Exporter for a custom file format.
    """
    
    format_name = "custom"  # Register this name for the export API
    
    def export(self, leads: List[Lead], output_path: str) -> str:
        """
        Export leads to a custom format.
        
        Args:
            leads: List of leads to export
            output_path: Path where the export file will be saved
            
        Returns:
            str: Path to the exported file
        """
        # Convert leads to your custom format
        output_data = {
            "meta": {
                "version": "1.0",
                "exported_at": self.get_timestamp(),
                "lead_count": len(leads)
            },
            "leads": []
        }
        
        for lead in leads:
            # Format each lead according to your requirements
            lead_data = {
                "id": lead.id,
                "basic_info": {
                    "name": lead.name,
                    "company": lead.company,
                    "contact": {
                        "email": lead.email,
                        "phone": lead.phone
                    }
                },
                "project": {
                    "title": lead.name,
                    "type": lead.project_type,
                    "value": lead.project_value,
                    "description": lead.project_description,
                    "location": lead.address
                },
                "metadata": {
                    "source": lead.source,
                    "source_url": lead.source_url,
                    "quality_score": lead.quality_score,
                    "status": lead.status,
                    "discovered_at": lead.timestamp.isoformat() if lead.timestamp else None
                }
            }
            
            # Add any custom metadata
            if hasattr(lead, "metadata") and lead.metadata:
                lead_data["custom_data"] = lead.metadata
                
            output_data["leads"].append(lead_data)
        
        # Write to file
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
            
        return output_path
```

2. Register your exporter in `src/perera_lead_scraper/export/__init__.py`:

```python
from perera_lead_scraper.export.csv_exporter import CsvExporter
from perera_lead_scraper.export.json_exporter import JsonExporter
from perera_lead_scraper.export.excel_exporter import ExcelExporter
from perera_lead_scraper.export.hubspot_exporter import HubSpotExporter
from perera_lead_scraper.export.custom_format import CustomFormatExporter

EXPORTERS = {
    "csv": CsvExporter,
    "json": JsonExporter,
    "xlsx": ExcelExporter,
    "hubspot": HubSpotExporter,
    "custom": CustomFormatExporter  # Register your custom exporter
}
```

### Custom Notification Channel

You can add a custom notification channel for alerts:

1. Create a notification class in `src/perera_lead_scraper/notifications/custom_channel.py`:

```python
from typing import Dict, Any
import requests

from perera_lead_scraper.notifications.base_channel import BaseNotificationChannel

class CustomNotificationChannel(BaseNotificationChannel):
    """
    Custom notification channel (e.g., Slack, Microsoft Teams, etc.).
    """
    
    channel_type = "custom"  # Register this channel type
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.webhook_url = config.get("webhook_url")
        self.username = config.get("username", "Lead Scraper Bot")
        self.verify_ssl = config.get("verify_ssl", True)
    
    def send(self, subject: str, message: str, level: str = "info", 
             metadata: Dict[str, Any] = None) -> bool:
        """
        Send a notification via the custom channel.
        
        Args:
            subject: Notification subject/title
            message: Notification body text
            level: Severity level (info, warning, error, critical)
            metadata: Additional metadata for the notification
            
        Returns:
            bool: True if sent successfully, False otherwise
        """
        if not self.webhook_url:
            self.logger.error("Webhook URL not configured for custom notification channel")
            return False
            
        try:
            # Format the message for your service (this example is for Slack)
            payload = {
                "username": self.username,
                "text": f"*{subject}*\n{message}",
                "attachments": []
            }
            
            # Add color based on level
            color = {
                "info": "#36a64f",  # green
                "warning": "#daa038",  # yellow
                "error": "#d00000",  # red
                "critical": "#7a0000"  # dark red
            }.get(level, "#36a64f")
            
            # Add metadata as attachment if provided
            if metadata:
                fields = []
                for key, value in metadata.items():
                    fields.append({
                        "title": key,
                        "value": str(value),
                        "short": len(str(value)) < 20
                    })
                
                payload["attachments"].append({
                    "color": color,
                    "fields": fields,
                    "footer": "Lead Scraper Notification",
                    "ts": int(time.time())
                })
            
            # Send the notification
            response = requests.post(
                self.webhook_url,
                json=payload,
                verify=self.verify_ssl,
                timeout=10
            )
            response.raise_for_status()
            
            self.logger.info(f"Sent notification via custom channel: {subject}")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to send notification via custom channel: {str(e)}")
            return False
```

2. Register your notification channel in `src/perera_lead_scraper/notifications/__init__.py`:

```python
from perera_lead_scraper.notifications.email_channel import EmailNotificationChannel
from perera_lead_scraper.notifications.webhook_channel import WebhookNotificationChannel
from perera_lead_scraper.notifications.custom_channel import CustomNotificationChannel

NOTIFICATION_CHANNELS = {
    "email": EmailNotificationChannel,
    "webhook": WebhookNotificationChannel,
    "custom": CustomNotificationChannel  # Register your custom channel
}
```

3. Configure your custom notification channel in the configuration:

```json
{
  "notifications": {
    "channels": {
      "custom": {
        "enabled": true,
        "webhook_url": "https://hooks.slack.com/services/your/webhook/url",
        "username": "Lead Scraper Bot",
        "verify_ssl": true
      }
    },
    "alerts": {
      "critical_error": {
        "channels": ["email", "custom"],
        "subject": "CRITICAL: Lead Scraper Error",
        "level": "critical"
      }
    }
  }
}
```