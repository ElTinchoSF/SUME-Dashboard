"""
Pipeline orchestration package for SUME Dashboard.

Provides CLI entry points for running the ETL pipeline phases:
- init-db: Initialize database schema
- scraper: Run the web scraper
- analyzer: Run the circuit analysis
- reporter: Generate ISO 9001 reports
- all: Run complete pipeline
"""

from src.pipeline.run import main

__all__ = ["main"]