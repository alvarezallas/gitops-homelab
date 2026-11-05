# Speakr instalado — 05/11/2026

## Acceso desde el móvil o cualquier equipo de casa

Abre **https://notas.bearsfamily.es** desde la LAN o con tu WireGuard conectado.

- Correo de acceso: **thebear@bearsfamily.es**. El formulario pide correo, no el nombre de usuario.
- Nombre de la cuenta: `bearsfamily`.
- Contraseña: archivo privado del PC `C:\Users\aalva\Documents\Codex\ia-workspace-runtime\speakr-pc\secrets\acceso.txt`. No se copia a OneDrive ni Git.
- También hay un enlace **Speakr** en el menú de aplicaciones de la página de inicio.

Pulsa **Nueva grabación** y elige grabar con el micrófono o subir un archivo. Autoriza el micrófono cuando el navegador lo pida. Para reuniones largas usa inicialmente la grabadora nativa del móvil y sube después el audio: no se ha probado todavía la continuidad con pantalla bloqueada en tu teléfono real. Conserva el original hasta comprobar la carga.

La biblioteca contiene una **Prueba sintética de instalación** de unos 13 segundos. Puedes abrirla para ver la transcripción, el resumen y el chat. Pregunta «¿Quién preparará el informe?». Es un audio generado con una voz del PC; no se ha grabado tu micrófono.

## Instalación real

| Componente | Configuración |
| --- | --- |
| Web | Speakr `0.10.19-alpha-lite`, ARM64, namespace `speakr`, una réplica en pi5 |
| Imagen | `learnedmachine/speakr:0.10.19-alpha-lite@sha256:80bc63c5f704047ec5a9406ff3ad1915b0bd22aeb6c6e60801ddec53e87099be` |
| GitOps | Application `homelab-speakr`, `apps/speakr`, sincronización manual |
| PostgreSQL | DB `speakr`, rol propio `speakr_app`, TLS `verify-full`, CA montada |
| Archivos | NAS `.164:/mnt/d01tb/speakr`, PV `speakr-data-pv`, PVC propio de 30 GiB nominales |
| nginx | HTTPS existente, upstream `127.0.0.1:30095`; publicación atómica por Semaphore |
| DNS | Registro privado exacto `notas.bearsfamily.es → 192.168.1.163` |
| Transcripción | faster-whisper `medium` multilingüe, RTX 2070, `int8_float16` |
| Resúmenes y chat | Ollama `qwen3.5:4b`, local |
| Búsqueda semántica | Ollama `embeddinggemma:300m`, CPU del PC, mediante API privada |
| Motor PC | `C:\Users\aalva\Documents\Codex\ia-workspace-runtime\speakr-pc` |
| Arranque PC | Tarea **Bears Speakr PC**, al iniciar sesión con el usuario normal |

La capacidad de un PV NFS estático no impone una cuota física de 30 GiB: vigila el espacio real del NAS. No se han reutilizado los PVC de PostgreSQL, Jellyfin o qBittorrent.

El PC escucha solo en `127.0.0.1:18995`. Establece un túnel SSH con huella de pi5 fijada y clave dedicada restringida a ese puerto remoto. El pod usa HTTPS y credencial Bearer para llegar al motor. nginx limita además la ruta interna a pi5 y sus pods. No hay nuevos puertos de router ni reglas de firewall de Windows. Ollama sigue en localhost; el supervisor lo inicia si no está disponible.

Los registros públicos y la inscripción libre están desactivados. La cuenta inicial es administradora. No se han habilitado envíos de correo, integraciones externas, perfiles de voz ni publicación automática de tareas.

## Verificado

- Dieciséis Applications `Synced/Healthy` al terminar la prueba funcional, incluidos los servicios anteriores.
- Inicio de sesión por HTTPS con validación del certificado.
- El pod resuelve el dominio a la IP privada; el motor responde 401 sin credencial y 200 con la suya.
- Audio sintético transcrito en GPU: aproximadamente 7 segundos para unos 13 segundos de audio. No es una estimación garantizada para reuniones largas.
- Resumen en español y respuesta correcta a una pregunta sobre el audio.
- Búsqueda semántica devuelve la grabación de prueba.
- PostgreSQL confirma conexiones cifradas del rol de la aplicación.
- Datos conservados tras recreación del pod.
- Copia inicial privada y restauración a una base temporal: una grabación recuperada y hashes de audios coincidentes. La base temporal se eliminó; la original se conservó.
- PyAV se fijó en `16.0.1` tras detectar incompatibilidad de `19.0.2` con faster-whisper. Dependencias aisladas de ComfyUI y registradas en `requirements-pc.lock`.

