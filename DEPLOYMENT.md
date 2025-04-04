# Perera Construction Lead Scraper - Deployment Guide

This document provides detailed instructions for deploying the Perera Construction Lead Scraper in various environments.

## Table of Contents

- [System Requirements](#system-requirements)
- [Environment Preparation](#environment-preparation)
- [Standard Deployment](#standard-deployment)
- [Docker Deployment](#docker-deployment)
- [Configuration](#configuration)
- [Post-Installation Verification](#post-installation-verification)
- [Upgrade Procedures](#upgrade-procedures)

## System Requirements

### Hardware Requirements

**Minimum:**
- 2GB RAM
- 1 CPU core
- 10GB disk space

**Recommended:**
- 4GB RAM
- 2 CPU cores
- 20GB disk space

### Software Requirements

**Standard Deployment:**
- Python 3.9+
- pip (Python package manager)
- git
- SMTP server (for email notifications)
- Internet connectivity

**Docker Deployment:**
- Docker Engine 19.03+
- Docker Compose 1.27+
- Internet connectivity

### Network Requirements

- Outbound HTTP/HTTPS access to source websites
- Outbound SMTP access (if using email notifications)
- Outbound HTTP/HTTPS to HubSpot API (if using HubSpot integration)

## Environment Preparation

### Standard Environment Setup

1. **Install Python 3.9+**:

   **Ubuntu/Debian:**
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-venv
   ```

   **CentOS/RHEL:**
   ```bash
   sudo yum install python39 python39-pip
   ```

   **macOS:**
   ```bash
   brew install python
   ```

   **Windows:**
   Download and install from [python.org](https://www.python.org/downloads/)

2. **Install Git**:

   **Ubuntu/Debian:**
   ```bash
   sudo apt install git
   ```

   **CentOS/RHEL:**
   ```bash
   sudo yum install git
   ```

   **macOS:**
   ```bash
   brew install git
   ```

   **Windows:**
   Download and install from [git-scm.com](https://git-scm.com/download/win)

### Docker Environment Setup

1. **Install Docker Engine**:

   Follow the official Docker installation guide for your platform:
   - [Ubuntu](https://docs.docker.com/engine/install/ubuntu/)
   - [CentOS](https://docs.docker.com/engine/install/centos/)
   - [macOS](https://docs.docker.com/desktop/install/mac-install/)
   - [Windows](https://docs.docker.com/desktop/install/windows-install/)

2. **Install Docker Compose**:

   Follow the official [Docker Compose installation guide](https://docs.docker.com/compose/install/)

3. **Verify Installation**:
   ```bash
   docker --version
   docker-compose --version
   ```

## Standard Deployment

### Clone the Repository

```bash
git clone https://github.com/perera-construction/lead-scraper.git
cd lead-scraper
```

### Create and Activate Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Initialize the Database

```bash
python -m src.perera_lead_scraper.cli init-db
```

### Configure the Application

1. Create a configuration file:
   ```bash
   cp config.example.yml config.yml
   ```

2. Edit the configuration file:
   ```bash
   nano config.yml  # Or use any text editor
   ```

   Set at least the following required parameters:
   - API key
   - Data source credentials
   - Export settings

   See [CONFIGURATION.md](CONFIGURATION.md) for details on all available options.

### Create Required Directories

```bash
mkdir -p data exports logs
```

### Run the Application

**Start the API server:**
```bash
python -m src.perera_lead_scraper.api.api
```

**Start the orchestrator (in a separate terminal):**
```bash
python -m src.perera_lead_scraper.orchestrator
```

### Setup System Service (Optional)

For production deployments, you'll want to set up the application as a system service.

**Create a systemd service file (Linux):**

```bash
sudo nano /etc/systemd/system/perera-lead-scraper-api.service
```

Add the following content (adjust paths as needed):

```
[Unit]
Description=Perera Lead Scraper API
After=network.target

[Service]
User=leaduser
WorkingDirectory=/opt/lead-scraper
ExecStart=/opt/lead-scraper/venv/bin/python -m src.perera_lead_scraper.api.api
Restart=on-failure
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Create a similar file for the orchestrator:

```bash
sudo nano /etc/systemd/system/perera-lead-scraper-orchestrator.service
```

With content:

```
[Unit]
Description=Perera Lead Scraper Orchestrator
After=network.target

[Service]
User=leaduser
WorkingDirectory=/opt/lead-scraper
ExecStart=/opt/lead-scraper/venv/bin/python -m src.perera_lead_scraper.orchestrator
Restart=on-failure
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Enable and start the services:

```bash
sudo systemctl daemon-reload
sudo systemctl enable perera-lead-scraper-api
sudo systemctl enable perera-lead-scraper-orchestrator
sudo systemctl start perera-lead-scraper-api
sudo systemctl start perera-lead-scraper-orchestrator
```

## Docker Deployment

### Basic Deployment

1. **Clone the Repository**:
   ```bash
   git clone https://github.com/perera-construction/lead-scraper.git
   cd lead-scraper
   ```

2. **Create Environment File**:
   ```bash
   cp .env.example .env
   ```
   
   Edit the `.env` file to set your configuration:
   ```
   API_KEY=your_secure_api_key
   HUBSPOT_API_KEY=your_hubspot_api_key
   API_PORT=8000
   TZ=America/New_York
   ```

3. **Start the Services**:
   ```bash
   docker-compose up -d
   ```

4. **Verify Deployment**:
   ```bash
   docker-compose ps
   curl http://localhost:8000/api/health
   ```

### Advanced Docker Configuration

#### Using Custom Docker Compose File

For different environments, you can create custom docker-compose files:

```bash
# For staging
docker-compose -f docker-compose.yml -f docker-compose.staging.yml up -d

# For production
docker-compose -f docker-compose.yml -f docker-compose.production.yml up -d
```

#### Scaling the Application

To handle higher loads, you can run multiple worker containers:

```bash
docker-compose up -d --scale worker=3
```

#### Using External Database

Edit the `docker-compose.yml` file to uncomment the database service and update the connection parameters.

#### Persisting Data with Named Volumes

For better data management, update the volumes section in `docker-compose.yml`:

```yaml
volumes:
  lead-data:
    driver: local
  lead-exports:
    driver: local
  lead-logs:
    driver: local
```

And update the service volumes:

```yaml
volumes:
  - lead-data:/app/data
  - lead-exports:/app/exports
  - lead-logs:/app/logs
```

## Configuration

See [CONFIGURATION.md](CONFIGURATION.md) for detailed information on all configuration options.

### Core Configuration Options

The main configuration parameters to set are:

1. **API Key**: Used for API authentication
2. **Data Sources**: Credentials and configuration for each data source
3. **Export Settings**: HubSpot API key, email settings, etc.
4. **Scheduling**: How often to scrape each source and export leads
5. **Monitoring**: Alert thresholds and notification settings

### Environment Variables

The application can be configured using environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| API_KEY | Authentication key for API access | - |
| HUBSPOT_API_KEY | API key for HubSpot integration | - |
| DATABASE_URL | Database connection URL | sqlite:///data/leads.db |
| LOG_LEVEL | Logging verbosity | INFO |
| MAX_WORKERS | Maximum number of worker threads | 4 |
| PORT | Port for API server | 8000 |
| TZ | Timezone | UTC |

## Post-Installation Verification

After deployment, follow these steps to verify that the system is working correctly:

### Check the API

```bash
curl http://localhost:8000/api/health
```

Expected response:
```json
{
  "status": "operational",
  "version": "1.0.0",
  "uptime": 123.45,
  "timestamp": "2023-01-01T00:00:00.000Z",
  "components": {
    "storage": {
      "status": "healthy",
      "lead_count": 0
    },
    "orchestrator": {
      "status": "healthy",
      "active_sources": 0
    },
    "monitor": {
      "status": "healthy",
      "metrics": {}
    }
  }
}
```

### Add a Data Source

```bash
curl -X POST http://localhost:8000/api/sources \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your_api_key" \
  -d '{"name": "Test Source", "type": "test", "url": "https://example.com", "is_active": true}'
```

### Trigger Lead Generation

```bash
curl -X POST http://localhost:8000/api/triggers/generate \
  -H "X-API-Key: your_api_key"
```

### Check for Leads

```bash
curl -X GET http://localhost:8000/api/leads \
  -H "X-API-Key: your_api_key"
```

### Check Logs

Standard deployment:
```bash
cat logs/app.log
```

Docker deployment:
```bash
docker-compose logs -f
```

## Upgrade Procedures

### Standard Deployment Upgrade

1. **Stop the services**:
   ```bash
   sudo systemctl stop perera-lead-scraper-api
   sudo systemctl stop perera-lead-scraper-orchestrator
   ```

2. **Backup data**:
   ```bash
   cp -r data data.bak
   ```

3. **Update the code**:
   ```bash
   git pull origin main
   ```

4. **Update dependencies**:
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

5. **Run database migrations**:
   ```bash
   python -m src.perera_lead_scraper.cli migrate
   ```

6. **Restart services**:
   ```bash
   sudo systemctl start perera-lead-scraper-api
   sudo systemctl start perera-lead-scraper-orchestrator
   ```

7. **Verify upgrade**:
   ```bash
   curl http://localhost:8000/api/health
   ```

### Docker Deployment Upgrade

1. **Backup data volumes**:
   ```bash
   docker run --rm -v perera-lead-scraper_data:/data -v $(pwd)/backup:/backup \
     alpine tar -czf /backup/data-backup.tar.gz /data
   ```

2. **Pull the latest changes**:
   ```bash
   git pull origin main
   ```

3. **Rebuild and restart containers**:
   ```bash
   docker-compose down
   docker-compose build
   docker-compose up -d
   ```

4. **Verify upgrade**:
   ```bash
   curl http://localhost:8000/api/health
   ```