#!/usr/bin/env python3
"""
API Backend for Perera Construction Lead Scraper.

This module provides a FastAPI implementation that exposes the lead scraper
functionality through RESTful API endpoints, including lead management,
data source configuration, system monitoring, and export functionality.
"""

import os
import time
import uuid
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from functools import lru_cache

import fastapi
from fastapi import FastAPI, Depends, HTTPException, status, Request, BackgroundTasks
from fastapi.security.api_key import APIKeyHeader, APIKey
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator, root_validator

# Import project components
from perera_lead_scraper.orchestrator import LeadGenerationOrchestrator
from perera_lead_scraper.storage import LeadStorage
from perera_lead_scraper.sources import BaseDataSource, get_available_sources
from perera_lead_scraper.export import ExportManager
from perera_lead_scraper.config import config
from perera_lead_scraper.monitoring.monitoring import SystemMonitor

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("api")

# API Key authentication setup
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

# Rate limiting configuration
RATE_LIMIT_WINDOW = 60  # 1 minute window
MAX_REQUESTS_PER_WINDOW = 100
rate_limit_storage: Dict[str, Dict[str, Union[int, float]]] = {}

# Initialize FastAPI application
app = FastAPI(
    title="Perera Construction Lead Scraper API",
    description="API for managing construction lead generation and processing",
    version="1.0.0",
    docs_url=None,  # Disable the default docs to use custom endpoint with API key auth
    redoc_url=None,  # Disable the default redoc to use custom endpoint with API key auth
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=getattr(config, "cors_allow_origins", ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


#----------------
# Pydantic Models
#----------------

class HealthStatus(BaseModel):
    status: str
    version: str
    uptime: float
    timestamp: datetime
    components: Dict[str, Dict[str, Any]]


class LeadBase(BaseModel):
    name: str
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    project_type: Optional[str] = None
    project_value: Optional[float] = None
    project_description: Optional[str] = None
    source: str
    source_url: Optional[str] = None
    timestamp: datetime
    quality_score: Optional[float] = None
    status: Optional[str] = "new"
    notes: Optional[str] = None
    
    class Config:
        orm_mode = True


class Lead(LeadBase):
    id: str


class LeadCreate(LeadBase):
    pass


class LeadUpdate(BaseModel):
    name: Optional[str] = None
    company: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    project_type: Optional[str] = None
    project_value: Optional[float] = None
    project_description: Optional[str] = None
    quality_score: Optional[float] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    
    @root_validator
    def check_not_empty(cls, values):
        if not any(values.values()):
            raise ValueError("At least one field must be provided for update")
        return values


class PaginatedLeads(BaseModel):
    items: List[Lead]
    total: int
    page: int
    size: int
    pages: int


class DataSourceBase(BaseModel):
    name: str
    type: str
    url: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None
    schedule: Optional[str] = None  # Cron expression
    config: Optional[Dict[str, Any]] = None
    is_active: bool = True


class DataSource(DataSourceBase):
    id: str
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    status: str = "configured"
    lead_count: int = 0


class DataSourceCreate(DataSourceBase):
    @validator('type')
    def validate_source_type(cls, v):
        available_sources = get_available_sources()
        if v not in available_sources:
            raise ValueError(f"Source type must be one of: {', '.join(available_sources)}")
        return v


class DataSourceUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    credentials: Optional[Dict[str, Any]] = None
    schedule: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None

    @root_validator
    def check_not_empty(cls, values):
        if not any(values.values()):
            raise ValueError("At least one field must be provided for update")
        return values


class SystemMetrics(BaseModel):
    cpu_usage: float
    memory_usage: float
    disk_usage: float
    lead_count: int
    avg_processing_time: float
    success_rate: float
    active_sources: int
    recent_errors: List[Dict[str, Any]]
    last_updated: datetime


class ExportRequest(BaseModel):
    format: str = "csv"
    filter: Optional[Dict[str, Any]] = None
    destination: Optional[str] = None  # Email or other destination
    
    @validator('format')
    def validate_format(cls, v):
        if v not in ["csv", "json", "xlsx", "hubspot"]:
            raise ValueError("Format must be one of: csv, json, xlsx, hubspot")
        return v


class ExportResponse(BaseModel):
    job_id: str
    status: str
    message: str
    timestamp: datetime


class Settings(BaseModel):
    sources_check_interval: int = Field(..., description="Interval in seconds for checking data sources")
    export_interval: int = Field(..., description="Interval in seconds for automatic exports")
    hubspot_api_key: Optional[str] = Field(None, description="HubSpot API key for CRM export")
    export_email: Optional[str] = Field(None, description="Email for receiving exports")
    quality_threshold: float = Field(..., description="Minimum quality score for leads")
    enable_automatic_exports: bool = Field(..., description="Enable automatic exports")
    monitoring_metrics_interval: int = Field(..., description="Interval in seconds for metrics collection")
    notification_email: Optional[str] = Field(None, description="Email for system notifications")
    max_leads_per_source: Optional[int] = Field(None, description="Maximum leads to process per source")
    retention_days: int = Field(..., description="Days to retain leads before archiving")


class SettingsUpdate(BaseModel):
    sources_check_interval: Optional[int] = None
    export_interval: Optional[int] = None
    hubspot_api_key: Optional[str] = None
    export_email: Optional[str] = None
    quality_threshold: Optional[float] = None
    enable_automatic_exports: Optional[bool] = None
    monitoring_metrics_interval: Optional[int] = None
    notification_email: Optional[str] = None
    max_leads_per_source: Optional[int] = None
    retention_days: Optional[int] = None
    
    @root_validator
    def check_not_empty(cls, values):
        if not any(values.values()):
            raise ValueError("At least one setting must be provided for update")
        return values


#---------------------
# Dependency Injection
#---------------------

@lru_cache
def get_orchestrator():
    """Get or create the lead generation orchestrator."""
    return LeadGenerationOrchestrator()


@lru_cache
def get_storage():
    """Get or create the lead storage."""
    return LeadStorage()


@lru_cache
def get_monitor():
    """Get or create the system monitor."""
    return SystemMonitor()


@lru_cache
def get_export_manager():
    """Get or create the export manager."""
    return ExportManager()


def get_start_time():
    """Get the server start time."""
    if not hasattr(get_start_time, "start_time"):
        get_start_time.start_time = time.time()
    return get_start_time.start_time


async def get_api_key(
    api_key_header: str = Depends(api_key_header),
) -> str:
    """Validate API key from request header."""
    if api_key_header is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API Key header is missing",
        )
    
    # Get the valid API keys from configuration
    valid_api_keys = getattr(config, "api_keys", [])
    
    if not valid_api_keys:  # Fallback to .env or predefined key if no keys in config
        valid_api_keys = [os.environ.get("API_KEY", "development_api_key")]
    
    if api_key_header not in valid_api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key",
        )
    
    return api_key_header


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    """Rate limit middleware to prevent abuse."""
    if request.url.path in ["/api/health", "/docs", "/redoc", "/openapi.json"]:
        # Skip rate limiting for non-critical endpoints
        return await call_next(request)
    
    # Get client IP
    client_ip = request.client.host if request.client else "unknown"
    
    # Check if client has available quota
    now = time.time()
    client_data = rate_limit_storage.get(client_ip, {"count": 0, "window_start": now})
    
    # Reset window if expired
    if now - client_data["window_start"] > RATE_LIMIT_WINDOW:
        client_data = {"count": 0, "window_start": now}
    
    # Increment request count
    client_data["count"] += 1
    rate_limit_storage[client_ip] = client_data
    
    # Check if over limit
    if client_data["count"] > MAX_REQUESTS_PER_WINDOW:
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "detail": "Rate limit exceeded. Try again later.",
                "retry_after": int(client_data["window_start"] + RATE_LIMIT_WINDOW - now)
            }
        )
    
    # Process the request if within rate limit
    return await call_next(request)


