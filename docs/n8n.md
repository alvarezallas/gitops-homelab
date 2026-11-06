# n8n y primer agente local

Instalado el 06/11/2026. Interfaz: **https://n8n.bearsfamily.es**. También está en el menú de aplicaciones del home.

Correo propietario: `thebear@bearsfamily.es`. La contraseña está únicamente en el PC, fuera de OneDrive y Git:

`C:\Users\aalva\Documents\Codex\ia-workspace-runtime\n8n\secrets\acceso.txt`

## Cómo usarlo

1. Entra por HTTPS e inicia sesión con esa cuenta.
2. Abre el flujo **Homelab - informe diario (lectura)**. Está publicado, con horario **08:00 Europe/Madrid**, que adapta el cambio de hora.
3. Para probarlo, pulsa **Execute workflow**. Selecciona la entrada «Prueba manual» si lo solicita.
4. En **Executions**, abre la ejecución y el nodo **Agente de salud**: `output` contiene el informe; `intermediateSteps` muestra la consulta que hizo la herramienta.
5. El nodo **Guardar informe** conserva un único informe por día en `automation_state.public.agent_reports`. Las pruebas repetidas se ven en Executions, pero no reemplazan el informe diario existente.

La hora del informe no garantiza que el PC esté disponible. El gateway arranca al iniciar sesión en Windows: si el PC está apagado, suspendido, sin sesión tras reiniciar o el túnel no está disponible, la ejecución puede fallar. Revisa **Executions** y reintenta manualmente cuando se recupere; no se ha configurado un envío de notificaciones ni una cola de reintentos automáticos. La GPU se comparte con Speakr/ComfyUI mediante el bloqueo del gateway; puede haber espera o rechazo por ocupación.

## Qué está instalado

| Componente | Configuración |
|---|---|
| n8n | Community 2.46.6, imagen ARM64 fijada por digest, una réplica en pi5 |
| Argo CD | Application `homelab-n8n`, sincronización manual, sin Prune/Force/Replace |
| Publicación | nginx del host → `127.0.0.1:30096`; HTTPS válido del wildcard existente |
| Datos de n8n | DB `n8n`, usuario `n8n_app`; PVC local propio de 2 GiB, Retain |
| Informes | DB independiente `automation_state`, usuario `automation_state_app` |
| TLS PostgreSQL | CA del clúster, validación de certificado activada |
| IA | Qwen3.5:4b en el PC, sin API de pago; credencial distinta de Speakr |
| Herramienta inicial | GET de Prometheus con URL y consulta fijas; no acepta órdenes o URLs del modelo |
| Copia | Diaria 04:15–04:18 Europe/Madrid, AES-256-GCM a `192.168.1.164:/mnt/d01tb/n8n-backups` |

La clave de cifrado de credenciales de n8n y la de copias son distintas. Están en el fichero privado `config.json` del PC y de pi5; las copias incluyen su configuración de recuperación y el Secret de n8n, cifrados. Conserva una copia privada del `config.json` del PC: perder todas las copias de la clave del backup impide recuperar los archivos cifrados.

Los manifiestos y herramientas están en el repositorio GitOps (`apps/n8n`, `automation/n8n`, `platform/storage/13-n8n-data-pv.yaml`, `clusters/home/n8n.yaml`). Las exportaciones de flujos se guardan saneadas, sin valores de credenciales. La configuración real y las claves se mantienen fuera del repositorio.

## Alcance del agente

Consulta nodos inventariados, CPU ocupada, RAM disponible, pods activos no listos y targets de Prometheus caídos. Redacta un informe en español y guarda sus pruebas. No representa una auditoría exhaustiva de hardware, discos del NAS o cada aplicación. Las inferencias del modelo deben contrastarse con los datos de la herramienta.

El contenedor no tiene kubeconfig, token de ServiceAccount, socket Docker, SSH general ni acceso al disco completo del NAS. Los nodos Code/Execute Command/archivos locales y los paquetes comunitarios están deshabilitados. No se han desplegado ejecutores externos porque el flujo inicial no los necesita. Flannel no proporciona aislamiento mediante NetworkPolicy: no importar flujos o nodos de origen desconocido.

Se conservan ejecuciones durante 7 días y un máximo de 1000, con límite de concurrencia de producción de 1. Ese límite no cubre todas las ejecuciones manuales/subflujos. No hay suscripción adicional ni facturación de API habilitada.

## Verificaciones realizadas

- HTTPS y login desde navegador; sesión válida después de recrear el pod.
- Gateway autenticado y herramienta real del modelo; credencial de n8n sin acceso al endpoint de transcripción.
- Informe generado dentro de n8n y guardado con TLS en PostgreSQL.
- Repetición del mismo día: una sola fila de informe.
- Dos ejecuciones automáticas de un flujo de prueba; después despublicado y archivado.
- Backup autenticado, copia cifrada al NAS y restauración de ambas DB en bases temporales.
- Dos credenciales recuperadas y descifradas con la misma versión de n8n en un pod aislado, sin servidor, horarios ni Service.
- PVC archivado, clave de n8n comprobada contra el Secret y arranque/login tras recreación.
- Portal con 27 componentes, enlace de n8n y comprobación de layout móvil.

