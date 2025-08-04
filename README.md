# PHIVOLCS Earthquake ETL Pipeline

ETL pipeline for processing Philippine earthquake data, built during my PHIVOLCS internship to learn data engineering fundamentals through a real-world problem.

## Background

As my first data engineering project, I wanted to learn DE fundamentals hands-on while tackling a genuinely useful problem. During my internship at PHIVOLCS (where I trained seismic wave identification), I was inspired by the QuakeFlow pipeline and saw an opportunity to apply data engineering principles to earthquake data - which is both technically challenging and serves public safety.

## Overview

Automated system that extracts earthquake data from PHIVOLCS bulletins, transforms it into structured format, and loads it into PostgreSQL database with web interface for data visualization.

**Dataset**: 103,596 earthquake records (2018 - Present)

## Tech Stack

- **Python**: ETL pipeline, data processing
- **PostgreSQL**: Database with optimized indexing  
- **Flask**: Web API and interface
- **Docker**: Containerized deployment
- **UV**: Fast dependency management

## ETL Pipeline

### Extract
- Web scraping of PHIVOLCS earthquake bulletins
- Robust HTML parsing with fallback strategies
- Rate limiting and retry logic

### Transform  
- Data cleaning and validation
- Standardization of earthquake parameters
- Duplicate detection using business keys

### Load
- PostgreSQL database with proper indexing
- Intelligent upsert operations (INSERT/UPDATE/SKIP)
- Data quality checks before insertion

## Quick Start

```bash
# Clone and setup
git clone https://github.com/your-username/phivolcs-etl-backend.git
cd phivolcs-etl-backend
cp .env.example .env

# Deploy with Docker
docker-compose up -d --build

# Access: http://localhost:5000
```

## Key Features

- **Automated Data Pipeline**: Daily processing of 1000+ earthquake records
- **Data Quality**: Validation and error handling throughout pipeline  
- **Performance**: Optimized database queries with composite indexing
- **Monitoring**: Health checks and comprehensive logging
- **Scalability**: Containerized deployment ready for production

## Database Schema

```sql
seismic_event: Main earthquake table with geospatial indexing
intensities: Related intensity measurements table
Indexes: Optimized for date/location/magnitude queries
```

## Learning Outcomes

- ETL pipeline design and implementation
- Database optimization for geospatial data
- Error handling and data quality management
- Production deployment with Docker
- Web scraping and data extraction techniques

## Acknowledgments

Data provided by PHIVOLCS (Philippine Institute of Volcanology and Seismology). Built during internship while learning seismic wave analysis.

## Disclaimer

Educational project demonstrating data engineering skills. Not affiliated with PHIVOLCS official systems.