#-----------------
# Helper Functions
#-----------------

def apply_lead_filters(leads, filters):
    """Apply filters to a list of leads."""
    if not filters:
        return leads
    
    filtered_leads = leads
    
    if 'status' in filters:
        filtered_leads = [l for l in filtered_leads if l.status == filters['status']]
    
    if 'source' in filters:
        filtered_leads = [l for l in filtered_leads if l.source == filters['source']]
    
    if 'min_quality' in filters:
        filtered_leads = [l for l in filtered_leads 
                          if l.quality_score and l.quality_score >= filters['min_quality']]
    
    if 'date_from' in filters:
        date_from = datetime.fromisoformat(filters['date_from'])
        filtered_leads = [l for l in filtered_leads if l.timestamp >= date_from]
    
    if 'date_to' in filters:
        date_to = datetime.fromisoformat(filters['date_to'])
        filtered_leads = [l for l in filtered_leads if l.timestamp <= date_to]
    
    if 'search' in filters and filters['search']:
        search = filters['search'].lower()
        filtered_leads = [l for l in filtered_leads 
                         if (search in l.name.lower() or 
                            (l.company and search in l.company.lower()) or
                            (l.project_description and search in l.project_description.lower()))]
    
    return filtered_leads


def paginate(items, page=1, size=20):
    """Paginate a list of items."""
    start = (page - 1) * size
    end = start + size
    
    return {
        "items": items[start:end],
        "total": len(items),
        "page": page,
        "size": size,
        "pages": (len(items) + size - 1) // size  # Ceiling division
    }


