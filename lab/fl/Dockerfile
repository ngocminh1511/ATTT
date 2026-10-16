# FL server: flower-superlink. ServerApp chạy trong container này nên cần cài đủ thư viện.
FROM python:3.12-slim-bookworm
WORKDIR /app
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu
COPY pyproject.toml README.md ./
COPY fl_ddos ./fl_ddos
RUN pip install --no-cache-dir .
ENV FL_DDOS_DATA=/app/data FL_DDOS_RESULTS=/app/results FLWR_DISABLE_RUNTIME_DEPENDENCY_INSTALLATION=1
EXPOSE 9091 9092 9093
