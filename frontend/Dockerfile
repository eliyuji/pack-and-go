FROM python:3.10-slim 

# Set the working directory
WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
# Install Faiss dependencies (even if only for imports/type hints)
RUN apt-get update && apt-get install -y libopenblas-dev
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code (including frontend.py)
COPY . /app

# Expose the port where Streamlit will run
EXPOSE 8501

# Command to run the Streamlit app
# --server.address 0.0.0.0 is crucial for containers
CMD ["streamlit", "run", "frontend/frontend.py", "--server.port", "8501", "--server.address", "0.0.0.0"]