async def export_leads_background(
    format: str,
    filter: dict,
    destination: Optional[str],
    job_id: str,
    export_manager: ExportManager,
    storage: LeadStorage
):
    """Background task for exporting leads."""
    try:
        # Get leads with filters
        all_leads = storage.get_all_leads()
        filtered_leads = apply_lead_filters(all_leads, filter)
        
        # Perform the export
        if format == "hubspot":
            export_manager.export_to_hubspot(filtered_leads)
        else:
            export_path = f"exports/leads_export_{job_id}.{format}"
            if format == "csv":
                export_manager.export_to_csv(filtered_leads, export_path)
            elif format == "json":
                export_manager.export_to_json(filtered_leads, export_path)
            elif format == "xlsx":
                export_manager.export_to_excel(filtered_leads, export_path)
            
            # Send to destination if provided
            if destination and "@" in destination:  # Simple check if it's an email
                export_manager.send_export_email(destination, export_path)
        
        logger.info(f"Completed export job {job_id}")
    except Exception as e:
        logger.error(f"Export job {job_id} failed: {str(e)}", exc_info=True)


#---------
# Endpoints
#---------

@app.get("/docs", include_in_schema=False)
async def get_docs(api_key: APIKey = Depends(get_api_key)):
    """Custom Swagger docs that require API key authentication."""
    return get_swagger_ui_html(openapi_url="/openapi.json", title="API Documentation")


@app.get("/api/health")
async def health_check(
    orchestrator: LeadGenerationOrchestrator = Depends(get_orchestrator),
    storage: LeadStorage = Depends(get_storage),
    monitor: SystemMonitor = Depends(get_monitor)
):
    """
    System health check endpoint providing status of all components.
    Does not require authentication for monitoring purposes.
    """
    # Get component statuses
    storage_status = "healthy" if storage.is_connected() else "unhealthy"
    orchestrator_status = "healthy" if orchestrator.is_initialized() else "unhealthy"
    
    # Get uptime
    uptime = time.time() - get_start_time()
    
    # Get component-specific metrics
    metrics = monitor.track_metrics() if hasattr(monitor, 'track_metrics') else {}
    
    return HealthStatus(
        status="operational" if storage_status == "healthy" and orchestrator_status == "healthy" else "degraded",
        version=getattr(config, "version", "1.0.0"),
        uptime=uptime,
        timestamp=datetime.now(),
        components={
            "storage": {
                "status": storage_status,
                "lead_count": len(storage.get_all_leads())
            },
            "orchestrator": {
                "status": orchestrator_status,
                "active_sources": len(orchestrator.get_active_sources())
            },
            "monitor": {
                "status": "healthy" if metrics else "unknown",
                "metrics": metrics
            }
        }
    )


