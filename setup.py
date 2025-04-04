#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from setuptools import setup, find_packages

# Read version from __init__.py
with open("src/perera_lead_scraper/__init__.py", "r") as f:
    for line in f:
        if line.startswith("__version__"):
            version = line.split("=")[1].strip().strip('"').strip("'")
            break
    else:
        version = "0.0.1"

# Read long description from README.md
with open("README.md", "r", encoding="utf-8") as f:
    long_description = f.read()

setup(
    name="perera-lead-scraper",
    version=version,
    description="A tool for finding construction project leads from various sources",
    long_description=long_description,
    long_description_content_type="text/markdown",
    author="Perera Construction",
    author_email="info@pereraconstruction.com",
    url="https://github.com/pereraconstruction/lead-scraper",
    package_dir={"": "src"},
    packages=find_packages(where="src"),
    include_package_data=True,
    python_requires=">=3.9",
    install_requires=[
        "scrapy>=2.11.0",
        "selenium>=4.18.1",
        "playwright>=1.42.0",
        "beautifulsoup4>=4.12.2",
        "pandas>=2.2.1",
        "numpy>=1.26.4",
        "requests>=2.31.0",
        "nltk>=3.8.1",
        "spacy>=3.7.4",
        "hubspot-api-client==7.5.0",
        "feedparser>=6.0.11",
        "python-dotenv>=1.0.1",
        "pydantic>=2.6.1",
        "sqlalchemy>=2.0.23",
        "tenacity>=8.2.3",
        "alembic>=1.12.1",
        "email-validator>=2.1.0",
    ],
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "pytest-cov>=4.1.0",
            "black>=24.1.0",
            "ruff>=0.1.15",
            "mypy>=1.8.0",
            "isort>=5.13.2",
        ],
    },
    entry_points={
        "console_scripts": [
            "lead-scraper=perera_lead_scraper.main:main",
        ],
    },
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
)