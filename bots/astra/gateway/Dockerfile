FROM python:3.13-slim

WORKDIR /app

RUN pip install --no-cache-dir poetry \
    && poetry config virtualenvs.create false

COPY pyproject.toml poetry.lock ./
RUN poetry install --no-root --no-directory --only main

COPY src/ ./src/
RUN poetry install --only main

RUN useradd -m -u 1000 -s /bin/bash astra
USER astra

ENV PORT=8080

CMD ["uvicorn", "astra_gateway.app:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
