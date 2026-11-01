# WireGuard instalado con wg-easy — 01/11/2026

Servidor instalado en Kubernetes, pi5 192.168.1.163. Application **homelab-wireguard**, sincronización manual y sin prune. Las trece Applications quedaron Synced/Healthy y los cuatro nodos Ready. La entrada exterior desde 4G/5G sigue pendiente de prueba.

## Entrar y conectar el móvil

1. Desde casa abre **https://wireguard.bearsfamily.aa**. Usa el DNS doméstico 192.168.1.163. Se mantiene el certificado doméstico existente.
2. Usuario **admin**. Para consultar la contraseña inicial, ejecuta en pi5, sin copiar su salida al chat:

   ```bash
   sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n wireguard get secret wireguard-admin-auth -o jsonpath='{.data.password}' | base64 -d; echo
   ```

3. Activa TOTP desde tu perfil y conserva la recuperación de forma privada. Requiere tu aplicación autenticadora; no se ha activado automáticamente.
4. Crea un cliente por dispositivo, por ejemplo `movil-alvaro`. Instala el cliente oficial WireGuard y escanea su QR desde tu panel. El QR contiene claves privadas: no compartirlo ni guardarlo en Git/OneDrive.
5. Desactiva WiFi en el móvil y activa WireGuard. Comprueba handshake reciente en el panel, abre https://bearsfamily.aa y tus aplicaciones, accede al NAS y compara la IP de salida con la de casa. Prueba DNS y que no haya salida IPv6 directa. Repite por plataforma y configura bloqueo fuera de VPN si quieres impedir navegación directa al desconectar.

El Secret conserva la **contraseña inicial**. Si la cambias desde el panel, ese Secret no se actualiza por sí mismo. No restablecer el administrador para resolver una contraseña desactualizada sin revisar antes.

## Red aplicada

| Elemento | Configuración real |
|---|---|
| Transporte | Router UDP51820 → pi5 **UDP51820**, sin traducción a 31820 |
| Publicación Kubernetes | hostPort UDP51820 asociado a 192.168.1.163; red propia del pod, sin hostNetwork |
| Panel | hostPort TCP51821 asociado exclusivamente a 127.0.0.1 |
| Proxy | nginx HTTPS → http://127.0.0.1:51821; allow LAN, localhost y PodCIDR pi5 10.244.0.0/24, deny resto |
| NodePort | Ninguno nuevo; no Service público del panel |
| Clientes | 10.8.0.0/24 y fd42:beaf:1::/64 |
| Rutas de perfiles | 0.0.0.0/0 y ::/0; túnel completo |
| DNS | 192.168.1.163 |
| IPv6 | Capturado en el túnel y bloqueado en servidor; casa no dispone de salida IPv6 verificada |
| NAT | IPv4 dentro del pod y salida habitual CNI por pi5; acceso a LAN e Internet |
| MTU / keepalive | 1380 / 25 segundos |
| Protección del clúster | Rechazo en forwarding VPN a redes de pods, Services, link-local y otros clientes; LAN doméstica permitida |

Los servicios domésticos siguen exigiendo sus propias credenciales. El acceso directo a 51821 desde la LAN falló como se esperaba; el panel funciona por nginx. No se ha probado su inaccesibilidad desde una red exterior. Mantén el único reenvío WAN de la VPN en **UDP51820**; no añadas reenvío del panel.

nginx acepta también el PodCIDR de pi5 porque el tráfico VPN llega tras NAT con IP del pod. Eso incluye otros pods de pi5, que siguen necesitando autenticarse. No se presenta la ACL como aislamiento entre aplicaciones del clúster. La revisión automática exigió confirmación de esta ampliación y el usuario la autorizó expresamente el 01/11/2026; se aplicó entonces.

