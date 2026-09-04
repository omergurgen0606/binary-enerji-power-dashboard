FROM python:3.11-slim

# DejaVu: PDF raporlarindaki Turkce karakterler icin. reportlab'in yerlesik
# Helvetica'si Latin-1 oldugu icin g/s/i harflerini basamiyor, bu yuzden
# gomulebilir bir TTF sart.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# logo.png: PDF raporlarinin basligindaki marka isareti.
COPY api.py iyzico.py create_user.py generate_claim_code.py logo.png .

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
