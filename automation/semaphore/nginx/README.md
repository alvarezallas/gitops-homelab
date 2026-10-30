# Automatización de nginx desde Semaphore

Fecha: 30/10/2026 · Europe/Madrid.

**Estado: instalado, activado y verificado el 30/10/2026**, tras la autorización explícita del usuario «autorizo todo entonces». Proyecto Homelab (1), plantilla nginx - sincronizar main (3), horario nginx main cada minuto (3), activo. El sondeo real detectó un push y lo publicó sin recarga en 32,71 segundos. Once Applications Synced/Healthy, cuatro nodos Ready y siete accesos HTTPS correctos al cierre.

## Resultado previsto

En Semaphore → proyecto **Homelab** → plantilla **nginx - sincronizar main** y horario **nginx main cada minuto** (`* * * * *`, Europe/Madrid). No requiere webhook público, conexión entrante desde GitHub ni abrir el router.

Cada ejecución comprueba `main` de `git@github.com:alvarezallas/nginx-sites-available.git`. Si no cambia el SHA, no publica ni recarga. Si cambia, prepara una release de configuración y contenido, ejecuta la validación completa de nginx y cambia un enlace de forma atómica. Los cambios HTML/imágenes se publican sin recargar. Los `.conf` requieren `systemctl reload nginx`, no un reinicio. Después comprueba HTTPS, el contenido exacto del welcome y el logo. Ante un fallo después de publicar, restaura los archivos anteriores, los valida y recarga nginx.

## Cambios autorizados e instalados

1. Crear el usuario de sistema `semaphore-nginx` en pi5, sin contraseña de acceso, y una identidad ED25519 dedicada. La clave privada se guarda únicamente en el Secret Kubernetes `semaphore/semaphore-nginx-ssh` y se monta de solo lectura en el contenedor. No se copia la clave personal `servidor` a Semaphore ni se guarda la nueva clave en Git/OneDrive.
2. Autorizar esa clave con `restrict`, origen limitado a la red de pods y pi5, y comando forzado. Sin consola, PTY, agente o reenvío de puertos. Public key en un archivo propiedad de root `/etc/ssh/authorized_keys/semaphore-nginx`, legible por sshd. Cambios Match User en un archivo específico; `sshd -t` antes de recargar SSH.
3. Regla sudo exacta para un único comando con argumentos fijos: `/usr/bin/timeout --signal=TERM --kill-after=10s 170s /usr/local/sbin/homelab-nginx-deploy`. Sin sudo general, sin parámetros elegibles por la tarea. Helper y wrapper propiedad de root. La entrada SSH solo admite la cadena `deploy-nginx`.
4. Crear `/var/lib/homelab-nginx/releases/<SHA>` y `/var/lib/homelab-nginx/current`. Cambiar `/etc/nginx/sites-available` y `/etc/nginx/sites-enabled` para que usen la release actual. El clon `/home/alvarense/nginx-sites-available` se conserva como fuente editable; ya no publica cambios sin commit/push/validación. `default.conf` usará `root /var/lib/homelab-nginx/current;`. Configuración y portal comparten el puntero. Se guarda el antiguo `sites-enabled` antes de migrar.
5. Instalar el servicio de arranque `homelab-nginx-recover.service`, anterior a nginx, para recuperar transacciones interrumpidas; y logrotate para la auditoría. Esto no programa despliegues en systemd: el sondeo pertenece a Semaphore.
6. Publicar los manifiestos públicos en GitOps y sincronizar manualmente `homelab-semaphore`. Habrá una recreación breve de su pod para montar el Secret. No se añaden token de ServiceAccount, RBAC, kubeconfig, hostPath ni socket del runtime al contenedor.
7. Tras pasar pruebas reales, habilitar el horario cada minuto. La activación inicial se hará con el horario deshabilitado.

**Capacidad concedida:** quien controle `main` puede proponer configuración que nginx procesa como root. El comando forzado evita una consola genérica, pero no convierte esa configuración en contenido sin privilegios. Mantener acceso a `main` solo para administradores y activar revisión/protección de rama en GitHub. Este paquete no configura por sí mismo una regla de protección de GitHub.

Para leer GitHub, el helper ejecuta Git como `alvarense` con el acceso SSH ya configurado en pi5; no lo ejecuta como root ni entrega esa identidad al pod. La identidad dedicada de este paquete corresponde al salto Semaphore → pi5. Una deploy key GitHub separada de solo lectura sería un endurecimiento adicional y no se da por instalada.

