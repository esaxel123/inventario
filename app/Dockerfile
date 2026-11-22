FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Gunicorn sirve la app Flask en el puerto 5000.
# El lector NFC (main.py) corre como servicio aparte (compose.lector.yaml).
EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", \
     "--timeout", "60", "app:app"]
