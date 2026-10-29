# Instalación PostgreSQL, CloudNativePG y pgAdmin — 30/10/2026

## Resultado

Instalados CloudNativePG 1.30.1, PostgreSQL 17.11 y pgAdmin 9.19 con imágenes ARM64 fijadas por digest. Las diez aplicaciones de Argo CD quedan Synced / Healthy, los cuatro nodos Ready y los dos pods de databases Running / Ready.

| Componente | Configuración |
| --- | --- |
| Operador | namespace cnpg-system, pi5 |
| PostgreSQL | databases/homelab-postgres, una instancia en pi5, 1Gi request / 2Gi límite |
| PGDATA | NAS .164:/mnt/d01tb/postgresql/pgdata, PV nfs-pv-01, Retain |
| Solicitud de volumen | 20Gi, vinculada a PV 1Ti; no implica cuota de carpeta |
| Base inicial | semaphore, propietario semaphore_app |
| pgAdmin | https://pgadmin.bearsfamily.aa, admin@bearsfamily.aa |
| Datos pgAdmin | /opt/pgadmin/data en pi5, PV local Retain |
| nginx | localhost:30091; SQL sin NodePort |
| Conexión pgAdmin | pgadmin_monitor, pg_monitor, sin superusuario; TLS verify-full |
| Dashboard | https://grafana.bearsfamily.aa/d/bearsfamily-postgresql |

La base está preparada para Semaphore; Semaphore todavía no está instalado. No hay alta disponibilidad ni PITR. No aumentar réplicas usando el mismo PV fijo. El portal welcome incluye el acceso a pgAdmin. No se ha modificado el mensaje de arranque solicitado anteriormente.

## Acceso y contraseñas

En pi5, para consultar únicamente la contraseña web de pgAdmin:

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n databases get secret pgadmin-web-auth -o jsonpath='{.data.password}' | base64 -d; echo
```

Usar el usuario admin@bearsfamily.aa en la web. El usuario SQL precargado es pgadmin_monitor. Las credenciales de Semaphore están en semaphore-db-auth (username/password) y las de monitorización en pgadmin-monitor-auth. Nunca copiarlas a Git, al diario o a OneDrive.

PostgreSQL para clientes internos: homelab-postgres-rw.databases.svc:5432. TLS verify-full y CA pública homelab-postgres-ca/ca.crt. No es necesario dar a las aplicaciones la clave privada de la CA. El NodePort web existe en las interfaces de los nodos; usar siempre la URL HTTPS de nginx. El certificado web sigue siendo el autofirmado doméstico existente, sin renovación automática.

## NAS y permisos

El usuario autorizó expresamente añadir permissions al montaje NTFS del disco de 1 TB y remontarlo sin formatear. Fstab original guardado en el NAS en /root/homelab-maintenance/ntfs-permissions-20261029-235444/fstab. UID/GID PostgreSQL 26:26 y modo 700 verificados. Los otros tres montajes no se modificaron. Sólo se recreó el objeto PV nfs-pv-01 cuando estaba Available, sin claimRef ni referencias PVC, para cambiar la ruta a la subcarpeta. Datos conservados.

## Verificaciones realizadas

- Login HTTPS real de pgAdmin, sesión /browser/ y conexión precargada confirmados mediante su API. No se ha hecho una revisión visual del navegador ni un ensayo del Query Tool completo.
- TLS SQL 1.3 con nombre y CA validados desde pgAdmin; conexiones sin TLS rechazadas. pgadmin_monitor no puede conectar a semaphore.
- fsync=on. Marcador de prueba conservado tras eliminar y recrear únicamente el pod PostgreSQL; esquema temporal retirado.
- Una copia puntual cifrada de la base inicial semaphore, guardada en /var/backups/homelab-postgresql de pi5, se descifró y restauró en una base temporal separada. Era una base vacía: esto no equivale a una recuperación completa ni acredita un RPO/RTO.
- Prometheus: 11 destinos up, incluido el exporter CNPG. Consultas reales de disponibilidad, tamaños, conexiones y transacciones con datos. Dashboard de 8 paneles provisionado en Grafana.
- DNS pgadmin → 192.168.1.163. Argo, Grafana, Prometheus, qBittorrent y pgAdmin responden por HTTPS.
- GitOps manual, sin auto-sync, prune, force ni Replace. CRD grandes aplicadas por servidor con DisableClientSideApplyMigration=true. El passfile de pgAdmin conserva 0600, sin fsGroup que lo cambie a 0660.

## Incidencias y trabajo pendiente

**Almacenamiento:** al eliminar la base temporal de restauración, PostgreSQL registró Input/output error al recorrer su directorio y dejó archivos huérfanos en PGDATA/base/16401. El NAS permite listarlo y no muestra errores de kernel en la comprobación posterior; montajes privados NFS de sólo lectura también lo listan. La causa no está confirmada. No se han eliminado manualmente esos archivos. El servicio responde, pero no se considera completada la validación de fiabilidad de NFS/NTFS para datos importantes. Investigar el problema y preferir un filesystem Linux (por ejemplo ext4) en el almacenamiento exportado, con copia y migración preparadas antes de cualquier cambio. No se autoriza formatear nada por este documento.

**Copias periódicas:** no instaladas. La revisión automática rechazó el temporizador por la recopilación periódica de credenciales sin autorización explícita. Se ha solicitado aprobación para limitarlo a bases/roles, tres Secrets de acceso y ajustes pgAdmin, cifrado local, 03:15 Europe/Madrid y retención 30 días. El script preparado no está activado. La copia puntual no contiene credenciales ni ajustes pgAdmin. Su clave permanece en /root/.config/homelab-postgresql/backup-passphrase de pi5, fuera de OneDrive. Hace falta una copia privada independiente de esa clave y destino adicional antes de considerar recuperación ante pérdida de pi5.

No están completados: recuperación integral desde cero, copias externas/PITR, alertas de copia, ensayo de parada del NAS, instalación de Semaphore y evaluación con carga real. Revisar estas fases antes del uso productivo.

## Fuentes oficiales

- https://cloudnative-pg.io/docs/1.30/
- https://www.pgadmin.org/docs/pgadmin4/9.19/container_deployment.html
- https://www.pgadmin.org/docs/pgadmin4/9.19/import_export_servers.html

Manifiestos y documentación publicados en gitops-homelab y nginx-sites-available. Las evidencias públicas de esta instalación están en evidencias/instalacion-postgresql-20261030. No incluyen Secrets vivos ni contraseñas.
