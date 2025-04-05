# Southern California Lead Sources

This document provides details on the configured Southern California construction lead sources integrated into the Perera Construction Lead Scraper.

## Overview

The system is configured with multiple Southern California-specific data sources to capture construction leads within a three-hour radius of Los Angeles. These sources are categorized into several types:

- **City Planning Portals**: Direct access to city/county planning department data
- **RSS Feeds**: Automated content from news and industry sources
- **Websites**: Structured data extraction from relevant websites
- **Bidding Platforms**: Construction project bid opportunities
- **Government Sources**: Public works and infrastructure projects

## Configured Source Categories

### County Planning Departments

| County | Source | Type | Notes |
|--------|--------|------|-------|
| Los Angeles | `los_angeles_city_planning` | City Portal | LA DBS permit data |
| Orange | `orange_county_planning` | City Portal | Planning & public hearings |
| San Diego | `san_diego_city_planning` | City Portal | OpenDSD approvals |
| Riverside | `riverside_city_planning` | City Portal | Development projects |
| San Bernardino | `san_bernardino_county_planning` | City Portal | Planning notices |
| Ventura | `ventura_county_planning` | City Portal | Planning div. hearings |
| Santa Barbara | `santa_barbara_planning` | City Portal | Development review |

### Major Cities

| City | Source | Type | Notes |
|------|--------|------|-------|
| Los Angeles | `los_angeles_city_planning` | City Portal | City of LA permits |
| Long Beach | `long_beach_city_planning` | City Portal | Planning Division portal |
| Irvine | `irvine_city_planning` | City Portal | eTrakit system |
| Anaheim | `anaheim_city_planning` | City Portal | Planning Division |
| Santa Ana | `santa_ana_city_planning` | City Portal | Current projects |
| Riverside | `riverside_city_planning` | City Portal | Current projects |
| San Diego | `san_diego_city_planning` | City Portal | OpenDSD system |
| Bakersfield | `bakersfield_planning` | City Portal | Planning Division |
| Palm Springs | `palm_springs_planning` | City Portal | Current projects |

### Infrastructure & Government

| Source | Type | Description |
|--------|------|-------------|
| `la_county_public_works` | Website | LA County Public Works contracting opportunities |
| `caltrans_projects` | Website | Statewide transportation projects |
| `la_metro_projects` | Website | LA Metro transit projects |
| `ca_dept_gen_services` | Website | State building code & regulations |
| `us_army_corps_engineers` | Website | Federal infrastructure projects |

### Bidding & Industry Platforms

| Source | Type | Description |
|--------|------|-------------|
| `california_construction_bidding` | RSS | eBidboard California construction bids |
| `socal_builders_exchange` | Website | Builders Exchange of Southern California plan room |
| `socal_bid_network` | Website | BidNet Direct California region |
| `socal_agc_chapter` | RSS | Associated General Contractors news & projects |

### Regional News & Industry Publications

| Source | Type | Description |
|--------|------|-------------|
| `california_builder_developer` | RSS | Builder.Media news feed |
| `los_angeles_business_journal` | RSS | Business news with project coverage |
| `constructech` | RSS | Construction technology news |
| `highways_today` | RSS | Infrastructure & transportation projects |

## Geographical Coverage

The configured sources provide comprehensive coverage of construction projects within a three-hour radius of Los Angeles, including:

- **Los Angeles Basin**: Los Angeles, Long Beach, Pasadena
- **Orange County**: Irvine, Anaheim, Santa Ana, Newport Beach
- **Inland Empire**: Riverside, San Bernardino, Ontario
- **San Diego Region**: San Diego, Oceanside, Escondido
- **Central Coast**: Santa Barbara, Ventura
- **Central Valley**: Bakersfield

## Running Scrapers for SoCal Sources

To scrape Southern California sources specifically:

```bash
# Run all SoCal-tagged sources
python -m src.perera_lead_scraper.run_orchestrator --tag socal

# Run specific city portal
python -m src.perera_lead_scraper.run_orchestrator --source los_angeles_city_planning
```

## Adding New SoCal Sources

To add additional Southern California sources:

1. Identify the data source URL and determine its type (RSS, city portal, website)
2. Add the source configuration to `config/sources.json`
3. For city portals, add corresponding selectors to `config/city_portals.json`
4. Test the source with `python -m src.perera_lead_scraper.run_orchestrator --source [source_name]`

## Lead Quality Assessment

The system has been tuned to identify emerging construction projects within Southern California using the following criteria:

- **Geographical Relevance**: Within ~3 hour radius of Los Angeles
- **Project Stage**: Focus on early-stage projects (planning, permitting)
- **Value Threshold**: Prioritizes projects meeting minimum value thresholds
- **Project Type**: Commercial, institutional, industrial, infrastructure
- **Data Freshness**: Configured for recent (7-30 day) project announcements

Sources are validated against the system's benchmark performance metrics described in `SYSTEM_PERFORMANCE_BENCHMARK.md`.