@app.get("/api/sources", response_model=List[DataSource])
async def get_sources(
    api_key: APIKey = Depends(get_api_key),
    orchestrator: LeadGenerationOrchestrator = Depends(get_orchestrator)
):
    """
    Get all configured data sources.
    """
    sources = orchestrator.get_sources()
    return sources


@app.post("/api/sources", response_model=DataSource, status_code=status.HTTP_201_CREATED)
async def create_source(
    source: DataSourceCreate,
    api_key: APIKey = Depends(get_api_key),
    orchestrator: LeadGenerationOrchestrator = Depends(get_orchestrator)
):
    """
    Add a new data source.
    """
    try:
        new_source = orchestrator.add_source(
            source_type=source.type,
            name=source.name,
            url=source.url,
            credentials=source.credentials,
            schedule=source.schedule,
            config=source.config,
            is_active=source.is_active
        )
        return new_source
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to create source: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create source: {str(e)}"
        )


@app.put("/api/sources/{source_id}", response_model=DataSource)
async def update_source(
    source_id: str,
    source_update: DataSourceUpdate,
    api_key: APIKey = Depends(get_api_key),
    orchestrator: LeadGenerationOrchestrator = Depends(get_orchestrator)
):
    """
    Update a data source configuration.
    """
    # Check if source exists
    sources = orchestrator.get_sources()
    source = next((s for s in sources if s.id == source_id), None)
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source with ID {source_id} not found"
        )
    
    try:
        updated_source = orchestrator.update_source(
            source_id=source_id,
            **{k: v for k, v in source_update.dict().items() if v is not None}
        )
        return updated_source
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to update source: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update source: {str(e)}"
        )


@app.delete("/api/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_source(
    source_id: str,
    api_key: APIKey = Depends(get_api_key),
    orchestrator: LeadGenerationOrchestrator = Depends(get_orchestrator)
):
    """
    Remove a data source.
    """
    # Check if source exists
    sources = orchestrator.get_sources()
    source = next((s for s in sources if s.id == source_id), None)
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source with ID {source_id} not found"
        )
    
    try:
        orchestrator.remove_source(source_id)
        return None
    except Exception as e:
        logger.error(f"Failed to delete source: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete source: {str(e)}"
        )


@app.get("/api/leads", response_model=PaginatedLeads)
async def get_leads(
    api_key: APIKey = Depends(get_api_key),
    storage: LeadStorage = Depends(get_storage),
    page: int = 1,
    size: int = 20,
    status: Optional[str] = None,
    source: Optional[str] = None,
    min_quality: Optional[float] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    search: Optional[str] = None
):
    """
    Get filtered lead listings with pagination.
    """
    if page < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Page must be greater than 0"
        )
    
    if size < 1 or size > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Size must be between 1 and 100"
        )
    
    try:
        # Build filters
        filters = {}
        if status:
            filters['status'] = status
        if source:
            filters['source'] = source
        if min_quality is not None:
            filters['min_quality'] = min_quality
        if date_from:
            filters['date_from'] = date_from
        if date_to:
            filters['date_to'] = date_to
        if search:
            filters['search'] = search
        
        # Get all leads
        all_leads = storage.get_all_leads()
        
        # Apply filters
        filtered_leads = apply_lead_filters(all_leads, filters)
        
        # Apply pagination
        paginated_result = paginate(filtered_leads, page, size)
        return PaginatedLeads(**paginated_result)
    
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to get leads: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get leads: {str(e)}"
        )


