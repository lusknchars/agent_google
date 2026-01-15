# Orbit - AI-Powered Daily Briefing Agent

Orbit aggregates data from your SaaS tools and generates an actionable daily briefing using AI.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with your API credentials

# Run database migrations
alembic upgrade head

# Start the server
uvicorn app.main:app --reload
```

## API Documentation

After starting the server, visit: http://localhost:8000/docs

## Environment Variables

See `.env.example` for all required configuration options.
