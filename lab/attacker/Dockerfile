FROM ubuntu:24.04
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      hping3 tcpreplay iperf3 curl iproute2 dnsutils ca-certificates \
 && rm -rf /var/lib/apt/lists/*
