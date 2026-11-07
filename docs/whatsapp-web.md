# WhatsApp Web en Kubernetes: sandbox resuelto

07/11/2026. **Servicio listo para vincular, sin sesión conectada ni primer envío desde el clúster todavía.**

Panel: **https://whatsapp.bearsfamily.es**. Usuario: `bearsfamily`. Contraseña en el PC, fuera de Git y OneDrive:

`C:\Users\aalva\Documents\Codex\ia-workspace-runtime\whatsapp-web\private\acceso.txt`

Abre el panel desde la LAN o la VPN y, en el móvil, entra en **WhatsApp → Dispositivos vinculados → Vincular un dispositivo**. Escanea el QR de ese panel. No hace falta vincular la aplicación de Windows ni compartir el QR por el chat.

Hay un único mensaje sintético pendiente, sin correos reales, preparado para comprobar la entrega al chat propio al vincular la sesión. Los buzones de Hotmail, Live y Gmail siguen sin conectar: no se está clasificando, borrando o leyendo correo.

## Qué fallaba y cómo se corrigió

1. El perfil seccomp efectivo de containerd no permitía `unshare` ni `setns`; `clone` estaba limitado para namespaces. La prueba devolvió EPERM. No era suficiente atribuirlo a AppArmor por la configuración de Ubuntu.
2. Con las tres llamadas habilitadas en un perfil exclusivo, Chromium avanzó y falló al ejecutar `chroot` para su propio aislamiento. Se añadió esa cuarta llamada, sin añadir capacidades al pod.
3. Chromium pudo arrancar con sandbox activo, pero WhatsApp rechazó la variante headless como navegador no compatible. Chromium completo, con una pantalla virtual Xvfb, sí cargó el QR usando su identificación normal, sin modificar el user-agent.
4. Para el servicio persistente, Node gestiona Xvfb como proceso hijo y guarda HOME/configuración/caché en el volumen privado. La raíz del contenedor sigue siendo de solo lectura.

El perfil `/var/lib/kubelet/seccomp/whatsapp-playwright.json` parte del perfil real de pi5 y añade solo la autorización de `clone`, `unshare`, `setns` y `chroot`. Se aplica mediante `seccompProfile: Localhost` exclusivamente al contenedor del navegador. No es el perfil predeterminado del host. El initContainer de dependencias conserva RuntimeDefault.

AppArmor sigue como `cri-containerd.apparmor.d (enforce)` y `kernel.apparmor_restrict_unprivileged_userns=1` sigue vigente. El proceso renderer comprobado tiene UID1000, CapEff0, NoNewPrivs1, Seccomp2 y dos filtros seccomp; no contiene `--no-sandbox`. No se ha usado modo privilegiado ni SYS_ADMIN en el pod. Chromium gestiona capacidades internas de sus propios namespaces para construir su sandbox; no son capacidades añadidas al contenedor sobre el host.

## Configuración vigente

| Elemento | Estado |
|---|---|
| Application | `homelab-whatsapp-web`, sincronización manual |
| Namespace / nodo | `whatsapp` / `pi5` |
| Navegador | Playwright1.65.0, imagen ARM64 fijada por digest; Chromium completo + Xvfb |
| URL / backend | HTTPS doméstico → nginx → `127.0.0.1:30097` |
| Sesión | PVC local propio2Gi, Retain; sin hostPath en el pod |
| Recursos | Request250m/256Mi; límite1CPU/1Gi; `/dev/shm` propio256Mi |
| Permisos | Usuario1000, sin token SA, sin privilegios, raíz de solo lectura |
| Cola | PostgreSQL `automation_state.whatsapp_delivery.outbox`, rol propio |
| Integración | Flujo n8n `WhatsApp Web - cola privada`, webhooks con credencial de cabecera |
| Worker de Windows | Tarea `Bears WhatsApp Web` desactivada y detenida; fallback no operativo |
| Codex programado | No se creó ninguna tarea; no se necesita para entregar mensajes |

El perfil seccomp solo está instalado y revisado para pi5 ARM64. El selector de nodo evita ejecutar el navegador en los workers sin preparar. Al reconstruir pi5, ejecutar primero con sudo `automation/whatsapp-web/install-seccomp.py` desde GitOps. Después sincronizar almacenamiento y aplicación. Ese script verifica hostname, arquitectura y SHA256 del perfil antes de instalarlo; no modifica AppArmor ni perfiles globales. Revisar el perfil al actualizar containerd o Playwright.

## Entrega y límites

El worker consulta cada minuto la cola, comprueba que el chat sea el propio y añade un marcador por ID. Un ID repetido no crea una entrega nueva y un cambio de cuerpo con el mismo ID no modifica el original. Confirmar «sent» exige ver el mensaje y un icono de envío, no solo que aparezca una burbuja. Ante resultado incierto no se reenvía a ciegas: la cola se detiene para reconciliarlo.

La sesión del navegador permanece en el volumen privado, fuera de Git y OneDrive. Solo se sirve la imagen del QR en un panel protegido y sin caché. El sistema no expone un navegador remoto, DevTools o noVNC en la red. No se abrieron puertos del router.

Esto no convierte WhatsApp Web en una API oficial ni garantiza que sus selectores o condiciones de uso permanezcan estables. La vinculación puede caducar y necesitar un nuevo QR. La prueba real con cuenta vinculada sigue pendiente; no afirmar que el envío automático ya se ha ensayado en pi5.

Los webhooks son para mensajes al chat propio. No proporcionan destinatario libre, enlaces que el modelo pueda abrir, acceso al correo ni envío de respuestas por email. La inferencia de correo prevista sigue en el PC con Qwen; únicamente el navegador de entrega se ha trasladado al clúster.

## Copias y recuperación

La cola y las credenciales están incluidas en las copias cifradas existentes de n8n, porque usan `automation_state` y las credenciales de n8n. Se creó y verificó una copia al NAS tras añadirlas: restauración aislada de las dos DB y descifrado de cuatro credenciales, sin publicar la instancia de prueba.

**El perfil de Chromium aún no tiene una copia automática específica.** El PVC Retain protege frente a recrear el pod, no frente a perder pi5 o su disco. Si se pierde la sesión, habrá que vincularla de nuevo. Antes de restaurar una cola antigua o recrear una sesión, detener el worker y reconciliar IDs/estados con el chat; no convertir indiscriminadamente entregas inciertas o ya enviadas en pendientes.

No se ha ensayado una restauración de una sesión vinculada, un reinicio físico de pi5 ni acceso real desde fuera por VPN. Tampoco se ha conectado el correo ni activado su resumen diario.

## Comprobaciones

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n whatsapp get pods,svc,pvc
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n argocd get application homelab-whatsapp-web
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n whatsapp logs deployment/whatsapp-web -c worker --tail=30
```

Parada reversible del worker:

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n whatsapp scale deployment/whatsapp-web --replicas=0
```

La sincronización de Argo es manual. Para una parada permanente, cambiar las réplicas en Git y no reactivar el worker de Windows a la vez. El contenedor no obtiene acceso SSH ni kubeconfig de administrador.

Fuentes: [Playwright en Docker y seccomp](https://playwright.dev/docs/docker), [restricciones userns de Chromium/Ubuntu](https://chromium.googlesource.com/chromium/src/+/main/docs/security/apparmor-userns-restrictions.md). Las conclusiones concretas de este documento proceden de las pruebas reales guardadas en `verificacion.json`.