## Archivos

- `host/bootstrap-host.py`: bootstrap ejecutable en pi5 como root. Bootstrap de primera migración: no reejecutar sobre un host ya migrado. Crea y aplica el Secret por stdin; nunca imprime la clave. Migra primero los enlaces con candidata validada. Si detecta una migración existente, se detiene para revisión; no es un script para repetir a ciegas después de una instalación parcial.
- `host/homelab-nginx-deploy.py`: publicador, bloqueo, validación, promoción, auditoría y reversión.
- `host/homelab-nginx-ssh`: entrada SSH con operación forzada.
- `host/homelab-nginx-recover.service`: recuperación de una transacción incompleta en el arranque.
- `gitops/platform/semaphore/`: manifiestos públicos candidatos completos de Semaphore, incluyendo únicamente la referencia al nuevo Secret.
- `gitops/automation/semaphore/tasks/nginx-sync.sh`: cliente SSH fijo; huella de pi5 verificada en el ConfigMap de tareas.
- `gitops/automation/semaphore/nginx/configure-nginx-task.py`: configuración de plantilla/horario y operaciones administrativas por API desde pi5. Lee la contraseña localmente sin mostrarla. Acciones `configure`, `run`, `enable`, `disable`, `status`.
- `validation.json`: evidencias de pruebas realizadas.
- `SHA256SUMS.json`: integridad de los archivos del paquete.

## Procedimiento de referencia de activación — ya ejecutado

1. Revalidar acceso a pi5, huella, nginx sano, GitOps y clon nginx limpios y actualizados. No sobrescribir cambios locales. Confirmar que no se ha instalado otra automatización entretanto.
2. Copiar este paquete a pi5 y ejecutar `sudo python3 host/bootstrap-host.py`. Registrar el commit de migración y revisar HTTPS de las siete entradas. La primera migración cambia la raíz estática y recarga nginx.
3. Integrar **solo** los archivos de `gitops/` sobre el repositorio GitOps real actualizado. Revisar el diff, `kubectl kustomize platform/semaphore` y `kubectl apply --server-side --dry-run=server -k platform/semaphore`; commit y push. La carpeta no contiene Secrets reales. Sincronizar manualmente `homelab-semaphore` en Argo CD y esperar a Ready.
4. En pi5, dentro de `~/gitops-homelab`, ejecutar:

   ```bash
   sudo python3 automation/semaphore/nginx/configure-nginx-task.py configure
   sudo python3 automation/semaphore/nginx/configure-nginx-task.py run
   ```

   El horario se crea **deshabilitado**. La primera tarea debe confirmar el SHA actual y `no-change`.
5. Probar el comando no permitido: la misma identidad no debe ejecutar `id`, shell o un comando sudo arbitrario. Confirmar la huella y el origen real desde el pod. No registrar la clave en evidencias.
6. Completar pruebas reales de un push inocuo de HTML, actualización `.conf` válida, repetición sin cambios y reversión. La candidata inválida y el fallo HTTPS ya se probaron con objetos Git locales sintéticos sin publicarlos en main; el fallo HTTPS revirtió realmente los archivos y la configuración activa. No publicar una configuración inválida en `main` para probar.
7. Solo con las pruebas correctas:

   ```bash
   sudo python3 automation/semaphore/nginx/configure-nginx-task.py enable
   sudo python3 automation/semaphore/nginx/configure-nginx-task.py status
   ```

   Probar un push real con el horario activo, comprobar la tarea programada y medir la latencia. Lo esperable es hasta un minuto más cola y duración de tarea; no se promete ejecución instantánea.
8. Actualizar plan, diario y espejos públicos D/OneDrive con el commit final, los IDs de plantilla/horario y los resultados. No marcar la fase 6–7 completada hasta terminar esta secuencia.

## Operación y fallos

