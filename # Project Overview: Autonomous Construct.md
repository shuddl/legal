# Project Overview: Autonomous Construction Lead Generation Agent for Perera Construction (AI Reference v1.1)

**1. Executive Summary & Vision:**

This project aims to build an autonomous software agent that proactively identifies, qualifies, enriches, and delivers high-value, early-stage construction project and real estate development leads directly into Perera Construction's HubSpot CRM.  The target markets for the construction projects are Healthcare, Higher Education, Energy/Utilities, Themed Entertainment, and General Commercial Construction such as tenant improvements and capital projects. The ultimate goal is to significantly reduce manual prospecting efforts and increase the pipeline of relevant opportunities within Perera's target markets and geographical focus (Southern California). Success hinges on the **quality, relevance, and timeliness** of the leads generated.

**2. Core Problem Addressed:**

Manually scanning numerous disparate public sources (city portals, news sites, databases) is time-consuming, inefficient, and prone to missing early indicators of potential projects. Perera needs a systematic, automated way to detect opportunities *before* they become widely known RFPs, allowing for earlier relationship building.

**3. Primary Goal & Key Objectives:**

* **Goal:** Automate the discovery and qualification of actionable, early-stage construction leads aligned with Perera's business profile.
* **Objectives:**
  * Continuously monitor **50-100+** configured public data sources.
  * Accurately extract project-related information (details, location, value, companies).
  * Classify leads by target market sector (**Healthcare, Higher Education, Energy, Entertainment, Commercial**) and location (**Southern California focus**).
  * Filter out irrelevant noise using robust keyword, NLP, and validation logic.
  * Enrich leads with basic company/contact information where possible.
  * Prevent duplicate entries in the system and CRM (**<5%** duplication rate target).
  * Deliver qualified leads meeting defined criteria (**>80%** acceptance rate target) to HubSpot.
  * Operate reliably on a configurable schedule (**>99%** uptime target).

**4. Target Lead Profile (Definition of "High Quality"):**

The system should prioritize leads exhibiting these characteristics:

* **Location Match:** Clearly within specified Southern California counties/cities (configurable).
* **Sector Match:** Falls into one of the **5** target market sectors.
* **Early Stage:** Indicates project is in planning, design, seeking approval, permit application, or pre-bid phase (keywords: "planning", "design review", "entitlement", "permit application", "seeking bids", "approved funding", "future development"). Avoid leads already deep into bidding or under construction unless specified otherwise.
* **Relevance:** High confidence score (**>=0.7**) based on NLP analysis, keyword matching, and validation, indicating a strong likelihood of being a genuine construction opportunity.
* **Key Information:** Ideally contains identifiable project name/description, location address/parcel, owner/developer name, and ideally an estimated value or size indicator (even if rough).
* **Timeliness:** Information is recent (published/updated within **7-14 days**, configurable).
* **Actionability:** Provides enough context for initial outreach or further investigation by Perera's team.

**5. Key Functional Requirements:**

* **Data Acquisition:** Scrape websites (Playwright/Selenium for JS sites), parse RSS/Atom feeds (`feedparser`), interact with APIs.
* **Data Processing:** Extract structured data from unstructured text using NLP (spaCy).
* **Filtering & Classification:** Apply rules, keyword matching, and NLP classification to identify relevant market sector, location, and project intent.
* **Validation:** Check for required fields, validate location against target geography, perform basic timeline checks.
* **Deduplication:** Identify and discard likely duplicates based on URL and content similarity (fuzzy matching **>85%** threshold).
* **Enrichment (Basic):** Attempt to find company website/basic details based on extracted names.
* **CRM Export:** Format and push qualified leads as Companies, Contacts (if found), and Deals (with associated notes/metadata) into HubSpot via its API, including logic to find/update existing records where possible.
* **Scheduling & Orchestration:** Run data acquisition, processing, and export tasks automatically on a configurable schedule (e.g., daily, hourly for specific sources).

**6. Key Non-Functional Requirements:**

