#!/bin/bash
set -euo pipefail
printf 'Homelab: tarea local correcta\n'
date -Iseconds
printf 'Zona horaria: %s\n' "${TZ:-no-definida}"
printf 'UID: '; id -u
printf 'Git: '; git --version
printf 'Python: '; python3 --version
printf 'Sin cambios en hosts o cluster\n'
