# Jellyfin: servidor, NAS y tele conectados

Fecha03/11/2026. Servidor BearsFamily Cinema, Jellyfin12.4.0 ARM64, desplegado en pi5 por ArgoCD (homelab-jellyfin, namespace media). Una réplica, configuración local persistente, mediosNFS de solo lectura. Quince Applications sanas y sincronizadas al verificar. URL: https://jellyfin.bearsfamily.es . Enlace disponible en el menú de aplicaciones de bearsfamily.es.

## Conectar la tele Samsung UE49MU6505

1. Abrir Jellyfin instalado en laTV192.168.1.48.
2. Añadir https://jellyfin.bearsfamily.es como servidor.
3. Usar Conexión rápida. En esta instalación ya se autorizó el código entregado por el usuario para iniciar sesión como bearsfamily. La autorización fue aceptada por el servidor. El código no se guarda en este documento.
4. Entrar en Películas y seleccionar una. Hay cuatro películas indexadas. Elegir calidad Original/Auto sin reducir resolución y, si hay problemas de audio, probar la pistaAC3. Mantener subtítulosSRT cuando sean necesarios; subtítulos que exijan quemado pueden requerir conversión de vídeo, desactivada para este usuario.

Si se cierra sesión, se puede repetir conexión rápida desde un navegador previamente autenticado en Jellyfin (perfil → Conexión rápida), o acceder con usuario bearsfamily y su contraseña. Las credenciales están en el archivo PRIVADO del PC C:\Users\aalva\AppData\Local\Homelab\Jellyfin\acceso.txt. El usuario admin administra el servidor; usar bearsfamily paraTV/tablet. No copiar el archivo de acceso al repositorio/OneDrive.

TabletAndroid: instalar el cliente oficial Jellyfin, introducir la mismaURL y acceder con bearsfamily o conexión rápida. Fuera de casa activar primero WireGuard. La VPN y los puertos del router no se han modificado.

Si laTV antigua falla exclusivamente por confianzaTLS, alternativa solo en LAN: http://192.168.1.163:30093 . No hace falta usarla si HTTPS funciona. No se han desactivado comprobacionesTLS ni instalado certificados privados en laTV. Descubrimiento automático no requerido: la dirección se introduce manualmente.

## Almacenamiento y biblioteca

- OrigenNAS:192.168.1.164:/mnt/d12tb/qbittorrent/downloads, mismo contenido que qBittorrent ve en /downloads. Jellyfin lo monta en /media/movies, NFS4.2 realmente ro, usuario10001sinroot. PV independiente jellyfin-media-pv y PVCmedia/jellyfin-media: no se ha reasignado nfs-pv-12/torrents-pvc.
- Se añadió .ignore con incomplete/, *.!qB y *.part a la carpeta compartida para excluir temporales. No se han movido ni renombrado películas; qBittorrent conserva su funcionamiento/siembra.
- Datos ySQLite: /var/lib/homelab-apps/jellyfin/config en pi5, PVjellyfin-config-pv/PVCjellyfin-config, Retain. Capacidad5Gi declarada, sin cuota física independiente. PostgreSQL compartido no interviene en esta aplicación.
- Caché temporal8Gi en emptyDir. Solicitud250mCPU/768Mi; límites1CPU/2Gi. Vídeo por reproducción directa o remux; transcodificación de vídeo deshabilitada para bearsfamily. Audio puede convertirse. Extracción de trickplay y capítulos desactivada para contener trabajo. Películas actualesH2641080p, audioAC3/EAC3 y subtítulosSubRip según indexación.
- Escaneo horario60min, primer escaneo completado. Monitor en tiempo real desactivado por NFS. Carátulas/metadatos se guardan localmente en la configuración.

## Entrada y seguridad operativa

DNS explícito jellyfin.bearsfamily.es→192.168.1.163. CoreDNS ya reenvía la zona.es. nginx terminaTLS con el wildcard público existente y envía a http://127.0.0.1:30093; WebSocket, streaming sin buffering y tiempos ampliados configurados. Publishernginx comprueba ahoraJellyfin cuando la release contiene jellyfin.conf; distribuidorTLS incluye su nombre. SinUPnP ni publicación web en el router. Configurado KnownProxies para los orígenes de nginx en el host y red localLAN/VPN.

Credenciales inicialesroot: /root/.config/homelab-jellyfin/initial-access.json,0600. Copia privada inicial cifrada: /var/backups/homelab-jellyfin/jellyfin-20261103T215450Z.tar.gz.gpg, clave separada root en /root/.config/homelab-jellyfin/backup-passphrase. Copia online deSQLite con quick_check y descifrado verificados; no se ha ensayado recuperación completa en un clúster nuevo. El respaldo sigue enpi5, no existe copia externa ni horario de backup deJellyfin todavía. Puede repetir manualmente:

```bash
sudo python3 /home/alvarense/gitops-homelab/automation/jellyfin/backup.py
```

Comprobacionesrealizadas: recreación del pod conservó cuentas/configuración; dosPVCBound;4películas; lectura autenticada de1024bytes respondió206; login familiar porHTTPS desdeWindows y WebSocket101 correctos; montajeNFSro yUID10001 comprobados. Reproducción audiovisual en la TV confirmada por el usuario; ver resultado final y corrección de caché al final de este documento.