La recuperación de DB/credenciales se ha probado en aislamiento. No se ha reconstruido todo el clúster desde cero ni se ha ensayado una pérdida real de pi5. Tampoco se ha realizado una nueva prueba de acceso VPN desde Internet o una observación de 24–48 horas.

En la revisión apareció una réplica de CoreDNS no lista en pi3b1 (`Unknown`), mientras la otra estaba `1/1` en pi3b2. El agente señaló correctamente un pod activo no listo; no se ha reiniciado ni reconfigurado CoreDNS como parte de esta instalación.

## Operación y copias

En pi5:

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n n8n get pods,svc,pvc
sudo systemctl list-timers homelab-n8n-backup.timer
sudo systemctl status homelab-n8n-backup.service --no-pager
sudo journalctl -u homelab-n8n-backup.service -n 30 --no-pager
sudo backup-n8n
```

El backup espera a que terminen las ejecuciones activas y falla sin detener n8n si siguen activas tras cinco minutos. Después detiene solo n8n para coordinar DB y archivos, y lo levanta en un bloque de recuperación incluso si la copia falla. Habrá una interrupción breve del panel. El horario elegido no coincide con el informe diario ni con la copia de AdGuard. Evita crear otros horarios a esa hora.

Retención: siete copias diarias y cuatro semanales en el NAS; hasta once copias cifradas locales. Las copias contienen más historia que la retención de Executions y se protegen como datos privados.

Para inspeccionar una copia local, sin restaurar producción:

```bash
sudo restore-n8n /var/lib/homelab-apps/n8n/private/backups/n8n-FECHA.n8b
# Ensayo de DB y credenciales en bases y pod temporales:
sudo restore-n8n /var/lib/homelab-apps/n8n/private/backups/n8n-FECHA.n8b --verify-databases
```

Para extraerla a un directorio privado NUEVO:

```bash
sudo restore-n8n /ruta/backup.n8b --extract-to /var/lib/homelab-apps/n8n/private/recovery-FECHA
```

No vuelca secretos por pantalla. El modo de extracción nunca sustituye la DB/PVC de producción. Si la copia solo está en el NAS, cópiala primero de su carpeta NFS a una ubicación privada en pi5. Antes de extraer debe existir el `private/config.json` con la clave del backup, recuperado del fichero privado del PC si pi5 se perdió.

## Reconstrucción tras una pérdida

1. Recupera PostgreSQL y GitOps según sus guías. Mantén desactivado el timer de copias hasta terminar y conserva el backup elegido intacto.
2. Recupera la configuración privada de n8n del PC en `/var/lib/homelab-apps/n8n/private/config.json`, con root:root, carpeta 700 y fichero 600. Instala los helpers desde GitOps; inspecciona y extrae el backup a un directorio `recovery-*` nuevo.
3. Detén solo el Deployment de n8n. En un clúster nuevo, crea únicamente los roles que falten con el SQL privado generado `private/roles-new-cluster.sql`; no ejecutes ese SQL si ya existen. Crea las DB `n8n` y `automation_state` con sus propietarios correspondientes y restaura los `.dump` con `pg_restore --no-owner --no-acl --role=PROPIETARIO --exit-on-error`. Si ya tienen datos, restaura primero a DB nuevas; no sobreescribas la única copia existente.
4. Recupera el directorio `data` al volumen local propio de n8n, con UID/GID 1000. Aplica el Secret saneado `private/k8s-secret.json`; recrea la ConfigMap `postgresql-ca` desde la CA pública vigente de CloudNativePG. Los manifiestos GitOps no contienen esos valores secretos.
5. Para el primer arranque de recuperación, despublica horarios en una instancia aislada o usa `n8n unpublish:workflow --all` contra la DB recuperada antes de poner en marcha el servidor. No arranques dos instancias con horarios activos sobre copias de los mismos flujos.
6. Usa la misma imagen 2.46.6/digest; comprueba login, descifrado de credenciales, permisos y flujo de lectura en aislamiento. Publica nginx y restaura el horario después. Si se perdió el PC, restablece también el gateway, su token de n8n y el túnel privado; Ollama permanece en localhost.
7. Verifica una nueva copia y reactiva el timer. Para revertir una actualización con migraciones, recupera también DB/PVC/clave compatibles: volver solo a una imagen antigua puede no ser suficiente.

Los scripts no ejecutan automáticamente esta sustitución de producción: la restauración aislada es la opción predeterminada. No requiere desactivar TLS ni dar permisos de administrador de Kubernetes al modelo.

## Siguientes agentes

Speakr y revisión de repositorios son siguientes fases del plan, todavía sin conexión ni horarios activos. Primero hay que definir sus accesos mínimos y qué contenido pueden leer. No se ha habilitado envío de correo, publicación de código, cambios de infraestructura ni ejecución general de comandos por el agente.

Fuentes: [n8n Community](https://docs.n8n.io/hosting/community-edition-features/), [despliegue Docker](https://docs.n8n.io/hosting/installation/docker/), [CLI](https://docs.n8n.io/hosting/cli-commands/), [Schedule Trigger](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.scheduletrigger/). La versión/digest y los esquemas de nodos se contrastaron con la imagen ARM64 y el código oficial 2.46.6.