El resumen necesita revisión: la transcripción del audio sintético confundió «Bears» con «Verse» y cambió un matiz de «el viernes». No debe usarse como registro exacto sin contrastarlo con el audio.

## Operación

En Windows, arrancar manualmente el motor:

```powershell
Start-ScheduledTask -TaskName 'Bears Speakr PC'
Get-ScheduledTask -TaskName 'Bears Speakr PC'
```

La tarea arranca después del inicio de sesión, no antes de iniciar sesión tras un reinicio. No se ha ensayado un reinicio completo de Windows. Los logs están en `speakr-pc\bridge-error.log` y `speakr-pc\ollama.log`; pueden contener información privada, por lo que no deben subirse sin revisar.

En pi5:

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n speakr get pods,svc,pvc
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n speakr logs deployment/speakr --tail=50
sudo /usr/local/sbin/backup-speakr --restore-test
```

El último comando pausa únicamente Speakr para crear una copia coherente y después lo reanuda. Las copias están bajo `/var/lib/homelab-apps/speakr/backups`, solo para root. Incluyen base de datos, audios y secretos: **no copiarlas a Git/OneDrive**. Esta instalación deja una copia manual probada; no activa todavía un calendario de copias ni una copia externa. Guardar además el directorio privado del PC en un destino de respaldo privado protege la clave del túnel.

La restauración probada es de datos en una base temporal y archivos extraídos; no demuestra una reconstrucción completa desde cero del clúster. Para una recuperación real, primero conservar el estado actual, recuperar los manifiestos, rol/base `speakr`, secreto/CA y el directorio del NAS, y restaurar el dump y los archivos con Speakr detenido. Nunca restaurar encima de una base con datos sin revisar.

## Límites pendientes

- **Separación de hablantes:** no activada. Requiere una fase WhisperX/pyannote, comprobar recursos y aceptar las condiciones de los modelos, con token privado de Hugging Face. No se ha suplantado esa aceptación.
- El conector Whisper utilizado conserva el texto en Speakr; todavía no ofrece el recorrido completo de segmentos temporales/diarización en su interfaz. El motor devuelve tiempos, pero el conector actual los descarta.
- PC apagado o sin sesión iniciada: se puede acceder a los datos del clúster, pero no procesar audio ni generar respuestas. La cola tiene reintentos finitos; si termina en error hay que pulsar reprocesar después de recuperar el PC.
- El bloqueo de GPU coordina los ayudantes multimedia existentes y espera a la cola de ComfyUI antes de empezar. No impide que alguien lance manualmente una generación nueva en ComfyUI o una consulta externa a Ollama durante el proceso. Evita esas operaciones simultáneas.
- No se han probado aún una reunión real larga, subida interrumpida, pantalla bloqueada ni acceso desde el teléfono mediante VPN. La configuración de VPN existente se conserva.
- Se detectó que el resolvedor del host pi5 puede elegir el DNS público para el dominio nuevo. El DNS `.163` y CoreDNS sí devuelven la dirección privada, y Windows lo resolvió correctamente. Las pruebas del host fijaron la IP local conservando SNI y validación TLS; no se desactivó HTTPS. Para diagnosticar en otro dispositivo: consultar `notas.bearsfamily.es` contra `.163` y comprobar que usa el DNS doméstico/VPN.

## Fuentes de implementación

- [Speakr](https://github.com/murtaza-nasir/speakr) y [documentación de instalación](https://murtaza-nasir.github.io/speakr/getting-started/installation/).
- [Grabación móvil](https://murtaza-nasir.github.io/speakr/user-guide/recording/).
- [faster-whisper](https://github.com/SYSTRAN/faster-whisper).
- [WhisperX, fase de hablantes pendiente](https://github.com/m-bain/whisperX).