@app.get("/api/leads/{lead_id}", response_model=Lead)
async def get_lead(
    lead_id: str,
    api_key: APIKey = Depends(get_api_key),
    storage: LeadStorage = Depends(get_storage)
):
    """
    Get detailed lead information by ID.
    """
    lead = storage.get_lead(lead_id)
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead with ID {lead_id} not found"
        )
    
    return lead


@app.put("/api/leads/{lead_id}", response_model=Lead)
async def update_lead(
    lead_id: str,
    lead_update: LeadUpdate,
    api_key: APIKey = Depends(get_api_key),
    storage: LeadStorage = Depends(get_storage)
):
    """
    Update lead information.
    """
    # Check if lead exists
    lead = storage.get_lead(lead_id)
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead with ID {lead_id} not found"
        )
    
    try:
        # Update lead attributes
        update_data = {k: v for k, v in lead_update.dict().items() if v is not None}
        
        for key, value in update_data.items():
            setattr(lead, key, value)
        
        # Save updated lead
        updated_lead = storage.update_lead(lead)
        return updated_lead
    except Exception as e:
        logger.error(f"Failed to update lead: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update lead: {str(e)}"
        )


@app.delete("/api/leads/{lead_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lead(
    lead_id: str,
    api_key: APIKey = Depends(get_api_key),
    storage: LeadStorage = Depends(get_storage)
):
    """
    Delete a lead.
    """
    # Check if lead exists
    lead = storage.get_lead(lead_id)
    
    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Lead with ID {lead_id} not found"
        )
    
    try:
        # Delete the lead
        storage.delete_lead(lead_id)
        return None
    except Exception as e:
        logger.error(f"Failed to delete lead: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete lead: {str(e)}"
        )


@app.get("/api/stats", response_model=SystemMetrics)
async def get_system_stats(
    api_key: APIKey = Depends(get_api_key),
    monitor: SystemMonitor = Depends(get_monitor),
    orchestrator: LeadGenerationOrchestrator = Depends(get_orchestrator),
    storage: LeadStorage = Depends(get_storage)
):
    """
    Retrieve system performance metrics.
    """
    try:
        # Collect metrics
        metrics = monitor.track_metrics()
        
        # Get additional data
        lead_count = len(storage.get_all_leads())
        active_sources = len(orchestrator.get_active_sources())
        
        # Get recent errors from monitoring system
        recent_errors = monitor.get_recent_errors() if hasattr(monitor, 'get_recent_errors') else []
        
        return SystemMetrics(
            cpu_usage=metrics.get('cpu_percent', 0.0),
            memory_usage=metrics.get('memory_percent', 0.0),
            disk_usage=metrics.get('disk_percent', 0.0),
            lead_count=lead_count,
            avg_processing_time=metrics.get('avg_processing_time', 0.0),
            success_rate=metrics.get('success_rate', 100.0),
            active_sources=active_sources,
            recent_errors=recent_errors,
            last_updated=datetime.now()
        )
    except Exception as e:
        logger.error(f"Failed to get system stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get system stats: {str(e)}"
        )


@app.post("/api/export", response_model=ExportResponse)
async def export_leads(
    export_request: ExportRequest,
    background_tasks: BackgroundTasks,
    api_key: APIKey = Depends(get_api_key),
    export_manager: ExportManager = Depends(get_export_manager),
    storage: LeadStorage = Depends(get_storage)
):
    """
    Trigger manual lead export.
    """
    try:
        # Generate a job ID
        job_id = str(uuid.uuid4())
        
        # Schedule export as a background task
        background_tasks.add_task(
            export_leads_background,
            export_request.format,
            export_request.filter or {},
            export_request.destination,
            job_id,
            export_manager,
            storage
        )
        
        return ExportResponse(
            job_id=job_id,
            status="processing",
            message=f"Export job started with format: {export_request.format}",
            timestamp=datetime.now()
        )
    except Exception as e:
        logger.error(f"Failed to start export: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start export: {str(e)}"
        )


