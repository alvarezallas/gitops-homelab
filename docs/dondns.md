# DonDNS para WireGuard — 01/11/2026

Implementación publicada en GitOps y aplicada al clúster. **El CronJob empieza pausado y se activa únicamente después de introducir la DonDNS Key y superar una actualización real y la comprobación DNS.** Consulta el estado actual con los comandos de esta guía. La preparación del despliegue no acredita todavía que el DDNS funcione.

## Completar la configuración

1. En DonDominio, confirma que `bearsfamily.es` está activo y que usa el DNS que administra DonDominio. El acceso al panel no demuestra que el registro/delegación ya esté publicado: las consultas iniciales a 1.1.1.1 devolvieron NXDOMAIN para NS/SOA del dominio.
2. En la zona DNS del dominio crea un registro **A**, host **vpn**, apuntando a la IPv4 pública de casa. TTL300 si la interfaz lo permite. Puedes consultar esa IP en pi5 con `curl -4fsS https://api.ipify.org`. No uses192.168.1.163 como valor público. DonDNS actualiza un registro existente; este actualizador no compra dominios, cambia nameservers ni crea registros mediante la API general.
3. En **Mi cuenta → DonDNS Key**, obtén la clave específica DonDNS. No uses la contraseña de tu cuenta ni una clave general de administración. No pegues la clave en el chat, Git, OneDrive, argumentos de comandos o capturas.
4. Ejecuta en una terminal interactiva de pi5:

   ```bash
   sudo python3 /home/alvarense/gitops-homelab/automation/dondns/configure.py
   ```

   Introduce el usuario de DonDominio y la DonDNS Key cuando el asistente los pida. La clave se oculta al escribir y se guarda en el Secret `wireguard/dondns-credentials`, sin fichero local ni impresión. La cuenta administra su propia clave; no se ha supuesto que DonDominio permita limitarla a un único registro. El código del actualizador fija exclusivamente `vpn.bearsfamily.es`.

5. El asistente lanza un Job de comprobación con actualización forzada. Solo si el proveedor acepta el registro/IP y el DNS público coincide, activa el horario en Git, solicita sync manual de homelab-wireguard y cambia el host de wg-easy a `vpn.bearsfamily.es`. Es una actualización SQLite atómica de ese metadato; conserva claves, clientes y cuentas, y no reinicia la VPN.
6. Vuelve a descargar los perfiles existentes o edita solo su Endpoint para usar **vpn.bearsfamily.es:51820**. Los perfiles ya descargados no se cambian automáticamente. No regeneres sus claves.

Si falla la verificación, se conserva la IP inicial de WireGuard y el horario queda pausado. La credencial permanece en Kubernetes para reintentar sin introducirla otra vez:

```bash
sudo python3 /home/alvarense/gitops-homelab/automation/dondns/configure.py --activate
```

Un resultado `dns_not_yet_matching_public_ip` puede deberse a delegación/propagación o caché negativa. Espera y repite después de comprobar el registro. `dns_zone_missing` significa que DonDNS no encuentra la zona/registro solicitado: activa el servicio DNS del dominio y crea A vpn. `provider_credentials_rejected` exige revisar usuario/DonDNS Key. `provider_rejected_update` indica otro rechazo del proveedor. No copies la clave para diagnosticarlo. Los errores HTTP se distinguen mediante `https_http_CODIGO` sin registrar la URL autenticada.

Si hay cambios pendientes en GitOps o una operación Argo en curso, el asistente se detiene antes de continuar esas etapas; revisa el estado y completa el commit/sync correspondiente. No fuerza ramas ni sobrescribe cambios ajenos. Ante un push fallido, no dar por activa la tarea hasta verificar el CronJob real.

## Qué se ejecuta en el clúster

