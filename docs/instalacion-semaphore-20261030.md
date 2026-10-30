# Instalación de Semaphore Community

Fecha: **30/10/2026 · Europe/Madrid**.

## Resultado

Plan revisado con PostgreSQL ya instalado y ext4 validado. Se mantuvo la arquitectura elegida y se concretaron versión, configuración de la imagen, bootstrap, claves persistentes, retención y pruebas. Instalación base de las fases 0–5 realizada; despliegues automáticos de nginx y acceso remoto a hosts siguen pendientes de las fases 6–7.

| Elemento | Configuración instalada |
|---|---|
| Versión | Semaphore Community v2.19.17, imagen linux/arm64 |
| Imagen | docker.io/semaphoreui/semaphore:v2.19.17@sha256:9ec6b4ebc0f1028399fad22beb70bb0ae8d3f785d9b0bb30f23ccde53c3300dd |
| Application | homelab-semaphore, sincronización manual |
| Namespace / nodo | semaphore / pi5 |
| Réplicas | Una, estrategia Recreate |
| URL | https://semaphore.bearsfamily.aa |
| Usuario web | admin |
| Contraseña web / claves | Secret semaphore/semaphore-web-auth, fuera de Git |
| Base | PostgreSQL existente: semaphore, propietario semaphore_app |
| Endpoint SQL | homelab-postgres-rw.databases.svc:5432 |
| TLS SQL | verify-full, CA pública en ConfigMap semaphore/postgresql-ca |
| Acceso SQL | Secret semaphore/semaphore-db-auth, copia privada limitada del original en databases |
| nginx | localhost:30090 → Service NodePort 30090 → contenedor 3000 |
| Recursos | Request 100 mCPU/256 MiB; límite 1 CPU/768 MiB |
| Ejecución | Local en contenedor, UID 1001, una tarea simultánea |
| Tiempo máximo / historial | 300 segundos / 100 ejecuciones por plantilla |
| Zona horaria | Europe/Madrid, tanto servidor/scheduler como variables de las tareas piloto |
| Programaciones al cierre | Ninguna; las pruebas puntuales se retiraron |

No se creó otro PostgreSQL ni un PVC para una base embebida. Proyectos, usuarios, plantillas e historial viven en PostgreSQL sobre nfs-pv-01/ext4. La configuración generada, home y caché son efímeros; las claves de cifrado/cookies se conservan en Secret y se suministran en cada arranque. No cargar archivos persistentes adicionales sin definir su almacenamiento y copia.

## Acceso

