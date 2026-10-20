FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN useradd -m app && mkdir -p /data && chown app:app /data
USER app
CMD ["uvicorn","api.main:app","--host","0.0.0.0","--port","8000","--no-access-log"]
