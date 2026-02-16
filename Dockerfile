FROM python:3.10-slim

WORKDIR /app

# 1. Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 2. Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# 3. CRITICAL: Install CPU-only Torch AND Sentence-Transformers
# We install them together to lock in the CPU versions before requirements.txt runs
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install --no-cache-dir sentence-transformers==2.5.1

# 4. Copy and install the rest of the requirements
COPY requirements.txt .
RUN pip install --no-cache-dir --timeout 1000 --retries 10 -r requirements.txt

# 5. Pre-download the embedding model (to cache it in the image layer)
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# 6. Copy application code (done last to maximize cache efficiency)
COPY . .

# Default command
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]