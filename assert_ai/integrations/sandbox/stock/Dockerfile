# Copyright (c) Microsoft Corporation.
# Licensed under the MIT License.

FROM python:3.11-bookworm

WORKDIR /app
COPY server.py /app/server.py
RUN chmod 0444 /app/server.py

USER 65534:65534
EXPOSE 8080
CMD ["python", "/app/server.py"]
