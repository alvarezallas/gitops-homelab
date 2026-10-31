# On The Manga — desplegado en Kubernetes

Inicio: 30/10/2026. Publicación y verificación final: **31/10/2026 · Europe/Madrid**.

Web: **https://onthemanga.bearsfamily.aa**. Usa los usuarios y contraseñas de la instalación original. Es una publicación doméstica en la LAN; DNS y certificado del homelab existentes. No se abrieron puertos del router ni se modificó la confianza de Windows.

## Resultado

- Aplicación Java 21 / Spring Boot 3.5.16, perfil nuevo `cluster`, imagen ARM64 en pi5.
- PostgreSQL 17 de CloudNativePG existente: `homelab-postgres-rw.databases.svc:5432`, base **onthemanga**, propietario **onthemanga_app**. TLS `verify-full` con CA pública montada. Conexión real TLS1.3 comprobada. Rol sin superusuario, creación de bases o roles; 10 conexiones máximas y pool de aplicación de 5.
- Credenciales y clave estable Recordarme en Secret propio `onthemanga/onthemanga-app-auth`, leídas por config tree; copia de credenciales SQL en `databases/onthemanga-db-auth`. Sin contraseñas reales en repositorios, imagen o entregables. Nueva clave Recordarme porque el origen no tenía una configurada: será necesario volver a iniciar sesión.
- Una réplica Recreate, UID/GID10001, raíz de solo lectura, capacidades retiradas, sin token SA, kubeconfig, hostPath ni socket del host. Límites web 1CPU/768MiB. Probes: readiness con PostgreSQL; liveness independiente de la base.
- Objetos: PVC **onthemanga-objects** → PV **onthemanga-objects-pv**, NFS `/mnt/d01tb/onthemanga-objects` en NAS .164. Carpeta propia ext4 y UID10001, separada de `/mnt/d01tb/postgresql`; no se tocaron los discos de 4/8/12 TB.
- Mailpit v1.31.1 en el mismo namespace, autenticado, solo ClusterIP. SMTP interno1025, UI/API8025. Sin relay/forward externo. Datos SQLite en PVC local pi5 **mailpit-data**, `/var/lib/homelab-apps/onthemanga/mailpit`; no sobre NFS. Sin borrado automático por número de mensajes.
- PV con Retain y protección Prune/Delete; los PV pertenecen a homelab-storage y los PVC a homelab-onthemanga. Capacidades declaradas20Gi/1Gi no son cuotas del sistema de archivos.
- Argo CD: nueva Application **homelab-onthemanga**, `apps/onthemanga`; sincronización manual, sin prune/force/replace. Doce Applications Synced/Healthy al verificar.
- nginx: `onthemanga.conf` → `http://127.0.0.1:30092`; HTTPS, límite de carga100MiB y cabeceras de proxy. Publicado desde Git por el horario existente de Semaphore. No se cambió el helper privilegiado.

## Migración conservando los datos

Se detuvo únicamente el contenedor local de la aplicación para congelar escrituras. Docker PostgreSQL16 y los archivos `.data/objects` siguen conservados en el PC. El dump viajó por SSH al directorio privado root de pi5 y se restauró exclusivamente en una base nueva vacía de PostgreSQL17.

Se compararon contenidos completos de las **19 tablas**, mediante hashes de representaciones ordenadas, además de recuentos. Coincidieron antes de cualquier corrección de origen de correo. No había correos pendientes que requirieran cambiar enlaces.

| Contenido | Conservado |
|---|---:|
| Usuarios | 2 |
| Series | 2 |
| Capítulos | 2 |
| Páginas y archivos | 4 |
| Versiones Flyway aplicadas | 5 |

También se conservaron editoriales, membresías, géneros, citas, puntuaciones, auditoría y demás tablas. Contraseñas existentes conservadas como hashes; no se restablecieron ni se creó un administrador adicional. Los cuatro objetos se copiaron con las mismas claves y hashes. Las cuatro respuestas de imagen servidas por HTTPS coinciden con sus archivos persistentes.

El contenedor local **web-on-the-manga-app-1 permanece detenido** para evitar dos instalaciones divergentes. No se eliminaron su base, volumen o imágenes. No existe sincronización bidireccional: cambios nuevos se guardan en el clúster. El Mailpit local antiguo también se conserva, pero su historial de correos no se importó al buzón nuevo.

Dump original y diagnóstico privados: `/var/lib/homelab-migrations/onthemanga-20261030/` en pi5, solo root. No están en OneDrive/Git. No son una política de backup periódico.

## Consultar Mailpit de forma privada

No tiene dominio HTTPS ni NodePort. En una terminal **de pi5**, mantener abierto:

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n onthemanga port-forward --address=127.0.0.1 service/mailpit-web 18025:8025
```

En otra terminal **del PC**, usando tu identidad SSH configurada:

```powershell
ssh -N -L 18025:127.0.0.1:18025 alvarense@192.168.1.163
```

Abre **http://localhost:18025**, usuario **admin**. Para consultar la contraseña, en pi5:

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n onthemanga get secret mailpit-web-auth -o jsonpath='{.data.password}' | base64 -d; echo
```

El tramo HTTP queda dentro del túnel SSH y localhost. No publicar el port-forward en0.0.0.0. Cerrar ambas terminales retira el acceso temporal. El puerto18025 evita conflicto con Mailpit local8025.

