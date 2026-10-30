# pgAdmin: contraseña no aplicable al abrir una base

Fecha: 30/10/2026.

La captura muestra fe_sendauth: no password supplied. El diagnóstico confirmó que el servidor Homelab PostgreSQL · monitor utiliza pgadmin_monitor y un passfile 0600 con entrada exclusivamente para postgres. La base semaphore aparecía en el explorador porque no había filtro de bases. Abrirla no encontraba una entrada de contraseña; además ese rol no tiene CONNECT a semaphore. No es un error de ext4, caída del servicio, contraseña web o IP de pod. La IP 10.107.15.141 de la captura es la ClusterIP actual; la configuración usa el DNS estable homelab-postgres-rw.databases.svc.

Corrección: se estableció db_res=[postgres] en el servidor existente mediante la API autenticada de pgAdmin; se publicó DBRestriction=postgres en servers.json del ConfigMap GitOps para futuros bootstraps. No se ampliaron permisos SQL ni se modificaron contraseñas. Se verificaron login HTTPS, conexión, lista de bases (sólo postgres) y lectura de sus propiedades mediante las mismas API que utiliza el navegador. No fue necesario reiniciar PostgreSQL o pgAdmin.

En el navegador, cerrar el aviso, recargar pgAdmin y actualizar/reconectar Homelab PostgreSQL · monitor. La conexión de monitorización sólo ofrece postgres. Para administrar semaphore se necesita una conexión separada, con su propietario semaphore_app; no usar ni ampliar pgadmin_monitor para ese fin.

## Conexión separada para semaphore, si se decide añadirla

Host homelab-postgres-rw.databases.svc, puerto 5432, mantenimiento semaphore, usuario semaphore_app, SSL verify-full y CA pública certs/ca.crt dentro del almacenamiento del usuario pgAdmin. Filtrar bases a semaphore. La contraseña procede de Secret databases/semaphore-db-auth; no es la contraseña web de pgAdmin. No se ha creado esa conexión ni copiado esa credencial a pgAdmin en esta corrección.

Puede consultarse privadamente en pi5 cuando sea necesario:

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n databases get secret semaphore-db-auth -o jsonpath='{.data.password}' | base64 -d; echo
```

No guardar el resultado en Git, OneDrive o el diario. El passfile de monitorización conserva su entrada limitada y modo 0600. El filtro de la interfaz no sustituye los permisos SQL: el aislamiento ya está aplicado en PostgreSQL.

Fuentes: https://www.postgresql.org/docs/17/libpq-pgpass.html y documentación/código de la imagen pgAdmin 9.19 instalada. Evidencias sin contraseñas: evidencias/pgadmin-conexion-20261030/.
