#!/usr/bin/env bash
# Sinh traffic trong lab (mục 5.4). CHỈ nhắm vào victim trong mạng Docker cô lập.
#   /lab/traffic.sh <victim> [kịch bản]      vd: /lab/traffic.sh site1-victim all
# Kịch bản: benign | syn | udp | icmp | replay <pcap> | all
# Mỗi đợt tấn công ghi một dòng vào /logs/attack_log.csv (label,start,end,dest_ip,src_ip),
# dùng để gán nhãn dữ liệu lab và tính độ trễ phát hiện (lab/measure_latency.py).
set -uo pipefail

VICTIM=${1:?Cần tên victim, vd. site1-victim}
MODE=${2:-all}
DUR=${DUR:-90}          # 60–120 giây mỗi đợt
RATE=${RATE:-u100}      # hping3 -i u100 (~10k gói/s) thay cho --flood để laptop không treo
LOG=/logs/attack_log.csv
DST=$(getent hosts "$VICTIM" | awk '{print $1}')
[ -z "$DST" ] && { echo "Không phân giải được $VICTIM"; exit 1; }
[ -f "$LOG" ] || echo "label,start,end,dest_ip,src_ip" > "$LOG"

now() { date -u +%Y-%m-%dT%H:%M:%S.%6N+0000; }

attack() {  # attack <label> <lệnh...>
  local label=$1; shift
  local t0; t0=$(now)
  echo "[$t0] $label -> $VICTIM ($DST) trong ${DUR}s"
  timeout "$DUR" "$@" >/dev/null 2>&1
  echo "$label,$t0,$(now),$DST," >> "$LOG"
}

benign() {  # nền: curl + iperf3 ngắt quãng
  local end=$((SECONDS + ${1:-$DUR}))
  while [ $SECONDS -lt $end ]; do
    curl -s "http://$VICTIM/" >/dev/null
    sleep "0.$RANDOM"
  done
}

case "$MODE" in
  benign) benign ;;
  syn)    attack SYN  hping3 -S -p 80 -i "$RATE" --rand-source "$VICTIM" ;;
  udp)    attack UDP  hping3 --udp -p 53 -i "$RATE" --rand-source "$VICTIM" ;;
  icmp)   attack ICMP hping3 --icmp -i "$RATE" "$VICTIM" ;;
  replay) attack "${LABEL:-DNS}" tcpreplay -i "$(ip route get "$DST" | awk '{print $3; exit}')" --mbps 50 --loop 0 "${3:?pcap}" ;;
  all)
    benign 30
    benign $((DUR * 3 + 90)) &
    BG=$!
    attack SYN  hping3 -S -p 80 -i "$RATE" --rand-source "$VICTIM"; sleep 30
    attack UDP  hping3 --udp -p 53 -i "$RATE" --rand-source "$VICTIM"; sleep 30
    attack ICMP hping3 --icmp -i "$RATE" "$VICTIM"; sleep 30
    wait $BG ;;
  *) echo "Kịch bản không hợp lệ: $MODE"; exit 1 ;;
esac
