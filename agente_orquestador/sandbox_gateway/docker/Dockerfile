FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN python -m pip install \
    --no-cache-dir \
    pytest==9.1.1

WORKDIR /workspace

USER 65534:65534