FROM python:3.10-slim

WORKDIR /app

# Copy and install dependencies first for better caching
COPY requirements.txt .
# Install Faiss dependencies (requires specific system packages)
RUN apt-get update && apt-get install -y libopenblas-dev
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY . /app

# Expose the port where Uvicorn will run
EXPOSE 8000

# Command to run the FastAPI app with Uvicorn
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]