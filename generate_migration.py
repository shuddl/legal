#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Generate initial database migration.
"""

import os
import sys
from alembic import command
from alembic.config import Config

# Add the parent directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import models to ensure they're available for metadata
from utils.storage import Base, LeadModel, ContactModel

def main():
    """Generate the initial migration."""
    # Get the alembic.ini path
    alembic_ini = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'alembic.ini')
    
    # Create alembic configuration
    config = Config(alembic_ini)
    
    # Create the initial migration
    command.revision(config, autogenerate=True, message="Initial migration")
    
    print("Initial migration created successfully.")

if __name__ == "__main__":
    main()