# Use the official Playwright Python image
FROM mcr.microsoft.com/playwright/python:v1.41.0-jammy

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers (Chromium only for efficiency)
RUN playwright install chromium

# Copy the rest of the application
COPY . .

# Expose the API port
EXPOSE 8000

# Command to be overridden by docker-compose for worker vs api
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
