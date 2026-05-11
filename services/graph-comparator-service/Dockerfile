# Basis-Image: offizielles, schlankes Python-Image.
FROM python:3.12-slim

# Arbeitsverzeichnis im Container. Alle folgenden Befehle laufen hier. /app ist Standard.
WORKDIR /app

# Abhaengigkeiten installieren
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Code kopieren
COPY src/ ./src/

EXPOSE 8000

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]