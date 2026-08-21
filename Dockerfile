FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create required directories
RUN mkdir -p /app/downloads /app/logs /app/data /app/temp

# Run the bot
CMD ["python", "main.py"]
