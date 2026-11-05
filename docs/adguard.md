# AdGuard Home instalado — 05/11/2026

## Acceso y uso

Panel: **https://adguard.bearsfamily.es**. También aparece en el menú de aplicaciones del home y en su topología.

- Usuario: **bearsfamily**.
- Contraseña: archivo privado del PC `C:\Users\aalva\Documents\Codex\ia-workspace-runtime\adguard-home\secrets\acceso.txt`.
- Credenciales y clave de copias fuera de Git y OneDrive. No compartir capturas del registro de consultas sin revisarlas.

El filtrado ya está activo para los dispositivos que consultan `192.168.1.163`. El usuario cambió el DHCP del router; una renovación del PC confirmó que dejó de anunciar el DNS público de Movistar. El router devuelve `.163` dos veces: ambas entradas apuntan al mismo DNS doméstico.

Reconecta el Wi-Fi o renueva la concesión de los demás equipos para que recojan el cambio. La navegación y la web interna funcionan en el PC y en un segundo dispositivo móvil/tablet, según la comprobación del usuario. Dispositivos con DNS estático, DNS privado de Android o DoH propio pueden evitar este filtro; no se ha impuesto interceptación.

## Arquitectura activa

```text
Clientes LAN / WireGuard → dnsmasq .163:53
                           ├─ nombres privados → registros locales
                           └─ consultas externas → AdGuard .163:30553
                                                     └─ Cloudflare / Quad9 por DoH
Panel HTTPS → nginx → localhost:30094 → AdGuard
```

| Elemento | Configuración |
| --- | --- |
| Imagen | `adguard/adguardhome:v0.107.80@sha256:198924ddb1cd509677e8101b138f58d985a6f0da6502a2fd0a1910e4b0f942b8` |
| Namespace / Argo CD | `dns-filter` / `homelab-adguard` |
| Nodo y estrategia | pi5 `.163`, una réplica, `Recreate`; sync manual, sin Prune |
| DNS / web del pod | TCP+UDP 5353 / TCP 3000 |
| Services | DNS NodePort 30553, `externalTrafficPolicy: Local`; panel NodePort 30094 |
| Recursos | Petición 100m/128Mi; límite 500m/512Mi |
| Persistencia | PV locales nuevos `adguard-conf-pv` y `adguard-work-pv`, Retain; 256Mi y 2Gi nominales |
| Directorios | `/var/lib/homelab-apps/adguard-home/conf` y `/work` |
| Registro / estadísticas | Retención 24 h / 7 d |
| Lista inicial | AdGuard DNS filter; 189.896 reglas al instalar, actualización cada 24 h |
| Upstreams | DoH Cloudflare yQuad9; bootstrap1.1.1.1/9.9.9.9, sin retorno al DNS doméstico |

Los tamaños de PV de directorio son nominales, no cuotas físicas. Los datos de AdGuard son locales para no depender del NAS al resolver DNS. No se han reutilizado los discos/PVC de otras aplicaciones. La configuración mutable vive en el PVC, no en un ConfigMap que la interfaz pueda sobrescribir.

Se ejecuta como UID/GID10001, sin token Kubernetes, sin capacidades Linux, con raíz de solo lectura y sin hostNetwork/hostPort. La imagen oficial tenía metadatos de capacidad en el binario que impedían arrancarlo con todas las capacidades retiradas. Un initContainer no privilegiado copia el binario, sin esos metadatos, a un volumen temporal; el contenedor principal lo monta de solo lectura. La ejecución real confirmó `CapEff=0` y `NoNewPrivs=1`.

No se activaron DHCP en AdGuard, filtros familiares, servicios bloqueados, listas adicionales masivas ni nuevos reenvíos de puertos en el router. El panel nginx admite LAN y el origen de pods de pi5 utilizado por la VPN, además de autenticación en AdGuard.

## Comprobaciones realizadas

- Cuatro nodos Ready y 17 Applications `Synced/Healthy`; pod actual de AdGuard Running/Ready y cero reinicios.
- Cien consultas públicas por TCP/UDP sin timeouts. Mediana observada46 ms y máximo 135 ms, incluyendo la invocación de `dig`; no es una promesa de latencia de red.
- Regla temporal bloqueada por TCP/UDP y motivo `FilteredBlackList` comprobado en el registro. La regla de prueba se retiró.
- Dominio publicitario real bloqueado; consultas permitidas resuelven normalmente desde el PC.
- Webs internas, nodos y NAS conservan sus IP; `vpn.bearsfamily.es` y TXT ACME siguen públicos. CoreDNS resuelve Kubernetes y los nombres privados.
- Panel HTTPS con certificado validado y login web comprobado en Edge sin perfil personal.
- Reinicio del pod con filtros y acceso persistentes. Bypass de emergencia probado y modo filtrado reactivado.
- Copia cifrada íntegra en el NAS, restauración aislada en un proceso secundario ligado solo a loopback del pod: login y bloqueo DNS recuperados. No se publicó esa instancia a la LAN.
- Servicio systemd de copias ejecutado expresamente: `Result=success`, `ExecMainStatus=0`.
- Home actualizado a26 componentes y 17 Applications, enlace nuevo y diseño móvil comprobados.
- Usuario confirma web interna y navegación normal en móvil/tablet tras reconectar Wi-Fi.

