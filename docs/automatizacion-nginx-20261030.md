# Automatización nginx activada — 30/10/2026

Autorización: el usuario confirmó «autorizo todo entonces», después de revisar las operaciones persistentes y el cambio a releases atómicas. La revisión automática anterior dejó de bloquear tras esa autorización. Instalación completada.

## Uso cotidiano

1. Modifica los archivos del repositorio `nginx-sites-available`, haz commit y push a `main`.
2. En [Semaphore](https://semaphore.bearsfamily.aa), proyecto **Homelab**, consulta **nginx - sincronizar main**. Horario **nginx main cada minuto** activo (`* * * * *`, Europe/Madrid).
3. La tarea despliega el SHA validado y comprueba HTTPS. Sin cambios, no recarga. HTML/imágenes tampoco recargan; los cambios `.conf` recargan después de `nginx -t`.

No editar los archivos bajo `/etc/nginx/sites-available` directamente: ahora son una release propiedad de root. El clon editable sigue en `/home/alvarense/nginx-sites-available`. Si tiene cambios locales sin commit, se detiene el despliegue para conservarlos.

## Estado instalado

- Host: pi5, 192.168.1.163. Scheduler y cliente SSH: contenedor Semaphore en Kubernetes; PostgreSQL existente.
- Proyecto 1, plantilla 3, horario 3; una tarea concurrente. Retención 100 registros por plantilla.
- Key dedicada `semaphore/semaphore-nginx-ssh`; usuario remoto `semaphore-nginx`, comando forzado `deploy-nginx`, sin consola ni sudo genérico. Clave personal sin copiar al pod.
- Helpers root `/usr/local/sbin/homelab-nginx-deploy` y `/usr/local/libexec/homelab-nginx-ssh`. Origen limitado a pods/pi5, host key verificada. Regla sudo de comando y argumentos fijos. SSH validado y recargado.
- `/etc/nginx/sites-available` → `/var/lib/homelab-nginx/current`.
- `/etc/nginx/sites-enabled` → `/var/lib/homelab-nginx/current/sites-enabled`.
- `current` → `/var/lib/homelab-nginx/releases/a05411815f74fe898f0bfdbd3d326b8a73d83b57`.
- Global nginx.conf y certificados privados conservados. El portal usa el mismo puntero que la configuración. Anterior sites-enabled conservado en `/etc/nginx/sites-enabled.before-semaphore-20261030`.
- Recuperación de transacción interrumpida mediante journal y servicio habilitado anterior a nginx; auditoría JSONL `/var/log/homelab-nginx-deploy.jsonl`, logrotate semanal/12 archivos. Releases sin purga automática.
- Secret montado de solo lectura. Semaphore conserva ausencia de token SA, kubeconfig, RBAC, hostPath y socket del host.

## Pruebas

| Prueba | Resultado |
|---|---|
| Ocho pruebas de comportamiento en Linux | Correctas |
| Configuración completa candidata válida/inválida con nginx -t | Aceptada/rechazada correctamente |
| Clave dedicada y operación forzada | Tarea 8 correcta; comando SSH id denegado |
| Candidata inválida, sin publicar en GitHub | No promovida, configuración activa válida |
| Candidata con upstream Grafana caído, sin publicar en GitHub | Fallo HTTPS y reversión real automática; siete accesos restaurados |
| Commit válido con cambio .conf | Tarea 9 correcta, recarga |
| Reversión manual a release previa y redespliegue main | Correctos; tarea 10 |
| Mismo SHA | Tarea 11 sin recarga, workers conservados |
| Push con horario activo | Tarea 12 detectó y publicó en 32.71 s; cambio HTML sin recarga |
| Comprobación final | 11 Applications Synced/Healthy; cuatro nodos Ready; pod Semaphore sin reinicios; 11 targets Prometheus UP; siete HTTPS correctos |

La prueba negativa de upstream interrumpió brevemente el acceso Grafana durante el ensayo y lo restauró automáticamente. No se dejaron configuraciones inválidas activas ni se subieron a main. El aspecto del portal, su logo y favicon se conservan; la prueba de HTML añadió solo un comentario invisible. No se realizó una nueva comprobación visual en navegador.

No se probó un corte eléctrico, reinicio físico ni caída real de GitHub. Se verificó la lógica de recuperación de arranque con pruebas automatizadas, no mediante apagar pi5.

## Pausar y revertir

En pi5:

```bash
cd ~/gitops-homelab
sudo python3 automation/semaphore/nginx/configure-nginx-task.py status
sudo python3 automation/semaphore/nginx/configure-nginx-task.py disable
```

Para una reversión persistente, usa `git revert` del commit en `main` y publica el resultado. Para volver de inmediato a una release ya validada, con el horario pausado:

```bash
sudo /usr/local/sbin/homelab-nginx-deploy --rollback-to SHA_DE_LA_RELEASE
```

Después de resolver el problema y publicar main:

```bash
sudo python3 ~/gitops-homelab/automation/semaphore/nginx/configure-nginx-task.py enable
```

Un SHA rechazado no se vuelve a desplegar en bucle. Publica un commit corrector o, tras resolver una causa externa, root puede usar `sudo /usr/local/sbin/homelab-nginx-deploy --retry`.

## Límites y pendientes

- Controlar `main` equivale a proponer configuración procesada con privilegios por nginx. Protección/revisión de rama GitHub pendiente, no configurada por este despliegue. La identidad de lectura GitHub sigue siendo la existente del usuario alvarense en pi5; una deploy key GitHub específica sería un endurecimiento adicional.
- Las copias cifradas de la instalación base incluían dos Secrets, no la nueva identidad SSH. Actualizar su política de recuperación privada y copias periódicas queda pendiente; no se activaron backups ni se exportó material privado a Git/OneDrive.
- Solo se automatizó nginx. La sincronización general de Argo CD sigue manual. No se instalaron webhooks públicos, cambios de router, adblock o automatización de otros hosts.
- La disponibilidad de los backends forma parte de las comprobaciones; si uno ya está caído, puede bloquear un despliegue hasta corregirlo. Las releases consumen espacio y no se purgan automáticamente.

## Revisiones y evidencias

- Commit inicial de migración nginx: `0b50a475481f5c74470a0eb73910e59a3357354e`.
- Commit de prueba/configuración y documentación nginx: `7725e3d3d510eeed634ae9be875d591917e0a49b`.
- Commit nginx actualmente publicado: `a05411815f74fe898f0bfdbd3d326b8a73d83b57`.
- Commit GitOps de implementación: `c64ca37e2e972af4a61194a32aa9e4bbf35054a7`. Documentación de cierre en commit posterior.
- Paquete público: `automatizacion-nginx-20261030/README.md`. Evidencias: `evidencias/automatizacion-nginx-20261030/`.

Los espejos D/OneDrive se actualizan con archivos públicos; sus historiales Git no se fuerzan ni se resetean.