La prueba final dejó un mensaje sintético de verificación interna con remitente/destinatario `.invalid`, sin datos personales ni envío externo. La UI/API deniega acceso sin credenciales y acepta el acceso autenticado.

## Validaciones realizadas

- `mvnw spotless:apply verify`: **26 pruebas**, cero fallos/errores/omitidas. Integración contra PostgreSQL17.11 efímero, arquitectura y contrato local/S3. El test nuevo comprueba probes anónimas y `/admin` protegido. No se usó la base local real para los tests.
- Imagen construida y cargada para linux/arm64 con Java y Mailpit fijados por digest; no publicada en registro externo.
- Dry-run servidor para GitOps/storage/aplicación; PV/PVC Bound; ambos pods Ready sin reinicios.
- HTTPS200 en portada, catálogo, editoriales, login, registro, CSS, JS, logo y health/probes. Admin anónimo redirige al login; cookie de sesión Secure.
- Dos lectores y cuatro páginas de imagen comprobados por HTTPS, con validación de hashes y tipos de contenido.
- PostgreSQL real TLS1.3; recuentos finales2usuarios/2series/2capítulos/4páginas.
- Mailpit ClusterIP, autenticación401sin credenciales y200con credenciales; captura SMTP interna correcta; sin relay externo configurado.
- Doce Applications de Argo CD Synced/Healthy; DNS doméstico resuelve la web a192.168.1.163.

No se hizo una nueva prueba visual de navegador ni se probó el login con la contraseña de un usuario real, que no se solicitó. Las contraseñas se conservaron y los flujos de autenticación están cubiertos por las pruebas de integración. No se simuló pérdida de nodo o recuperación integral.

## Actualizar o recuperar

Imagen desplegada:

```text
docker.io/homelab/onthemanga@sha256:4ea713e85084c177b2e01109d64ff05894183bc00ff004f1930eac0b2efa1e04
```

El código del proyecto está actualizado en su ruta original; los cambios se mantienen locales, sin commit/push en el repositorio de la aplicación. GitOps y nginx sí se publicaron en sus repositorios operativos. `source.patch` y los archivos modificados del paquete permiten revisar/reproducir el cambio sobre HEAD `cf94a89b45f87759c80403fec489677e93657d9a`.

El JAR verificado tiene SHA256 `950508843abfc56fc3d35ae8612fc6e4edba5488e8663ec600e22e39d122cb47`. Se entrega `artifacts/onthemanga-arm64.tar`, sin datos de usuarios ni Secrets, para recuperar la imagen si se pierde la caché del nodo. Copia privada local en pi5 `/var/lib/homelab-images/onthemanga-20261030.tar`. SHA256 del archivo: `ccd78d74472307b4e4064c752d78cd95eb5f53967c0e39a7201a587d4cef37a1`.

Solo pi5 tiene la imagen precargada y la aplicación usa `imagePullPolicy: Never`. Antes de reubicar o reconstruir el nodo hay que importar la imagen con containerd en namespace `k8s.io` y registrar el alias canónico `docker.io/homelab/onthemanga@sha256:...`; no basta con un tag. Los metadatos y scripts públicos de la entrega registran los pasos. Un registro privado sería una mejora posterior, no instalado.

Manifiestos de aplicación en `deploy/kubernetes` del proyecto y en `apps/onthemanga` de GitOps. Las definiciones de PV se guardan como referencia en `deploy/kubernetes/storage`; su propietario operativo sigue siendo homelab-storage. No aplicar carpetas generales ni duplicar propietarios. Secrets/CA se preparan por un canal privado; la CA copiada entre namespaces exige mantener su renovación.

Una reversión de imagen no deshace Flyway ni devuelve escrituras nuevas al Docker local. Conservar PostgreSQL, objetos NFS, SQLite Mailpit y claves de la aplicación mediante copias coordinadas. No se ha instalado backup periódico ni se ha ensayado una recuperación integral de esta aplicación.

## Incidencias resueltas y alcance

1. Metrics API no instalada: inventario de memoria desde Prometheus existente; sin instalar metrics-server.
2. Referencia de imagen con tag+digest no reconocida por CRI con Never: se añadió alias canónico sin tag y se corrigió GitOps. Pod actual sin reinicios.
3. Una escritura YAML desde Windows produjo CRLF, detectado por git diff --check: se corrigió a LF antes del commit.
4. Argo es asíncrono: la primera espera encontró Deployment todavía no creado; después se comprobó su creación y rollout completo.
5. La revisión automática rechazó ampliar la publicación a Mailpit HTTPS y modificar el helper privilegiado por falta de autorización explícita de esos extras. Un siguiente intento se bloqueó por límite temporal del servicio de revisión y no se ejecutó. Tras «Continua» se completó la alternativa de menor riesgo: Mailpit ClusterIP privado y publicación solo de la web, sin modificar el helper. Nada de lo rechazado se ejecutó.

El helper de nginx conserva sus comprobaciones HTTPS de siete servicios previos; las comprobaciones nuevas de On The Manga se hicieron por separado en esta entrega. No se afirma que haya adquirido una nueva prueba automática de salud de esta aplicación.

GitOps verificado: `96cd46b4e35674fe340e2c2929cd7ee1d5fde4a0`. nginx desplegado: `48f3cba5e6c3857a6f2d2f6abc264214111afb41`. Documentación de cierre en un commit GitOps posterior. Evidencias públicas en `evidencias/onthemanga-cluster-20261030/`; no contienen dumps, mensajes reales, cookies ni claves.
