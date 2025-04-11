#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lead Dashboard

This script provides a web-based dashboard for visualizing and interacting with
leads gathered by the Perera Construction Lead Scraper system. It allows users to:
- View all leads in the system
- Filter leads by various criteria
- Visualize lead quality and distribution
- Test lead enrichment and export processes
"""

import os
import sys
import logging
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
from pathlib import Path

# Add the project root to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.perera_lead_scraper.utils.storage import LeadStorage
from src.perera_lead_scraper.models.lead import MarketSector, LeadStatus
from src.perera_lead_scraper.enrichment.enrichment import LeadEnricher
from src.perera_lead_scraper.hubspot.hubspot_mapper import HubSpotMapper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger("lead_dashboard")

def format_lead_for_display(lead):
    """Format a lead for display in a table."""
    return {
        "ID": getattr(lead, "id", ""),
        "Title": getattr(lead, "project_name", getattr(lead, "title", "")),
        "Source": getattr(lead, "source", ""),
        "Market Sector": getattr(lead, "market_sector", ""),
        "Location": str(getattr(lead, "location", "")),
        "Value": f"${getattr(lead, 'estimated_value', 0):,.0f}" if getattr(lead, 'estimated_value', None) else "N/A",
        "Quality Score": f"{getattr(lead, 'confidence_score', 0):.2f}",
        "Status": getattr(lead, "status", ""),
        "Retrieved": getattr(lead, "retrieved_date", "").strftime("%Y-%m-%d") if getattr(lead, "retrieved_date", None) else ""
    }


def filter_leads(leads, filters):
    """Filter leads based on various criteria."""
    filtered_leads = leads.copy()
    
    # Apply filters
    if filters.get("min_quality", 0) > 0:
        filtered_leads = [l for l in filtered_leads if getattr(l, "confidence_score", 0) >= filters["min_quality"]]
    
    if filters.get("market_sectors"):
        filtered_leads = [l for l in filtered_leads if 
                         getattr(l, "market_sector", None) in filters["market_sectors"]]
    
    if filters.get("status"):
        filtered_leads = [l for l in filtered_leads if 
                         getattr(l, "status", None) in filters["status"]]
    
    if filters.get("min_value"):
        filtered_leads = [l for l in filtered_leads if 
                        getattr(l, "estimated_value", 0) >= filters["min_value"]]
    
    if filters.get("search_term"):
        search_term = filters["search_term"].lower()
        filtered_leads = [l for l in filtered_leads if 
                         search_term in getattr(l, "project_name", "").lower() or 
                         search_term in getattr(l, "description", "").lower()]
    
    return filtered_leads


def create_lead_visualizations(leads):
    """Create visualizations for lead data."""
    # Convert to pandas DataFrame for easier analysis
    lead_data = [format_lead_for_display(lead) for lead in leads]
    df = pd.DataFrame(lead_data)
    
    # Create two columns for charts
    col1, col2 = st.columns(2)
    
    # Market sector distribution
    with col1:
        if "Market Sector" in df.columns and not df["Market Sector"].empty:
            st.subheader("Lead Distribution by Market Sector")
            sector_counts = df["Market Sector"].value_counts()
            fig, ax = plt.subplots()
            sector_counts.plot(kind="bar", ax=ax)
            plt.xticks(rotation=45)
            plt.tight_layout()
            st.pyplot(fig)
    
    # Quality score distribution
    with col2:
        if "Quality Score" in df.columns and not df["Quality Score"].empty:
            st.subheader("Lead Quality Distribution")
            # Convert string scores to float
            quality_scores = pd.to_numeric(df["Quality Score"], errors="coerce")
            fig, ax = plt.subplots()
            quality_scores.hist(bins=10, ax=ax)
            plt.xlabel("Quality Score")
            plt.ylabel("Number of Leads")
            st.pyplot(fig)


def display_lead_detail(lead):
    """Display detailed information for a selected lead."""
    st.subheader(f"Lead Details: {getattr(lead, 'project_name', 'Unnamed Lead')}")
    
    # Basic Info
    st.write("**Basic Information:**")
    st.write(f"**Description:** {getattr(lead, 'description', 'N/A')}")
    st.write(f"**Source:** {getattr(lead, 'source', 'N/A')}")
    st.write(f"**Source URL:** {getattr(lead, 'source_url', 'N/A')}")
    st.write(f"**Confidence Score:** {getattr(lead, 'confidence_score', 0):.2f}")
    
    # Project Details
    st.write("**Project Details:**")
    st.write(f"**Market Sector:** {getattr(lead, 'market_sector', 'N/A')}")
    st.write(f"**Location:** {str(getattr(lead, 'location', 'N/A'))}")
    st.write(f"**Estimated Value:** ${getattr(lead, 'estimated_value', 0):,.0f}" if getattr(lead, 'estimated_value', None) else "N/A")
    
    # Company Details
    if hasattr(lead, 'extra_data') and lead.extra_data.get('company'):
        st.write("**Company Information:**")
        company = lead.extra_data['company']
        st.write(f"**Name:** {company.get('name', 'N/A')}")
        st.write(f"**Website:** {company.get('website', 'N/A')}")
        st.write(f"**Size:** {company.get('size', 'N/A')}")
    
    # Contact Details
    if hasattr(lead, 'contacts') and lead.contacts:
        st.write("**Contacts:**")
        for contact in lead.contacts:
            st.write(f"**Name:** {getattr(contact, 'name', 'N/A')}")
            st.write(f"**Email:** {getattr(contact, 'email', 'N/A')}")
            st.write(f"**Phone:** {getattr(contact, 'phone', 'N/A')}")
    
    # Enrichment & Export Options
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Enrich Lead"):
            try:
                enricher = LeadEnricher()
                enriched_data = enricher.enrich_lead(lead)
                st.success("Lead enriched successfully!")
                st.json(enriched_data)
            except Exception as e:
                st.error(f"Error enriching lead: {str(e)}")
    
    with col2:
        if st.button("Export to HubSpot"):
            try:
                hubspot_mapper = HubSpotMapper()
                company, contact, deal = hubspot_mapper.map_lead_to_hubspot(lead)
                
                # Show the mapped data that would be sent to HubSpot
                st.success("Lead mapped for HubSpot successfully!")
                
                # Display the mapped data
                st.write("**Company Data:**")
                st.json(company)
                
                if contact:
                    st.write("**Contact Data:**")
                    st.json(contact)
                    
                st.write("**Deal Data:**")
                st.json(deal)
                
            except Exception as e:
                st.error(f"Error mapping lead for HubSpot: {str(e)}")


def main():
    """Main entry point for the dashboard."""
    st.set_page_config(
        page_title="Perera Lead Scraper Dashboard",
        page_icon="📊",
        layout="wide",
    )
    
    st.title("Perera Construction Lead Scraper Dashboard")
    st.write("Use this dashboard to view, filter, and manage leads in the system.")
    
    # Initialize storage
    try:
        storage = LeadStorage()
        all_leads = storage.get_all_leads()
        logger.info(f"Retrieved {len(all_leads)} leads from storage")
    except Exception as e:
        st.error(f"Error connecting to lead storage: {str(e)}")
        all_leads = []
    
    # Sidebar for filters
    st.sidebar.header("Lead Filters")
    
    # Quality filter
    min_quality = st.sidebar.slider(
        "Minimum Quality Score", 
        min_value=0.0, 
        max_value=1.0, 
        value=0.0,
        step=0.05
    )
    
    # Market sector filter
    all_sectors = [sector.value for sector in MarketSector]
    selected_sectors = st.sidebar.multiselect(
        "Market Sectors",
        options=all_sectors,
        default=[]
    )
    
    # Status filter
    all_statuses = [status.value for status in LeadStatus]
    selected_statuses = st.sidebar.multiselect(
        "Lead Status",
        options=all_statuses,
        default=[]
    )
    
    # Value filter
    min_value = st.sidebar.number_input(
        "Minimum Project Value ($)",
        min_value=0,
        value=0,
        step=100000
    )
    
    # Search term
    search_term = st.sidebar.text_input("Search in Title/Description")
    
    # Apply filters
    filters = {
        "min_quality": min_quality,
        "market_sectors": selected_sectors,
        "status": selected_statuses,
        "min_value": min_value,
        "search_term": search_term,
    }
    
    filtered_leads = filter_leads(all_leads, filters)
    
    # Main content area - tabs for different views
    tab1, tab2 = st.tabs(["Lead List", "Analytics"])
    
    with tab1:
        # Show lead count
        st.write(f"**Showing {len(filtered_leads)} out of {len(all_leads)} leads**")
        
        # Display leads in a table
        if filtered_leads:
            lead_data = [format_lead_for_display(lead) for lead in filtered_leads]
            df = pd.DataFrame(lead_data)
            
            # Make the table clickable
            selection = st.dataframe(
                df,
                use_container_width=True,
                column_config={
                    "Title": st.column_config.TextColumn("Title", width="large"),
                    "Quality Score": st.column_config.NumberColumn("Quality Score", format="%.2f"),
                    "Value": st.column_config.TextColumn("Value", width="medium"),
                },
            )
            
            # Allow selection of a lead for detailed view
            selected_index = st.selectbox(
                "Select a lead to view details:",
                options=range(len(filtered_leads)),
                format_func=lambda i: lead_data[i]["Title"]
            )
            
            # Display detailed information for the selected lead
            if selected_index is not None:
                display_lead_detail(filtered_leads[selected_index])
                
        else:
            st.info("No leads match the current filters.")
    
    with tab2:
        if filtered_leads:
            create_lead_visualizations(filtered_leads)
            
            # Additional aggregate statistics
            st.subheader("Lead Statistics")
            
            # Source statistics
            sources = {}
            for lead in filtered_leads:
                source = getattr(lead, "source", "Unknown")
                if source in sources:
                    sources[source] += 1
                else:
                    sources[source] = 1
            
            # Quality statistics
            quality_scores = [getattr(lead, "confidence_score", 0) for lead in filtered_leads]
            avg_quality = sum(quality_scores) / len(quality_scores) if quality_scores else 0
            
            # Display statistics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Leads", len(filtered_leads))
            with col2:
                st.metric("Average Quality Score", f"{avg_quality:.2f}")
            with col3:
                st.metric("Top Source", max(sources.items(), key=lambda x: x[1])[0] if sources else "N/A")
            
            # Show counts by market sector
            sectors = {}
            for lead in filtered_leads:
                sector = getattr(lead, "market_sector", "Unknown")
                sector_name = sector.value if hasattr(sector, "value") else str(sector)
                if sector_name in sectors:
                    sectors[sector_name] += 1
                else:
                    sectors[sector_name] = 1
            
            st.write("**Leads by Market Sector:**")
            sector_df = pd.DataFrame({
                "Sector": list(sectors.keys()),
                "Count": list(sectors.values())
            })
            st.dataframe(sector_df, use_container_width=True)
            
        else:
            st.info("No leads available for analysis.")


if __name__ == "__main__":
    main()