## Operaciones

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n media get pods,svc,pvc
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n argocd get application homelab-jellyfin
```

Repositorioautoritativo: /home/alvarense/gitops-homelab/apps/jellyfin . Imagen fijada por digest, sin actualizaciones automáticas de imagen ni prune. Para cambios, commit enGit y sincronización manual enArgo. No ejecutar configure.py para cambiar una contraseña de usuario ya existente: usar administración deJellyfin. El asistente depende del archivo privado inicial y no lo publica.

Fuentes: https://jellyfin.org/docs/general/installation/container/ , https://jellyfin.org/docs/general/post-install/networking/reverse-proxy/nginx/ , https://jellyfin.org/docs/general/server/media/excluding-directory/ .


## Incidencia de reproducción y corrección — 03/11/2026

El usuario confirmó imagen y audio correctos pero cortes. El evento deKubernetes mostró Evicted por superar2Gi deemptyDir/cache, seguido de reemplazo depod: causa concreta de interrupción. La configuración inicial de caché era insuficiente con el adelanto sin límite predeterminado. Corregido: EnableThrottling=true, ThrottleDelaySeconds120, EnableSegmentDeletion=true, SegmentKeepSeconds60; caché8Gi y límiteephemeral10Gi para margen (no reserva inmediata en disco). Readiness tolera transitorios hasta60segundos. Ajustes persistidos enconfiguración y asistente de reconstrucción. LaTV está por cable, pingmedido~0.26ms sin pérdidas; no hay evidencia de falloWiFi. Verificada sesiónTizen con direcciónreal .48. Última observación antesdelajuste: DirectPlay; en una sesiónanterior, remux con vídeo y audio directos por SecondaryAudioNotSupported. Confirmar reproducción sostenida despuésdeaplicar: no declarar resueltos los cortes solo por podReady.


## Resultado final confirmado — 03/11/2026

La tele Samsung192.168.1.48 quedó vinculada mediante Conexión rápida al usuario bearsfamily. El usuario confirma que ahora reproduce sin cortes después del ajuste de caché. Observación adicional de40segundos: mismo pod sin reinicios, posición avanzó de380,6 a422,6segundos, caché975→1116MiB y se mantuvo en1116MiB en las últimas muestras. Vídeo y audio originales (IsVideoDirect/IsAudioDirect=true), con cambio de contenedor/remux identificado por SecondaryAudioNotSupported. No se está recodificando el vídeo.

Copia cifrada actualizada incluyendo los ajustes corregidos: /var/backups/homelab-jellyfin/jellyfin-20261103T220346Z.tar.gz.gpg. SQLitequick_check y descifrado correctos. Copia sigue solo enpi5 y no tiene horario periódico.

Acceso TV/tablet: https://jellyfin.bearsfamily.es , usuario bearsfamily. TV ya conectada. Claves de administración y familiar disponibles únicamente en el PC, archivo C:\Users\aalva\AppData\Local\Homelab\Jellyfin\acceso.txt, y archivo privado root del servidor. Nuevos contenidos de la carpeta de descargas se detectan en el escaneo horario o mediante escaneo manual de la biblioteca. Cuatro películas disponibles al cierre. Despliegue y conexión solicitados completados.


## Escaneo manual en curso — 03/11/2026

Ejecutado a petición del usuario después de mover películas. 131 películas ya indexadas y visibles. Último estado Running, progreso 57.6 %. El resultado Completed antiguo de la API corresponde al escaneo anterior, no a este. El trabajo actual sigue procesando metadatos e imágenes; no se cancela ni se vuelve a iniciar..

Durante el primer intento se detectó OOMKilled con el límite inicial de1536Mi. La ampliación a2Gi por sí sola tampoco bastó. Se aplicó procesamiento secuencial (LibraryScanFanoutConcurrency=1, LibraryMetadataRefreshConcurrency=1, ParallelImageEncodingLimit=1), solicitud768Mi/límite2Gi y heap.NET768Mi (DOTNET_GCHeapHardLimit=0x30000000) con GCConserveMemory=9, dejando margen para memoria nativa/archivos. Cambios confirmados enGitOps y sincronizados. Última comprobación: podReady, cero reinicios desde el ajuste final y progreso creciente. No se han movido ni borrado películas al ejecutar el escaneo.

Fuente del ajuste.NET: https://learn.microsoft.com/en-us/dotnet/core/runtime-config/garbage-collector .


## Escaneo manual completado — 03/11/2026

Ejecutado a petición del usuario después de mover películas. 131 películas ya indexadas y visibles. Resultado Completed. Inicio UTC: 2026-11-03T22:26:50.1977786Z; fin UTC: 2026-11-03T22:43:14.3784645Z.

Durante el primer intento se detectó OOMKilled con el límite inicial de1536Mi. La ampliación a2Gi por sí sola tampoco bastó. Se aplicó procesamiento secuencial (LibraryScanFanoutConcurrency=1, LibraryMetadataRefreshConcurrency=1, ParallelImageEncodingLimit=1), solicitud768Mi/límite2Gi y heap.NET768Mi (DOTNET_GCHeapHardLimit=0x30000000) con GCConserveMemory=9, dejando margen para memoria nativa/archivos. Cambios confirmados enGitOps y sincronizados. Última comprobación: podReady, cero reinicios desde el ajuste final y progreso creciente. No se han movido ni borrado películas al ejecutar el escaneo.

Fuente del ajuste.NET: https://learn.microsoft.com/en-us/dotnet/core/runtime-config/garbage-collector .