En pi5, consultar privadamente la contraseña:

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n semaphore get secret semaphore-web-auth -o jsonpath='{.data.password}' | base64 -d; echo
```

Usuario `admin`. No guardar la salida en Git, OneDrive, logs o diario. El welcome existente incluye el acceso y un nodo de Semaphore; conserva logo, favicon y las terminales anteriores.

## Primer proyecto y tareas

Proyecto **Homelab**, máximo una tarea simultánea, con repositorio local de sólo lectura `/opt/homelab/tasks` procedente de un ConfigMap. Scripts públicos también en GitOps bajo automation/semaphore/tasks. Entrada de Key Store de tipo none para ese repositorio: no se importó la clave SSH personal ni se añadieron credenciales Git.

- **Diagnostico local:** fecha/hora, UID y versiones de Git/Python, sin modificar hosts.
- **Fallo controlado:** salida intencional con código 7 para comprobar estado y logs. Que esta plantilla aparezca en error al ejecutarla es lo esperado.
- Grupo de variables **Zona horaria Homelab**, TZ=Europe/Madrid, aplicado a ambas plantillas. El ejecutor limpia el entorno del servidor, por lo que se explicitó TZ para las tareas.

No se ha configurado seguimiento del repositorio nginx, webhook, recargas automáticas, notificaciones ni permisos remotos. Argo continúa manual. Semaphore no monta el token de ServiceAccount, filesystem del host, socket del runtime o kubeconfig; no recibió Role/ClusterRoleBinding.

## Verificaciones

- Credenciales SQL probadas desde un Job temporal en el namespace semaphore: TLS 1.3 con CA/nombre verificados, creación/escritura de tabla en transacción revertida y rechazo de contraseña incorrecta, CA incorrecta y conexión sin TLS. Rol sin superusuario, CREATEDB o CREATEROLE.
- Login HTTPS, cookie Secure, proyecto visible y conexión WebSocket autenticada: upgrade 101.
- Tarea local correcta; fallo controlado marcado como error; ejecución programada run_at puntual correcta y eliminada al terminar. Comprobada salida Europe/Madrid (+01:00 en esta fecha). No se ha simulado un cambio de hora DST.
- Pod recreado: misma sesión autenticada válida sin repetir login, proyecto y plantillas conservados, claves idénticas e historial disponible preservado. La política inicial demasiado corta de historial se amplió a 100 por plantilla; la concurrencia global y del proyecto se mantiene en uno.
- Once Applications Synced / Healthy, cuatro nodos Ready; pod actual sin reinicios. Once targets Prometheus up. Argo, Grafana, Prometheus, qBittorrent, pgAdmin y Semaphore responden por HTTPS.
- Uso de memoria observado de Semaphore aproximadamente 10,2 MiB en reposo; es una muestra, no el consumo de trabajos Ansible/Terraform ni una garantía de capacidad.
- JavaScript inline del welcome comprobado con Node; no se ha realizado una revisión visual de navegador.

## Ajustes durante el arranque

La inyección automática de variables de Services generaba SEMAPHORE_PORT=tcp://... y la aplicación lo rechazaba. Se desactivó enableServiceLinks y se fijó SEMAPHORE_PORT=:3000. El piloto usaba inicialmente la opción GNU de date; se sustituyó por date -Iseconds compatible con BusyBox. Los arranques y pruebas fallidos de preparación no implican que el pod final esté reiniciándose. No hubo cambios de arquitectura ni relajación de TLS.

La imagen original permite SSH sin verificar huellas; se sustituyó su archivo de configuración por otro que exige StrictHostKeyChecking yes. Todavía no hay conexiones SSH remotas configuradas.

## Copias y límites de recuperación

Copia previa cifrada en pi5: /var/backups/homelab-postgresql/semaphore-preinstall-20261030T213501Z.tar.gpg.

Copia posterior cifrada: /var/backups/homelab-postgresql/semaphore-postinstall-20261030T214821Z.tar.gpg. Incluye sólo la base semaphore y sus dos Secrets de acceso/claves; no es una exportación de Secrets del clúster. Se verificó el descifrado y se restauró la base en una base temporal aislada, sin lanzar un servidor Semaphore contra ella ni activar tareas. Coincidieron recuentos de proyecto, usuario, plantillas y Key Store; base temporal eliminada.

Clave privada de esas copias en /root/.config/homelab-postgresql/backup-passphrase de pi5. No se exportó a OneDrive. Falta guardar una copia privada independiente de clave y archivos cifrados; perder pi5 perdería esas copias locales. No se han activado copias periódicas, cuyo permiso sigue pendiente. El ensayo SQL no equivale a restaurar toda la aplicación y descifrar credenciales reales en un despliegue aislado; no se declara un RPO/RTO.

La CA pública se copia desde databases por un bootstrap privado. No se sincroniza automáticamente entre namespaces: documentar y realizar su actualización coordinada cuando CNPG renueve/cambie la CA. No copiar ca.key ni dar a Semaphore acceso a Secrets de otros namespaces.

## Siguientes fases

Instalación del servidor lista para el piloto local. Quedan el mecanismo restringido de despliegue nginx, pruebas de promoción/reversión y detección de commits (fases 6–7), copias periódicas/externas y recuperación integral, alertas de servicio y evaluación con carga real. No se han activado automáticamente por instalar la interfaz.

Fuentes oficiales revisadas: https://github.com/semaphoreui/semaphore/releases/tag/v2.19.17 y código de ese tag; https://semaphoreui.com/docs/admin-guide/installation/docker. Evidencias sin credenciales en evidencias/instalacion-semaphore-20261030.
