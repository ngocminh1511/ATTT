#!/usr/bin/env bash
# Khởi động 3 tiến trình của sensor:
#   1) Suricata nghe interface của mạng chi nhánh (SITE_SUBNET)
#   2) flower-supernode: FL client, chỉ nói chuyện với server qua mạng mgmt
#   3) detector/realtime.py: chờ tới khi có mô hình toàn cục ($MODEL) rồi phát hiện realtime
set -euo pipefail

IFACE=$(ip -o -4 addr show | awk -v s="$SITE_SUBNET" 'index($4, s) == 1 {print $2; exit}')
if [ -z "${IFACE:-}" ]; then echo "Không tìm thấy interface cho subnet $SITE_SUBNET"; ip -o -4 addr; exit 1; fi
echo "[sensor] Suricata nghe trên $IFACE (subnet ${SITE_SUBNET}0/24)"

rm -f /var/run/suricata.pid
suricata -c /etc/suricata/suricata.yaml -i "$IFACE" -k none &

flower-supernode --insecure --superlink "$SUPERLINK" \
  --node-config "partition-id=${PARTITION_ID} num-partitions=${NUM_PARTITIONS}" &

until [ -f "$MODEL" ]; do echo "[sensor] Chờ mô hình toàn cục $MODEL ..."; sleep 15; done
until [ -f /var/log/suricata/eve.json ]; do sleep 1; done
python /app/detector/realtime.py --model "$MODEL" --eve /var/log/suricata/eve.json \
  --min-flows "${MIN_FLOWS:-50}" ${DROP_RULES:+--drop-rules /etc/suricata/rules/ml.rules} &

wait -n
