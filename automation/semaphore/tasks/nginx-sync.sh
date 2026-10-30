#!/bin/bash
set -euo pipefail
exec timeout -s TERM -k 10 190 ssh -T -F /dev/null \
  -i /run/secrets/nginx-ssh/id_ed25519 \
  -o IdentitiesOnly=yes -o BatchMode=yes \
  -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile=/opt/homelab/tasks/pi5_known_hosts \
  -o ConnectTimeout=10 -o ServerAliveInterval=10 -o ServerAliveCountMax=3 \
  -o ClearAllForwardings=yes \
  semaphore-nginx@192.168.1.163 deploy-nginx
