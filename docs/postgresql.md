# PostgreSQL, CloudNativePG y pgAdmin

Una instancia PostgreSQL 17.11 en pi5. Datos en NAS 192.168.1.164:/mnt/d01tb/postgresql, nfs-pv-01, Retain. No aumentar instancias con este volumen fijo. La petición 20Gi no limita el uso real del disco. NTFS montado con permissions; UID/GID 26, modo 700.

Orden manual: homelab-root, homelab-cnpg-operator, homelab-storage (recrear únicamente el PV libre al cambiar la ruta), homelab-postgresql, homelab-pgadmin. Sin auto-sync, prune ni force. Secrets creados fuera de Git: semaphore-db-auth, pgadmin-monitor-auth y pgadmin-web-auth en databases. El operador genera sus certificados.

pgAdmin: https://pgadmin.bearsfamily.aa, usuario admin@bearsfamily.aa. Contraseña consultable localmente con kubectl; nunca se guarda en este repositorio. Conexión precargada con pgadmin_monitor (pg_monitor, no superusuario), TLS verify-full y CA pública montada. El passfile privado reside en /opt/pgadmin/data/storage/admin_bearsfamily.aa/monitor.pgpass en pi5.

La base semaphore es de semaphore_app; PUBLIC no tiene CONNECT. pgAdmin conserva sus ajustes en un PV local de pi5, /opt/pgadmin/data, y no puede migrar automáticamente. El servicio PostgreSQL es interno. Argo CD protege volúmenes y namespaces frente a borrado accidental.

NFS/NTFS y una única instancia no ofrecen alta disponibilidad ni sustituyen copias de seguridad. Mantener fsync activado; no habilitar WAL separado o réplicas sobre el mismo directorio.

Fuentes: https://cloudnative-pg.io/docs/1.30/ y https://www.pgadmin.org/docs/pgadmin4/9.19/container_deployment.html