**Endpoint inicial:** IP pública detectada durante la instalación, guardada en la configuración privada del servidor. `vpn.bearsfamily.es` no devuelve registro A en las consultas realizadas. Hasta configurar el dominio y DDNS, un cambio de IP pública obliga a actualizar el endpoint de los perfiles. Abrir un puerto no demuestra por sí solo ausencia de CGNAT; falta handshake desde 4G/5G para acreditar la entrada WAN.

DonDNS está preparado como CronJob `wireguard/dondns`, cada cinco minutos, inicialmente pausado. El usuario ya introdujo la DonDNS Key de forma privada en pi5. La API responde que la zona DNS no existe; falta activar el servicio DNS/crear A `vpn` y validar propagación. Hasta entonces el endpoint conserva la IP inicial. Guía: [DonDNS](dondns.md) en GitOps y `../dondns-instalacion-20261101/README.md` en la entrega. El asistente `automation/dondns/configure.py --activate` reutiliza el Secret, valida API/DNS, activa el horario en Git y cambia el host; después hay que actualizar los perfiles descargados.

## Permisos y funcionamiento

Imagen wg-easy 15.5.0 ARM64 fijada a:

```text
ghcr.io/wg-easy/wg-easy@sha256:4d19a233a70d519d60f55f7e2cf67da45ccdd4f32a20b4c73ca012580785f8ed
```

Una réplica Recreate, root dentro del contenedor, raíz de solo lectura, **NET_ADMIN como única capability adicional**, sin NET_RAW/SYS_MODULE/privileged, sin kubeconfig ni token ServiceAccount. `/etc/wireguard` usa PVC local 1Gi Retain; no toca NFS/PostgreSQL. Los límites de PV local son declarativos y no constituyen cuota real del filesystem. tmp/run son emptyDir.

El backend legacy falló por permisos de sockets. La revisión automática rechazó añadir NET_RAW. Se comprobó y aplicó la alternativa nft con solo NET_ADMIN; el rechazo no quedó pendiente. Wrappers públicos en ConfigMap seleccionan iptables-nft e ip6tables-nft. Módulos precargados en pi5 mediante `/etc/modules-load.d/homelab-wireguard.conf`: wireguard, nf_tables, nft_chain_nat, nft_reject_ipv6. No hubo cambios en kubelet ni en su lista de sysctls.

El ConfigMap `wireguard-network-policy` aplica hooks y valores predeterminados antes del arranque sobre la base SQLite existente. Es la fuente de configuración de rutas/DNS/MTU/keepalive y firewall. Edita y sincroniza GitOps para cambios persistentes en esos valores; cambios solo desde el panel pueden ser sustituidos al recrear el pod. El endpoint, clientes, cuentas y claves viven en el estado privado. Cambiar ConfigMap exige recrear la réplica para aplicar sus ajustes.

## Verificado

- Panel y login real HTTPS, cookie Secure/HttpOnly, sesión autenticada y logout; API administrativa anónima 401.
- Cliente temporal real: handshake a .163:51820, rutas IPv4/IPv6 al túnel, DNS doméstico, welcome HTTPS, TCP2049 del NAS, salida a Internet con IP pública de casa y salida IPv6 bloqueada. Prueba desde un pod, **no desde Internet**. Cliente revocado y borrado; cero clientes de prueba pendientes.
- Recreación del pod conserva identidad pública y usuario; pod final Ready 1/1, cero reinicios.
- HTTPS de welcome, Argo, Grafana, Prometheus, qBittorrent, pgAdmin, Semaphore, OnTheManga y WireGuard: 200.
- Trece Applications Synced/Healthy, sin habilitar auto-sync ni prune. nginx publicado por el mecanismo Semaphore existente, sin ampliar helper.
- Copia privada cifrada y descifrado/integridad SQLite/identidad contrastados en aislamiento. No se activó una segunda VPN con las mismas claves.

Pendientes: prueba móvil exterior, TOTP del usuario, DDNS, comportamiento de bloqueo al caer VPN por plataforma, reboot físico, medición de velocidad y recuperación integral en un host perdido.