- Auditoría persistente: `/var/log/homelab-nginx-deploy.jsonl`, rotación semanal con 12 archivos. Eventos `detected`, `applied`, `rejected-before-promotion`, `recovered`, `no-change`, `error`. Guarda SHA y resultados, sin claves o cookies. Historial de Semaphore limitado a 100 tareas por plantilla.
- Una sola tarea concurrente del proyecto y del template; bloqueo adicional en pi5. Tiempo SSH remoto 170 s y límite de tarea general 300 s. Si GitHub falla, se conserva la release activa; el siguiente minuto vuelve a consultar. No hay bucle de reinicios del servicio.
- Se verifica remoto, rama, árbol limpio y avance fast-forward. El helper no usa `reset --hard`. Archivos locales sin commit detienen el sondeo hasta resolverlos.
- Se rechazan archivos inesperados, symlinks, submódulos y archivos excesivos en la candidata. Deben seguir presentes las ocho configuraciones existentes. Añadir un `.conf` válido lo habilita en la release; retirar un servicio existente exige revisar expresamente la política `REQUIRED`.
- Una revisión rechazada no se reintenta automáticamente; publicar un commit corrector. Después de resolver una causa externa, root puede ejecutar `sudo /usr/local/sbin/homelab-nginx-deploy --retry`.
- Las releases no se purgan automáticamente. Revisar espacio y conservar las últimas revisiones necesarias; este paquete no hace borrados periódicos.
- Pausar antes de una reversión manual:

   ```bash
   sudo python3 ~/gitops-homelab/automation/semaphore/nginx/configure-nginx-task.py disable
   sudo /usr/local/sbin/homelab-nginx-deploy --rollback-to SHA_DE_UNA_RELEASE_VALIDADA
   ```

   El SHA debe existir en `releases`. Para conservar una reversión, hacer `git revert` del cambio en `main`; al reactivar el sondeo, se aplica de nuevo `main` si difiere. No manipular manualmente el enlace `current` con el horario activo.
- Las comprobaciones HTTPS dependen de la salud de las aplicaciones existentes. Un backend ajeno ya caído puede impedir un despliegue nuevo; corregir ese fallo y usar `--retry` o un nuevo commit.
- El certificado doméstico y su clave quedan donde están en pi5; no se incluyen en el repositorio ni en las releases.

## Pruebas realizadas y límites

Pasaron ocho pruebas automatizadas de comportamiento en Linux: mismo SHA sin recarga, candidata inválida sin promoción, cambio estático sin recarga, cambio de configuración con recarga, fallo HTTPS con restauración del puntero y recarga anterior, recuperación al arrancar, bloqueo de reintentos de revisión rechazada y reintento explícito de root.

Además, en pi5 se construyó una candidata en un directorio temporal de `/run`, con la futura raíz del portal. La configuración completa pasó `nginx -t`; añadir una directiva inválida hizo fallar la validación. Se comprobó sintaxis de ambos scripts de shell. Los directorios temporales se eliminaron.

**Verificación real completada:** la clave dedicada ejecutó la tarea 8 correctamente y denegó el comando SSH `id`. Una candidata inválida fue rechazada sin promoción. Una candidata sintácticamente válida con upstream Grafana inalcanzable se promovió brevemente, falló HTTPS y revirtió automáticamente a la release previa, que pasó nginx -t y todos los accesos HTTPS. Esos objetos Git sintéticos solo existen localmente; no se publicaron en main.

El commit válido `7725e3d3d510eeed634ae9be875d591917e0a49b` fue aplicado desde Semaphore en la tarea 9 con recarga. Se revirtió manualmente a `0b50a475481f5c74470a0eb73910e59a3357354e`, se verificó HTTPS y la tarea 10 volvió a desplegar main. La tarea 11 repitió SHA sin recarga y sin sustituir los procesos worker. Tras habilitar el horario, el push `a05411815f74fe898f0bfdbd3d326b8a73d83b57` se detectó en la tarea programada 12 y publicó un comentario HTML invisible, sin recarga; latencia observada 32,71 s. El aspecto de la portada se conserva.

No se simuló un corte eléctrico ni se reinició pi5: la recuperación de arranque tiene prueba de comportamiento automatizada y servicio habilitado, pero no una prueba de reinicio físico. No se ha probado una caída real de GitHub; las operaciones Git fallan antes de promover una candidata.

## Copias

La instalación anterior guardó la base y sus dos Secrets iniciales en copias cifradas puntuales. La nueva identidad SSH es un **tercer Secret**, no incluido en aquellas copias. Incorporarlo a una copia privada cifrada cuando se autorice esa política; no exportarlo a OneDrive. Si se pierde, se puede generar una identidad nueva y sustituir expresamente la autorización pública de pi5. Las copias periódicas siguen fuera del alcance de esta activación.

## Referencias oficiales consultadas

- [nginx: prueba de configuración y recarga](https://nginx.org/en/docs/switches.html).
- [Semaphore: horarios y zona horaria](https://semaphoreui.com/docs/user-guide/schedules).

Se contrastó además la API con el código de la versión instalada `v2.19.17`, ya obtenido durante la instalación base.