@app.get("/api/settings", response_model=Settings)
async def get_settings(
    api_key: APIKey = Depends(get_api_key)
):
    """
    Get system configuration settings.
    """
    try:
        # Get settings from config module
        return Settings(
            sources_check_interval=getattr(config, "sources_check_interval", 3600),
            export_interval=getattr(config, "export_interval", 86400),
            hubspot_api_key=getattr(config, "hubspot_api_key", None),
            export_email=getattr(config, "export_email", None),
            quality_threshold=getattr(config, "quality_threshold", 50.0),
            enable_automatic_exports=getattr(config, "enable_automatic_exports", True),
            monitoring_metrics_interval=getattr(config, "monitoring_metrics_interval", 300),
            notification_email=getattr(config, "notification_email", None),
            max_leads_per_source=getattr(config, "max_leads_per_source", None),
            retention_days=getattr(config, "retention_days", 365)
        )
    except Exception as e:
        logger.error(f"Failed to get settings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get settings: {str(e)}"
        )


@app.put("/api/settings", response_model=Settings)
async def update_settings(
    settings_update: SettingsUpdate,
    api_key: APIKey = Depends(get_api_key)
):
    """
    Update system configuration.
    """
    try:
        # Get current settings
        current_settings = {
            "sources_check_interval": getattr(config, "sources_check_interval", 3600),
            "export_interval": getattr(config, "export_interval", 86400),
            "hubspot_api_key": getattr(config, "hubspot_api_key", None),
            "export_email": getattr(config, "export_email", None),
            "quality_threshold": getattr(config, "quality_threshold", 50.0),
            "enable_automatic_exports": getattr(config, "enable_automatic_exports", True),
            "monitoring_metrics_interval": getattr(config, "monitoring_metrics_interval", 300),
            "notification_email": getattr(config, "notification_email", None),
            "max_leads_per_source": getattr(config, "max_leads_per_source", None),
            "retention_days": getattr(config, "retention_days", 365)
        }
        
        # Update with new values
        update_dict = {k: v for k, v in settings_update.dict().items() if v is not None}
        current_settings.update(update_dict)
        
        # Update config module
        for key, value in update_dict.items():
            setattr(config, key, value)
        
        # Save config changes to file if possible
        if hasattr(config, 'save_config'):
            config.save_config()
        
        return Settings(**current_settings)
    except Exception as e:
        logger.error(f"Failed to update settings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update settings: {str(e)}"
        )


@app.post("/api/triggers/generate", status_code=status.HTTP_202_ACCEPTED)
async def trigger_lead_generation(
    api_key: APIKey = Depends(get_api_key),
    orchestrator: LeadGenerationOrchestrator = Depends(get_orchestrator),
    background_tasks: BackgroundTasks
):
    """
    Manually trigger the lead generation process.
    """
    try:
        # Start lead generation in background
        background_tasks.add_task(orchestrator.generate_leads)
        
        return {
            "status": "processing",
            "message": "Lead generation process started",
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"Failed to trigger lead generation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger lead generation: {str(e)}"
        )


@app.post("/api/triggers/source/{source_id}", status_code=status.HTTP_202_ACCEPTED)
async def trigger_specific_source(
    source_id: str,
    api_key: APIKey = Depends(get_api_key),
    orchestrator: LeadGenerationOrchestrator = Depends(get_orchestrator),
    background_tasks: BackgroundTasks
):
    """
    Manually trigger a specific data source.
    """
    # Check if source exists
    sources = orchestrator.get_sources()
    source = next((s for s in sources if s.id == source_id), None)
    
    if not source:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Data source with ID {source_id} not found"
        )
    
    try:
        # Run the specific source in background
        background_tasks.add_task(orchestrator.run_source, source_id)
        
        return {
            "status": "processing",
            "message": f"Source '{source.name}' processing started",
            "timestamp": datetime.now()
        }
    except Exception as e:
        logger.error(f"Failed to trigger source: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger source: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    
    # Get port from environment or use default
    port = int(os.environ.get("PORT", 8000))
    
    # Start server
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=port,
        reload=True if os.environ.get("ENV") == "development" else False,
    )