* **Reliability:** Robust error handling, retry mechanisms (network/API calls: **3-5** attempts, exponential backoff), graceful failure modes, scheduled operation.
* **Accuracy:** Strive for high precision and recall in NLP tasks (Target: Sector classification F1 **>0.8**, Location NER F1 **>0.7** initially). Ensure qualified lead acceptance rate **>80%**.
* **Maintainability:** Modular codebase (`src` layout), clear separation of concerns, configuration-driven behavior, adherence to coding standards (PEP 8, Black, Ruff, MyPy), comprehensive logging (structured JSON), good documentation.
* **Scalability:** Architecture should support adding new data sources (**100+** target), parsers, and potentially increased processing load over time.
* **Security:** Secure handling of all credentials (API keys, potential logins) via environment variables and referencing; no hardcoding.

**7. Technology Stack (Primary):**

* **Language:** Python **>= 3.9**
* **Web Scraping/Parsing:** Scrapy, Playwright (Async Preferred), Selenium, BeautifulSoup4, feedparser, requests
* **Data Handling:** Pandas (optional), Pydantic (for data models/validation)
* **NLP:** spaCy (**>= 3.x**)
* **Database:** SQLAlchemy (**>= 2.0**) for ORM (with SQLite for local storage/caching initially). Alembic (optional for migrations).
* **CRM Integration:** `hubspot-api-client` (**v7.5.0+**)
* **Scheduling:** APScheduler (or similar lightweight library)
* **API (Optional):** FastAPI, Uvicorn
* **Infrastructure (Optional):** Docker, Docker Compose

**8. Core System Components (Conceptual):**

* Configuration Loader (`config.py`)
* Data Models (`data_models.py`)
* Logging Module (`logger_config.py`)
* Storage Manager (`storage.py`)
* Source Manager (`source_manager.py`)
* Parsers (e.g., `rss_parser.py`)
* Scrapers (e.g., `web_scraper.py` using Playwright/Selenium)
* NLP Processor (`nlp_processor.py`)
* Lead Validator (`lead_validator.py`)
* Processing Pipeline (`processing_pipeline.py`)
* Enrichment Module (`enrichment.py`)
* HubSpot Client (`hubspot_integration.py`)
* HubSpot Mapper (`hubspot_mapper.py`)
* Export Pipeline (`export_pipeline.py`)
* Scheduler (`scheduler.py`)
* Orchestrator (`orchestrator.py`)
* Monitoring Module (`monitoring.py`)
* API Backend (Optional - `api.py`)

**9. Data Sources:**

* **Types:** City Planning Portals, Permit Databases, Construction News Sites, Industry RSS Feeds, Association Websites, Corporate Press Release sections.
* **Initial Scope:** Configure and manage **50-100** diverse, active sources covering the target markets and locations.

**10. CRM Integration (HubSpot):**

* **Objects:** Create/Update Companies, Contacts (if identifiable), Deals. Associate Contacts/Deals with Companies.
* **Data Points:** Map extracted/enriched `Lead` data to standard and custom HubSpot properties (e.g., Project Title, Location, Est. Value, Market Sector, Source URL).
* **Goal:** Provide contextual information within HubSpot; avoid creating low-quality or duplicate records. Use `find_or_create` logic.

**11. Success Metrics (Project Level):**

* **Lead Volume:** **>= 200 Qualified Leads/week** delivered to HubSpot.
* **Lead Qualification Rate:** **> 80%** of delivered leads meet qualification criteria upon review.
* **HubSpot Duplication Rate:** **< 5%** duplicate Companies/Contacts created by the agent (30-day rolling).
* **Efficiency Gain:** **> 70%** reduction in manual prospecting time for target markets (user feedback).
* **System Reliability:** **> 99%** pipeline uptime; **> 90%** source connectivity success rate.

**12. Deliverables:**

* Fully functional, documented Python codebase adhering to standards.
* Configuration files for **50-100** initial sources, keywords, and selectors.
* Scripts for initialization, testing (unit, integration, E2E, accuracy).
* Reliable export mechanism to HubSpot.
* Comprehensive documentation (README, Architecture, Deployment, Maintenance).
* (Optional but Recommended) Docker setup (`Dockerfile`, `docker-compose.yml`).

**13. Scope Boundaries (Explicitly Out):**

* Complex multi-user authentication systems.

* Integrations with systems other than HubSpot.

* Features not directly related to construction lead generation for the specified markets/locations.