## Persistencia, copia y recuperación

- Estado privado: `/var/lib/homelab-apps/wireguard`, root 0700; base SQLite, configuración y claves.
- Credencial inicial: Secret `wireguard/wireguard-admin-auth`; no se guardó en esta entrega.
- Copia inicial: `/var/backups/homelab-wireguard/wireguard-20261101T213858Z.tar.gpg`, root 0600.
- Clave de cifrado: `/root/.config/homelab-wireguard/backup-passphrase`, root 0600, solo pi5. Debes conservar copia privada independiente de la clave y del archivo cifrado para sobrevivir a pérdida de pi5. No están en OneDrive ni se configuraron backups periódicos.

La copia incluye SQLite consistente, wg0.conf y el Secret de credencial inicial. Se verificó descifrado e integridad; no es una restauración integral ensayada.

Para recuperar **el mismo pi5 con el directorio conservado**, ejecuta `sudo python3 prepare-host.py --execute` y sincroniza homelab-storage y homelab-wireguard. No recrees cuentas ni claves. Para pérdida del directorio, detén primero la réplica y restaura la copia privada en una ubicación root0700 aislada; verifica su contenido e integridad antes de copiar SQLite/configuración a la ruta vacía y reponer el Secret. Nunca extraigas una copia sobre un servidor activo o un directorio con datos sin revisar, y nunca actives simultáneamente dos servidores con las mismas claves. Esta restauración destructiva no se automatiza en la entrega.

Para **instalación nueva sin datos**, prepara módulos/directorio con el script; sincroniza PV y nueva aplicación; completa el asistente desde el panel privado (endpoint público correcto, UDP51820, CIDR y DNS de la tabla). Recrea el pod una vez concluido el asistente para que se apliquen los hooks públicos. La contraseña del asistente será la que elijas; el Secret de contraseña inicial de esta instalación no se genera automáticamente en otra. El script prepare-host no cambia credenciales.

## Operación y reversión

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n wireguard get pods,pvc
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n wireguard exec deployment/wg-easy -- wg show wg0 latest-handshakes
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n wireguard rollout restart deployment/wg-easy
```

Para parar temporalmente, escala el Deployment a cero; al tener sync manual no se recupera por auto-sync. Conserva PVC/PV/estado/Secret. Reanudar con una réplica. Una reversión Git debe revisarse: no volver al primer commit que todavía referenciaba el Secret de bootstrap ya eliminado. La versión funcional es el commit nft indicado en `activation.json`.

La VPN está dentro del clúster: si pi5 o el clúster fallan, no proporciona un canal de rescate independiente.

Fuentes: [wg-easy v15.5.0](https://github.com/wg-easy/wg-easy/releases/tag/v15.5.0), [configuración oficial](https://wg-easy.github.io/wg-easy/latest/advanced/config/optional-config/), [WireGuard y rutas](https://www.wireguard.com/netns/).


## Estado vigente — 02/11/2026: DonDNS activo

Delegación .es publicada a ns1/ns2.dondominio.com; ambos autoritativos y Google/Cloudflare devuelven A vpn.bearsfamily.es→83.61.157.59, TTL600s en esta comprobación. Activación reintentada con la credencial ya guardada y Job exitoso. CronJob wireguard/dondns activo (suspend=false), horario cada5min. wg-easy usa vpn.bearsfamily.es:51820; conserva su cliente existente, claves y pod Ready. Trece Applications Synced/Healthy. Este estado sustituye las notas históricas de horario pausado/registro o delegación pendientes.

Los perfiles ya descargados deben cambiar únicamente Endpoint a vpn.bearsfamily.es:51820 o descargarse de nuevo sin regenerar claves. Falta acreditar conexión desde una red externa si aún no se ha probado. Los dominios web siguen en .aa; no se ejecutó su migración ni emisión de certificados.
