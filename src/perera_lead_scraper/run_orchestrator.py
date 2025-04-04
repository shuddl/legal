#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Lead Generation Orchestrator CLI

Command-line interface for running the lead generation orchestrator.
"""

import os
import sys
import argparse
import logging
import time
import signal
import json
from pathlib import Path

from src.perera_lead_scraper.orchestration.orchestrator import LeadGenerationOrchestrator
from utils.logger import configure_logging


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Perera Construction Lead Scraper Orchestrator"
    )
    
    parser.add_argument(
        "--config",
        help="Path to configuration file",
        type=str
    )
    
    parser.add_argument(
        "--log-level",
        help="Logging level",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        default="INFO"
    )
    
    parser.add_argument(
        "--export-only",
        help="Run export pipeline only and exit",
        action="store_true"
    )
    
    parser.add_argument(
        "--metrics-file",
        help="Path to write metrics to",
        type=str
    )
    
    parser.add_argument(
        "--metrics-interval",
        help="Interval to write metrics in seconds",
        type=int,
        default=60
    )
    
    return parser.parse_args()


def setup_logging(log_level):
    """Set up logging configuration."""
    numeric_level = getattr(logging, log_level, logging.INFO)
    
    # Configure logging
    configure_logging(log_level=numeric_level)
    
    # Get root logger
    logger = logging.getLogger()
    logger.setLevel(numeric_level)
    
    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(numeric_level)
    
    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    
    # Add formatter to console handler
    console_handler.setFormatter(formatter)
    
    # Add handler to logger
    logger.addHandler(console_handler)
    
    return logger


def write_metrics(orchestrator, file_path):
    """Write metrics to file."""
    # Get metrics
    metrics = orchestrator.get_system_metrics()
    
    # Write to file
    with open(file_path, "w") as f:
        json.dump(metrics, f, indent=2)


def main():
    """Main function."""
    # Parse arguments
    args = parse_args()
    
    # Set up logging
    logger = setup_logging(args.log_level)
    logger.info("Starting Perera Construction Lead Scraper Orchestrator")
    
    # Create orchestrator
    orchestrator = LeadGenerationOrchestrator()
    
    # Initialize components
    if not orchestrator.initialize_components():
        logger.error("Failed to initialize components, exiting")
        sys.exit(1)
    
    # If export-only mode, run export and exit
    if args.export_only:
        logger.info("Running export pipeline and exiting")
        export_result = orchestrator.trigger_export_pipeline()
        logger.info(f"Export result: {export_result}")
        sys.exit(0)
    
    # Start processing
    orchestrator.start_processing()
    logger.info("Lead generation process started")
    
    # Set up metrics writing if requested
    metrics_timer = None
    if args.metrics_file:
        def write_metrics_task():
            try:
                write_metrics(orchestrator, args.metrics_file)
            except Exception as e:
                logger.error(f"Error writing metrics: {str(e)}")
        
        # Write initial metrics
        write_metrics_task()
        
        # Set up periodic writing
        import threading
        metrics_timer = threading.Timer(args.metrics_interval, write_metrics_task)
        metrics_timer.daemon = True
        metrics_timer.start()
    
    try:
        # Keep running until interrupted
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down")
    finally:
        # Cancel metrics timer if active
        if metrics_timer:
            metrics_timer.cancel()
        
        # Ensure graceful shutdown
        logger.info("Shutting down orchestrator")
        orchestrator.shutdown_gracefully()
        logger.info("Orchestrator shutdown complete")


if __name__ == "__main__":
    main()