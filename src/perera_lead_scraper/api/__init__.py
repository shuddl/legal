"""
API package for Perera Construction Lead Scraper.

This package contains the FastAPI implementation that exposes
the lead scraper functionality through RESTful endpoints.
"""

from .api import app

__all__ = ["app"]