La observación durante 24–48 h queda en curso. No se ha hecho una prueba nueva de VPN desde red móvil, de todos los dispositivos ni de recuperación completa tras formatear el clúster. El bloqueo DNS tampoco garantiza eliminar publicidad servida desde el mismo dominio que el contenido, como ciertos anuncios de YouTube.

## Copias y supervisión

- Copia diaria entre **03:35 y03:40, Europe/Madrid**. Retención en NAS: últimas 7 fechas diarias y 4 semanas; en el primer día todavía no existe ese histórico.
- AES-256-GCM con comprobación de integridad y SHA256 del archivo transferido.
- Destino: NAS`.164`, `/mnt/d01tb/adguard-backups`. Contiene únicamente copias cifradas.
- Clave: pi5`/var/lib/homelab-apps/adguard-home/private/backup-key.bin`; copia privada en el PC bajo `adguard-home\secrets\backup-key.bin`. Conservarla: sin ella no se podrán descifrar las copias.
- Durante una copia consistente, el DNS pasa brevemente a bypass, AdGuard se detiene y se reinicia, y después se reactiva el filtro. La resolución privada sigue en dnsmasq y la externa usa temporalmente el upstream anterior.
- Comprobación funcional cada 5 minutos: DNS público TCP/UDP, nombres privados, bloqueo y espacio. Registra estado en pi5; no manda correos ni notificaciones externas.

```bash
sudo systemctl list-timers 'homelab-adguard-*'
sudo systemctl status homelab-adguard-health.service --no-pager
sudo cat /var/lib/homelab-apps/adguard-home/private/health-latest.json
sudo journalctl -u homelab-adguard-backup.service --no-pager -n 30
sudo /usr/local/sbin/backup-adguard --restore-test
```

La última orden crea otra copia y comprueba una restauración aislada. Los datos y logs sin cifrar permanecen privados en pi5. No publicar el YAML real de AdGuard: contiene el hash de acceso y configuración privada.

## Recuperación rápida de DNS

Conecta por IP aunque fallen los nombres:

```bash
ssh alvarense@192.168.1.163
sudo /usr/local/sbin/homelab-adguard-dns status
sudo /usr/local/sbin/homelab-adguard-dns bypass
```

`bypass` conserva los registros privados y devuelve a dnsmasq su upstream anterior`80.58.61.250`. Elimina temporalmente el filtrado. No hay que añadir ese DNS público a los clientes ni al DHCP del router.

Después de corregir la incidencia:

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n dns-filter get pods,pvc
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n dns-filter logs deployment/adguard-home --tail=40
sudo /usr/local/sbin/homelab-adguard-dns enable
```

`enable` espera a que el bloqueo esté listo, valida dnsmasq y comprueba que los nombres privados, VPN y TXT no cambien. Si falla el cambio, recupera la configuración anterior. AdGuard depende de pi5: esta instalación no proporciona alta disponibilidad.

## Restaurar datos de la aplicación

En pi5, inspeccionar primero una copia cifrada local de su directorio privado:

```bash
sudo /usr/local/sbin/restore-adguard /var/lib/homelab-apps/adguard-home/private/backups/adguard-FECHA.agh
```

Sin `--execute` solo descifra y valida en un temporal privado. Sustituir`FECHA`por el nombre real. Para recuperar producción, añadir`--execute`después de revisar la copia: activa bypass, detiene únicamente AdGuard, conserva los directorios actuales en un respaldo privado, instala conf/work del archivo y verifica el arranque antes de reactivar el filtro. Esta ruta de producción se ha preparado e inspeccionado; la prueba ejecutada fue la restauración aislada, no una sustitución de producción.

Si se perdió pi5, recuperar antes los manifiestos, sus directorios/PV, la clave de cifrado privada del PC y una copia del NAS. No habilitar Argo contra directorios vacíos y publicar el asistente sin protección. Mantener las credenciales privadas de pi5/PC coherentes si se cambia la contraseña.

## Archivos

- GitOps: `platform/adguard`, `clusters/home/adguard.yaml`.
- Operación: `automation/adguard` y `docs/adguard.md`.
- nginx: `adguard.conf` y `welcome.html`, publicación por Semaphore.
- Evidencias de esta entrega: imagen ARM64, pilotos, login/topología y verificaciones; sin historial real de consultas.
- Fuentes: [configuración oficial](https://adguard-dns.io/kb/adguard-home/configuration/) y [API de la versión instalada](https://github.com/AdguardTeam/AdGuardHome/blob/v0.107.80/openapi/openapi.yaml).
