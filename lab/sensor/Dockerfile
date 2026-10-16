# Sensor = Suricata + FL client (flower-supernode) + detector realtime trong cùng container.
# Build context: thư mục gốc dự án (xem lab/docker-compose.yml).
FROM python:3.12-slim-bookworm

RUN apt-get update \
 && apt-get install -y --no-install-recommends suricata iproute2 procps \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY pyproject.toml README.md ./
COPY fl_ddos ./fl_ddos
RUN pip install --no-cache-dir .
COPY detector ./detector

COPY lab/sensor/suricata.yaml /etc/suricata/suricata.yaml
COPY lab/sensor/local.rules /etc/suricata/rules/local.rules
RUN touch /etc/suricata/rules/ml.rules
COPY lab/sensor/entrypoint.sh /entrypoint.sh
RUN sed -i 's/\r$//' /entrypoint.sh && chmod +x /entrypoint.sh

ENV FL_DDOS_DATA=/app/data FL_DDOS_RESULTS=/app/results FL_DDOS_LOCAL_DATA=/data/local.parquet \
    MODEL=/app/results/global.pt FLWR_DISABLE_RUNTIME_DEPENDENCY_INSTALLATION=1
ENTRYPOINT ["/entrypoint.sh"]
