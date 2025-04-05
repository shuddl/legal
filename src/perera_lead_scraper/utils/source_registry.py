#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Source Registry - Manages data sources configuration.
"""

import os
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Any, Set

from utils.logger import get_logger

@dataclass
class DataSource:
    """Data source representation."""
    
    name: str
    url: str
    type: str  # 'rss', 'website', 'city_portal', 'permit_database', 'api'
    category: str
    active: bool = True
    requires_js: bool = False
    config: Dict[str, Any] = field(default_factory=dict)
    last_checked: Optional[str] = None
    status: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    tags: Set[str] = field(default_factory=set)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['tags'] = list(self.tags)  # Convert set to list for JSON serialization
        return data


class SourceRegistry:
    """Registry for managing data sources."""
    
    def __init__(self, sources_file: Optional[str] = None):
        """
        Initialize the source registry.
        
        Args:
            sources_file: Path to the sources JSON file
        """
        self.logger = get_logger('source_registry')
        self.sources: Dict[str, DataSource] = {}
        
        # Load sources if file provided
        if sources_file:
            self.load_sources(sources_file)
    
    def load_sources(self, sources_file: str) -> bool:
        """
        Load sources from a JSON file.
        
        Args:
            sources_file: Path to the sources JSON file
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not os.path.exists(sources_file):
                self.logger.error(f"Sources file not found: {sources_file}")
                return False
            
            with open(sources_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Clear existing sources
            self.sources = {}
            
            # Process sources
            for source_data in data.get('sources', []):
                name = source_data.get('name')
                if not name:
                    self.logger.warning("Skipping source without name")
                    continue
                
                # Convert tags to set if present
                if 'tags' in source_data:
                    tags = set(source_data['tags'])
                    source_data['tags'] = tags
                
                # Create DataSource object
                source = DataSource(**source_data)
                self.sources[name] = source
            
            self.logger.info(f"Loaded {len(self.sources)} sources")
            return True
            
        except Exception as e:
            self.logger.error(f"Error loading sources: {str(e)}")
            return False
    
    def save_sources(self, sources_file: str) -> bool:
        """
        Save sources to a JSON file.
        
        Args:
            sources_file: Path to the sources JSON file
        
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Convert sources to JSON-serializable format
            sources_data = []
            for source in self.sources.values():
                sources_data.append(source.to_dict())
            
            data = {'sources': sources_data}
            
            with open(sources_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
            
            self.logger.info(f"Saved {len(self.sources)} sources to {sources_file}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error saving sources: {str(e)}")
            return False
    
    def get_source(self, name: str) -> Optional[DataSource]:
        """
        Get a source by name.
        
        Args:
            name: Source name
        
        Returns:
            DataSource or None: The source if found, None otherwise
        """
        return self.sources.get(name)
    
    def add_source(self, source: DataSource) -> bool:
        """
        Add a source to the registry.
        
        Args:
            source: DataSource object
        
        Returns:
            bool: True if added, False if source with same name exists
        """
        if source.name in self.sources:
            self.logger.warning(f"Source with name {source.name} already exists")
            return False
        
        self.sources[source.name] = source
        self.logger.info(f"Added source: {source.name}")
        return True
    
    def update_source(self, source: DataSource) -> bool:
        """
        Update an existing source.
        
        Args:
            source: DataSource object with updated data
        
        Returns:
            bool: True if updated, False if source not found
        """
        if source.name not in self.sources:
            self.logger.warning(f"Source with name {source.name} not found")
            return False
        
        self.sources[source.name] = source
        self.logger.info(f"Updated source: {source.name}")
        return True
    
    def remove_source(self, name: str) -> bool:
        """
        Remove a source from the registry.
        
        Args:
            name: Source name
        
        Returns:
            bool: True if removed, False if source not found
        """
        if name not in self.sources:
            self.logger.warning(f"Source with name {name} not found")
            return False
        
        del self.sources[name]
        self.logger.info(f"Removed source: {name}")
        return True
    
    def get_active_sources(self) -> List[DataSource]:
        """
        Get all active sources.
        
        Returns:
            List[DataSource]: List of active sources
        """
        return [source for source in self.sources.values() if source.active]
    
    def get_sources_by_type(self, source_type: str) -> List[DataSource]:
        """
        Get sources by type.
        
        Args:
            source_type: Source type
        
        Returns:
            List[DataSource]: List of sources with the specified type
        """
        return [source for source in self.sources.values() if source.type == source_type]
    
    def get_sources_by_category(self, category: str) -> List[DataSource]:
        """
        Get sources by category.
        
        Args:
            category: Source category
        
        Returns:
            List[DataSource]: List of sources with the specified category
        """
        return [source for source in self.sources.values() if source.category == category]
    
    def get_sources_by_tag(self, tag: str) -> List[DataSource]:
        """
        Get sources by tag.
        
        Args:
            tag: Source tag
        
        Returns:
            List[DataSource]: List of sources with the specified tag
        """
        return [source for source in self.sources.values() if tag in source.tags]
    
    def create_or_update_source(self, source_data: Dict[str, Any]) -> DataSource:
        """
        Create a new source or update an existing one.
        
        Args:
            source_data: Dictionary with source data
        
        Returns:
            DataSource: The created or updated source
        """
        name = source_data.get('name')
        if not name:
            raise ValueError("Source must have a name")
        
        # Convert tags to set if present
        if 'tags' in source_data:
            tags = set(source_data['tags'])
            source_data['tags'] = tags
        
        # Check if source exists
        if name in self.sources:
            # Update existing source
            source = self.sources[name]
            
            # Update fields
            for key, value in source_data.items():
                setattr(source, key, value)
            
            self.logger.info(f"Updated source: {name}")
        else:
            # Create new source
            source = DataSource(**source_data)
            self.sources[name] = source
            self.logger.info(f"Created source: {name}")
        
        return source