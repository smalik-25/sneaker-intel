# Dashboard image. Reads the marts from Postgres via DATABASE_URL at runtime.
FROM python:3.11-slim

# Don't write .pyc files; flush logs straight to the container output.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install deps first so this layer caches across code changes.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as a non-root user.
RUN useradd --create-home appuser
USER appuser

EXPOSE 8501

# Bind to the platform-provided $PORT when present (Railway/Render), else 8501.
CMD ["sh", "-c", "streamlit run dashboard/app.py --server.port=${PORT:-8501} --server.address=0.0.0.0"]
