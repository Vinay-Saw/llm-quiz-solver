# Use Python 3.11
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies required for Playwright and generic usage
# We need curl/wget to download keys if necessary, and basic tools
RUN apt-get update && apt-get install -y \
    curl \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user 'user' with UID 1000 (Required by Hugging Face)
RUN useradd -m -u 1000 user

# Switch to this user
USER user

# Set home to the user's home directory
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Set working directory to the user's home
WORKDIR $HOME/app

# Copy requirements first (optimization)
COPY --chown=user:user requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Install Playwright Browsers
RUN playwright install chromium

# Copy the rest of the application
COPY --chown=user:user . .

# Expose port 7860 (Standard Hugging Face Spaces port)
EXPOSE 7860

# Start the application using uvicorn
# Note: We bind to 0.0.0.0 and port 7860
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "7860"]
