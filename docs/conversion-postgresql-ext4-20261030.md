# Conversión del almacenamiento PostgreSQL a ext4

Fecha: **30/10/2026 · Europe/Madrid**. Ejecutado por solicitud expresa del usuario, que indicó que el disco de 1 TB no tenía datos que conservar.

## Resultado

El disco de 1 TB del NAS 192.168.1.164 fue vaciado y reparticionado con GPT y una partición ext4. PostgreSQL se reinicializó mediante CloudNativePG y Argo CD, usando la misma exportación, el PV nfs-pv-01 y las credenciales de acceso existentes. La base semaphore está preparada, pero Semaphore aún no está instalado.

| Parámetro | Estado actual |
|---|---|
| Modelo / serie | GB1000EAMYC / WMATV2570914 |
| WWN | 0x50014ee056c5f4a6 |
| UUID ext4 | 3e1e114c-f683-46f3-8167-d888d1e28d71 |
| Montaje NAS | /mnt/d01tb |
| Carpeta PostgreSQL | /mnt/d01tb/postgresql, UID/GID 26:26, 0700 |
| Exportación NFS | /mnt/d01tb a 192.168.1.0/24, sync y mountpoint |
| Ruta del PV | 192.168.1.164:/mnt/d01tb/postgresql |
| fstab | UUID=3e1e114c-f683-46f3-8167-d888d1e28d71 /mnt/d01tb ext4 defaults,nofail,x-systemd.device-timeout=15s 0 2 |
| PostgreSQL | 17.11, una instancia en pi5, fsync=on |
| pgAdmin | https://pgadmin.bearsfamily.aa, usuario admin@bearsfamily.aa |

Discos de 4, 8 y 12 TB: montajes NTFS y exportaciones conservados. NFS y Samba siguen activos; la copia existente de 4 a 8 TB mantiene su horario de las 02:00 Europe/Madrid. No se ejecutó una copia completa ni se reinició el NAS. No se activaron las copias periódicas PostgreSQL pendientes de aprobación.

## Ejecución

1. Verificados hashes del paquete, identidad SSH de pi5/NAS, disco por UUID, serie, WWN, modelo y tamaño; comprobaciones sin cambios correctas. El cliente NFS de Windows de esta sesión no mostraba unidades montadas.
2. pgAdmin detenido; homelab-postgres hibernado limpiamente; Cluster y PVC de esa única instancia retirados. Se conservó nfs-pv-01 con Retain, se retiró su claimRef comprobando el UID y se verificó ausencia de montajes de kubelet. Auto-sync continuó deshabilitado.
3. Retirada sólo la exportación NFS de 1 TB; desmontaje normal. Eliminada la firma NTFS y creada GPT con una única partición Linux. El script se detuvo por una consulta lsblk sin salida jerárquica explícita. Se inspeccionó la GPT, la identidad física y el UUID de la partición recién creada; se corrigió lsblk con --tree y se continuó desde esa partición **sin repetir wipefs ni sfdisk**. Una segunda comprobación de recuperación se detuvo conservadoramente porque blkid devolvía código 0 con metadatos de partición, pero sin TYPE. wipefs confirmó ausencia de firmas y se permitió continuar sólo tras ambas comprobaciones. No se sobrescribió ningún filesystem nuevo.
4. Creado ext4 con metadatos y journal inicializados; actualizado fstab por UUID, montaje y carpeta postgresql. Pasaron 128 ciclos de escritura/rename/fsync, recorrido y borrado con UID 26. Restaurada únicamente esa exportación NFS.
5. En pi5 pasó la misma prueba NFS con 128 archivos. Argo recreó PostgreSQL y pgAdmin; Secrets de acceso conservados, certificados gestionados por CNPG. Los Services SQL cambiaron de ClusterIP, pero los clientes utilizan DNS estable.
6. Actualizados /etc/homelab-nas/config.json y el verificador instalado para reconocer ext4 sólo en d01tb; los otros discos mantienen su perfil NTFS. Health service ejecutado: Result=success. No se volvió a ejecutar el instalador completo ni se reiniciaron servicios de almacenamiento.

Registro del NAS: `/root/homelab-maintenance/d01tb-ext4-20261030T210558Z/`. Guarda estado, fstab/configuración anterior, inventario y tabla de particiones; no es una copia de los datos borrados. Informe público en `/home/alvarense/resultado-postgresql-ext4.json`.

## Pruebas reales y cierre de la incidencia

- Restauradas **512 filas** en una segunda base temporal; coinciden cantidad, suma de IDs y hash del contenido.
- Las dos bases temporales se eliminaron del catálogo. Los directorios de sus OID **16393 y 16401 no existen en el NAS** tras el borrado. El escenario que falló sobre NTFS ya no se reproduce con ext4; no se hizo una limpieza manual de archivos huérfanos.
- Marcador de persistencia conservado después de recrear el pod PostgreSQL; esquema de prueba retirado. Se esperó la parada limpia y el nuevo pod Ready, sin force.
- SQL TLS 1.3 con verify-full validado desde pgAdmin. El usuario pgadmin_monitor no es superusuario ni puede conectar a semaphore; conexiones SQL sin TLS rechazadas.
- Login HTTPS y conexión precargada de pgAdmin correctos después del reinicio. No se ha realizado revisión visual ni prueba completa del Query Tool.
- **10 Applications Synced / Healthy**, **4 nodos Ready**, PostgreSQL/pgAdmin Running/Ready y **11 destinos Prometheus up**. Dashboard PostgreSQL con datos. Argo, Grafana, Prometheus, qBittorrent y pgAdmin responden por HTTPS.
- Paquete NAS con perfil mixto ext4/NTFS: **41 pruebas offline correctas**. Paquete de conversión: corregida la consulta de árbol; formato ejecutado y evidencias guardadas.

Se considera resuelta la incidencia observada de borrado de bases para el escenario probado. Esto no demuestra su causa exacta ni sustituye pruebas prolongadas de carga, recuperación ante pérdida del NAS, alimentación/USB y copias independientes. Las copias periódicas y la instalación de Semaphore permanecen pendientes.

## Configuración y documentación actualizadas

Paquete nas-raspberry-ubuntu (perfil, código, pruebas y hashes), perfil instalado del NAS, copia pública del instalador en el NAS, protección del nuevo UUID en scripts de instalación limpia, paquete de conversión y documentación activa. Las capturas históricas conservan su UUID de origen y se marcan como históricas cuando corresponde: no deben sustituir el perfil real nuevo.

Las contraseñas no han cambiado ni se han guardado en Git, OneDrive o este informe. Evidencias públicas: `evidencias/conversion-ext4-20261030/`. El diario recoge autorización, ejecución, corrección, comprobaciones y resultados.
