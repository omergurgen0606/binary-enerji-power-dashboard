FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api.py create_user.py generate_claim_code.py .

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
