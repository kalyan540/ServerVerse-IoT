# Python Flask Server Boilerplate

A modern, production-ready Flask server boilerplate with basic configuration and best practices.

## Features

- Flask web framework
- CORS support
- Environment variable configuration
- Health check endpoint
- Production-ready with Gunicorn

## Prerequisites

- Python 3.8 or higher
- pip (Python package manager)

## Setup

1. Create a virtual environment (recommended):
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure environment variables:
- Copy `.env.example` to `.env` (if not already done)
- Modify the values in `.env` as needed

## Running the Server

### Development
```bash
python app.py
```

### Production
```bash
gunicorn app:app
```

## API Endpoints

- `GET /`: Welcome message
- `GET /health`: Health check endpoint

## Configuration

The server can be configured through environment variables in the `.env` file:

- `FLASK_DEBUG`: Enable/disable debug mode (default: True)
- `FLASK_HOST`: Server host (default: 0.0.0.0)
- `FLASK_PORT`: Server port (default: 5000)

## License

MIT License 