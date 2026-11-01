# Emisión Let's Encrypt en Kubernetes — 02/11/2026

Instalación del cliente ACME iniciada por orden del usuario. **Primera fase: emisión de prueba con publicación TXT manual.** Consultar `estado-publico.json` para el último estado guardado; los desafíos son temporales y no se reutilizan al empezar otra solicitud.

## Recursos instalados

- Application Argo `homelab-certificates`, sincronización manual; almacenamiento propiedad de homelab-storage.
- Namespace `certificates`, Deployment `certbot-manual`, una réplica Recreate en pi5 ARM64.
- Imagen Certbot5.9.0: `docker.io/certbot/certbot:v5.9.0@sha256:13c94d8a7f0e135583d44a1574813b2404a936c5ba851897259e130a47777c17`.
- PVC `acme-state`, PV `certificates-acme-pv`, local1Gi Retain en `/var/lib/homelab-apps/certificates` root0700. Capacidad declarativa sin cuota real del filesystem.
- El contenedor no tiene capabilities adicionales, privileged, hostNetwork ni token ServiceAccount. Raíz de solo lectura; solo `/acme` y tmp son escribibles. UID0 interno para compatibilidad con la imagen, sin privilegios extra del host.
- Sin Service, Ingress, NodePort ni reenvíos de router nuevos. No modifica DNS automáticamente.

## Flujo real

Se mantiene el desafío manual de DonDominio. Se ha añadido un hook público que recoge los TXT y **solo espera su publicación**, sin clave DNS ni cambios de registros. Cuando aparecen todos los valores en Google y Cloudflare, Certbot continúa la validación. Esto reduce pasos interactivos, pero **no automatiza el mantenimiento DNS ni la renovación**.

El hook usa los parámetros de Certbot `CERTBOT_DOMAIN`/`CERTBOT_IDENTIFIER`, `CERTBOT_VALIDATION` y `CERTBOT_REMAINING_CHALLENGES`. Se comprobó en la imagen instalada que Certbot genera todas las solicitudes antes de iniciar las validaciones. La última espera todos los valores simultáneos. Seis pruebas offline verificaron TXT fragmentado/múltiple, CNAME, transacción incorrecta, NXDOMAIN, respuesta truncada y malformada.

El operador host usa `/var/lib/homelab-acme-operations/session.py`, copia root0700 de la fuente GitOps `automation/certificates/session.py`. Cada sesión tiene ID único, registro privado, contacto privado y resultado. La sesión en segundo plano dura como máximo aproximadamente una hora para DNS y no comienza otra fase sola. No se inicia un segundo intento si el primero sigue pendiente; tampoco se reemite una fase ya exitosa por repetir el comando de inicio.

El correo fue el indicado por el usuario. La cuenta ACME y sus claves viven en el volumen privado. Se inició el registro de prueba con las condiciones que anunciaba el directorio ACME en la ejecución, sin suscribir servicios de pago ni cancelar el SSL de DonDominio.

## Consultar el estado sin exponer claves

En pi5:

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n certificates get pods,pvc
sudo python3 /var/lib/homelab-acme-operations/session.py status staging
sudo python3 /var/lib/homelab-acme-operations/session.py status production
```

El estado devuelve los TXT destinados a DNS público y sus fases. No muestra cuenta privada, clave TLS, contacto ni log íntegro. Para errores, revisar el log privado desde pi5 con cuidado; no copiarlo íntegro al chat/OneDrive porque puede contener información de cuenta/órdenes.

## Publicar los desafíos

DonDominio → bearsfamily.es → Zona DNS → registro TXT, host `_acme-challenge`. Cada valor que indique la sesión es un registro/valor independiente. Mantener ambos cuando se soliciten dos para el mismo nombre. Si existe un CNAME explícito con ese mismo nombre, sustituir solo esa entrada; una respuesta de parking por wildcard no obliga a borrar el wildcard general.

No modificar A vpn, MX, nameservers ni otros TXT. El hook verificará los valores en1.1.1.1 y8.8.8.8 durante3600s como máximo. Al terminar una fase, retirar solo sus valores ya innecesarios. La solicitud de producción genera sus propios desafíos; no reutilizar los de staging.

Los certificados staging no son confiables para Windows y nunca se instalan como raíz ni se publican como certificado real.

## Estado privado y recuperación

- `/acme/staging/config`, work y logs: ensayo.
- `/acme/production/config`, work y logs: producción.
- Dentro de config: conservar accounts, archive, live y renewal; live puede tener symlinks hacia archive.
- `/acme/<fase>/runs/<id>/`: solicitudes TXT y estado del hook.
- `/var/lib/homelab-acme-operations/`: supervisor/config/registro privado/resultados de las sesiones.

No eliminar PVC/PV/directorio ni escalar/recrear el cliente mientras espera una validación. Si el pod muere, conservar el estado y diagnosticar; no intentar sortear límites creando cuentas o solicitudes repetidas. El plan contempla copia privada cifrada y prueba de recuperación después de emitir el certificado real; no se da por creada mientras no se registre una verificación específica.

Una sesión que expire no emitirá indefinidamente ni hará cambios en nginx. Su siguiente intento, si hace falta, debe ser explícito y usar los valores que genere, retirando los TXT viejos correspondientes. No reiniciar toda la infraestructura para reintentar una validación.

## Pendientes

1. Completar TXT y emisión staging.
2. Solicitud de producción y sus TXT; comprobar SAN raíz+wildcard, cadena, fechas y correspondencia de clave.
3. Copia privada cifrada y descifrado/integridad comprobados.
4. Elegir solución DNS automática para renovaciones, con API TXT compatible o delegación limitada. La DonDNS Key actual no cumple esa función.
5. Si se decide usar el certificado en las webs, coordinar entrega a nginx y migración .aa→.es por su plan independiente. La migración sigue detenida y no se ha tocado nginx.

El contenedor preparado **no cambia la validez del certificado que actualmente ve el navegador**: los sitios continúan sirviendo su TLS anterior en .aa. Tampoco se ha instalado cert-manager ni un horario de renovación.