- Namespace `wireguard`, CronJob `dondns`, gestionado por `homelab-wireguard`.
- Cada cinco minutos, Europe/Madrid; `concurrencyPolicy: Forbid`, inicio máximo120s, ejecución máxima100s, sin reintento interno de Job, dos éxitos y dos fallos de historial; Jobs caducan al día.
- Imagen ARM64 fijada a `python:3.13-alpine@sha256:4dec53ac220d1cca3d31d40d346e4c2cd3540c1d7eb058ed70a3f94934728cf2`.
- Usuario10001, raíz de solo lectura, sin capabilities, sin token ServiceAccount, hostPath, hostNetwork, PVC ni permisos RBAC.
- Credencial montada desde Secret como archivos de solo lectura. El pod no administra Kubernetes ni la base de wg-easy; esas operaciones solo las hace el asistente interactivo root en pi5 durante la activación.
- Comprueba la IP pública con dos servicios HTTPS, rechaza IPv4 no pública/discrepancias, consulta DNS público y no actualiza cuando ya coincide. La activación fuerza una petición para validar la credencial aunque DNS ya sea correcto.
- API DonDNS por HTTPS con verificación TLS y sin redirecciones, conforme a la interfaz oficial; la clave va únicamente en memoria durante la solicitud, nunca en argumentos ni logs. No se ejecuta el Bash oficial que deshabilita la validación TLS en su ruta wget.
- Comprueba éxito, nombre exacto, tipo A, valor IP y resolución pública posterior. Solo registra códigos de error fijos, nombre e IP pública; nunca el cuerpo del proveedor, usuario, clave o URL autenticada.
- No publica registro AAAA: WireGuard conserva el diseño de salida IPv4 e IPv6 bloqueado dentro del túnel.

## Verificar y operar

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n wireguard get cronjob dondns
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n wireguard get jobs
dig @1.1.1.1 +short A vpn.bearsfamily.es
curl -4fsS https://api.ipify.org
```

El campo SUSPEND del CronJob debe ser `False` después de activar. Revisa el Job más reciente y sus logs con `kubectl ... logs job/NOMBRE`. Un Job exitoso devuelve JSON con status `updated`, `verified` o `unchanged`. Si falla, devuelve status `error` con reason fijo. Los Jobs de activación tienen prefijo `dondns-activate-`; los programados, `dondns-`.

Después de comprobar DDNS, prueba el móvil con WiFi apagado. La tarea no abre puertos, no evita CGNAT y no garantiza re-resolución automática en clientes WireGuard ya conectados; tras cambiar IP algunos necesitan reconexión.

Para pausar de forma duradera, cambia `spec.suspend` a true en Git y sincroniza homelab-wireguard. Una pausa manual con kubectl puede ser sustituida en un sync posterior. Para rotar clave, ejecuta otra vez el asistente interactivo. No borres la clave del proveedor que necesiten otros equipos sin revisar antes.

## Archivos y recuperación

GitOps:

```text
platform/wireguard/30-dondns-script.yaml
platform/wireguard/31-dondns-cronjob.yaml
platform/wireguard/kustomization.yaml
automation/dondns/configure.py
docs/dondns.md
```

El Secret se excluye de Git y OneDrive. Para un clúster reconstruido aplica manifiestos y vuelve a introducir la clave con el asistente. Si restauras un manifiesto ya activado pero falta el Secret, los Jobs no podrán arrancar; pausa la tarea hasta reponerlo. No se ha creado backup privado de esta clave antes de que exista.

## Validación realizada durante la preparación

Siete pruebas offline: rechazo de IP privada/CGNAT/IPv6, discrepancia entre fuentes de IP, validación del registro exacto y codificación de la clave, omisión cuando no hay cambios, errores sin filtración de credenciales, rechazo de redirecciones y diagnóstico seguro de zona inexistente. Prueba real del contenedor en pi5: runtime no root, HTTPS/CA y coincidencia entre dos fuentes de IP, manejo seguro de credencial ausente. Pod temporal eliminado. La API del proveedor y la actualización real requieren la credencial del usuario y no se dan por probadas por estos checks.

Durante la activación el usuario introdujo la clave en pi5. La primera ejecución devolvió un fallo HTTPS genérico. El diagnóstico posterior confirmó que el proveedor responde con un User-Agent explícito del cliente; se añadió y se distinguieron errores HTTP de errores de zona. DonDNS respondió `The DNS Zone doesn't exist` para vpn.bearsfamily.es. La credencial queda en el Secret, el CronJob sigue pausado y el endpoint WireGuard permanece con su IP anterior hasta validar el registro real. Esta observación no equivale a actualización DNS exitosa.

Fuentes: [API DonDNS y preparación del registro](https://dondominio.dev/es/dondns/docs/api/), [cliente oficial](https://github.com/dondominio/dondns-bash/), [periodicidad documentada](https://dondominio.dev/es/dondns/docs/linux/).
