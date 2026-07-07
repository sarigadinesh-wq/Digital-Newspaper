FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if any are needed in the future (currently slim python is sufficient)
# Copy requirements list from backend and run pip install
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend files into container workdir
COPY backend/ .

# Copy frontend assets into the /app/static folder
COPY frontend/ /app/static/

EXPOSE 8000

# Run uvicorn server exposing the integrated application on port 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
