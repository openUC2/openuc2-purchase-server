FROM python:3.11-slim

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the server script and frontend template
COPY Purchase_Ledger.py index.html ./

# Expose the application port
EXPOSE 5050

# Set environment variables for Flask binding
ENV HOST=0.0.0.0
ENV PORT=5050

# Run the application
CMD ["python", "Purchase_Ledger.py"]
