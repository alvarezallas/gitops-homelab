# EmisiÃ³n Let's Encrypt en Kubernetes â€” 02/11/2026

InstalaciÃ³n del cliente ACME iniciada por orden del usuario. **Primera fase: emisiÃ³n de prueba con publicaciÃ³n TXT manual.** Consultar `estado-publico.json` para el Ãºltimo estado guardado; los desafÃ­os son temporales y no se reutilizan al empezar otra solicitud.

## Recursos instalados

- Application Argo `homelab-certificates`, sincronizaciÃ³n manual; almacenamiento propiedad de homelab-storage.
- Namespace `certificates`, Deployment `certbot-manual`, una rÃ©plica Recreate en pi5 ARM64.
- Imagen Certbot5.9.0: `docker.io/certbot/certbot:v5.9.0@sha256:13c94d8a7f0e135583d44a1574813b2404a936c5ba851897259e130a47777c17`.
- PVC `acme-state`, PV `certificates-acme-pv`, local1Gi Retain en `/var/lib/homelab-apps/certificates` root0700. Capacidad declarativa sin cuota real del filesystem.
- El contenedor no tiene capabilities adicionales, privileged, hostNetwork ni token ServiceAccount. RaÃ­z de solo lectura; solo `/acme` y tmp son escribibles. UID0 interno para compatibilidad con la imagen, sin privilegios extra del host.
- Sin Service, Ingress, NodePort ni reenvÃ­os de router nuevos. No modifica DNS automÃ¡ticamente.

## Flujo real

Se mantiene el desafÃ­o manual de DonDominio. Se ha aÃ±adido un hook pÃºblico que recoge los TXT y **solo espera su publicaciÃ³n**, sin clave DNS ni cambios de registros. Cuando aparecen todos los valores en Google y Cloudflare, Certbot continÃºa la validaciÃ³n. Esto reduce pasos interactivos, pero **no automatiza el mantenimiento DNS ni la renovaciÃ³n**.

El hook usa los parÃ¡metros de Certbot `CERTBOT_DOMAIN`/`CERTBOT_IDENTIFIER`, `CERTBOT_VALIDATION` y `CERTBOT_REMAINING_CHALLENGES`. Se comprobÃ³ en la imagen instalada que Certbot genera todas las solicitudes antes de iniciar las validaciones. La Ãºltima espera todos los valores simultÃ¡neos. Seis pruebas offline verificaron TXT fragmentado/mÃºltiple, CNAME, transacciÃ³n incorrecta, NXDOMAIN, respuesta truncada y malformada.

El operador host usa `/var/lib/homelab-acme-operations/session.py`, copia root0700 de la fuente GitOps `automation/certificates/session.py`. Cada sesiÃ³n tiene ID Ãºnico, registro privado, contacto privado y resultado. La sesiÃ³n en segundo plano dura como mÃ¡ximo aproximadamente una hora para DNS y no comienza otra fase sola. No se inicia un segundo intento si el primero sigue pendiente; tampoco se reemite una fase ya exitosa por repetir el comando de inicio.

El correo fue el indicado por el usuario. La cuenta ACME y sus claves viven en el volumen privado. Se iniciÃ³ el registro de prueba con las condiciones que anunciaba el directorio ACME en la ejecuciÃ³n, sin suscribir servicios de pago ni cancelar el SSL de DonDominio.

## Consultar el estado sin exponer claves

En pi5:

```bash
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n certificates get pods,pvc
sudo python3 /var/lib/homelab-acme-operations/session.py status staging
sudo python3 /var/lib/homelab-acme-operations/session.py status production
```

El estado devuelve los TXT destinados a DNS pÃºblico y sus fases. No muestra cuenta privada, clave TLS, contacto ni log Ã­ntegro. Para errores, revisar el log privado desde pi5 con cuidado; no copiarlo Ã­ntegro al chat/OneDrive porque puede contener informaciÃ³n de cuenta/Ã³rdenes.

## Publicar los desafÃ­os

DonDominio â†’ bearsfamily.es â†’ Zona DNS â†’ registro TXT, host `_acme-challenge`. Cada valor que indique la sesiÃ³n es un registro/valor independiente. Mantener ambos cuando se soliciten dos para el mismo nombre. Si existe un CNAME explÃ­cito con ese mismo nombre, sustituir solo esa entrada; una respuesta de parking por wildcard no obliga a borrar el wildcard general.

No modificar A vpn, MX, nameservers ni otros TXT. El hook verificarÃ¡ los valores en1.1.1.1 y8.8.8.8 durante3600s como mÃ¡ximo. Al terminar una fase, retirar solo sus valores ya innecesarios. La solicitud de producciÃ³n genera sus propios desafÃ­os; no reutilizar los de staging.

Los certificados staging no son confiables para Windows y nunca se instalan como raÃ­z ni se publican como certificado real.

## Estado privado y recuperaciÃ³n

- `/acme/staging/config`, work y logs: ensayo.
- `/acme/production/config`, work y logs: producciÃ³n.
- Dentro de config: conservar accounts, archive, live y renewal; live puede tener symlinks hacia archive.
- `/acme/<fase>/runs/<id>/`: solicitudes TXT y estado del hook.
- `/var/lib/homelab-acme-operations/`: supervisor/config/registro privado/resultados de las sesiones.

No eliminar PVC/PV/directorio ni escalar/recrear el cliente mientras espera una validaciÃ³n. Si el pod muere, conservar el estado y diagnosticar; no intentar sortear lÃ­mites creando cuentas o solicitudes repetidas. El plan contempla copia privada cifrada y prueba de recuperaciÃ³n despuÃ©s de emitir el certificado real; no se da por creada mientras no se registre una verificaciÃ³n especÃ­fica.

Una sesiÃ³n que expire no emitirÃ¡ indefinidamente ni harÃ¡ cambios en nginx. Su siguiente intento, si hace falta, debe ser explÃ­cito y usar los valores que genere, retirando los TXT viejos correspondientes. No reiniciar toda la infraestructura para reintentar una validaciÃ³n.

## Pendientes

1. Completar TXT y emisiÃ³n staging.
2. Solicitud de producciÃ³n y sus TXT; comprobar SAN raÃ­z+wildcard, cadena, fechas y correspondencia de clave.
3. Copia privada cifrada y descifrado/integridad comprobados.
4. Elegir soluciÃ³n DNS automÃ¡tica para renovaciones, con API TXT compatible o delegaciÃ³n limitada. La DonDNS Key actual no cumple esa funciÃ³n.
5. Si se decide usar el certificado en las webs, coordinar entrega a nginx y migraciÃ³n .aaâ†’.es por su plan independiente. La migraciÃ³n sigue detenida y no se ha tocado nginx.

El contenedor preparado **no cambia la validez del certificado que actualmente ve el navegador**: los sitios continÃºan sirviendo su TLS anterior en .aa. Tampoco se ha instalado cert-manager ni un horario de renovaciÃ³n.


## Staging completado; producción esperando sus TXT — 02/11/2026

La sesión staging e0489ad1fc3b485f92be1afbe2a4bac9 terminó con exit0. Validación: SAN bearsfamily.es y *.bearsfamily.es, clave correspondiente y permisos privados, fechas vigentes; cadena staging correctamente no confiable en el almacén normal. No usar ese certificado para el navegador.

Iniciada una única solicitud de producción, sesión8db5232d9c4b4e04adbf0fa96dbe9661. Estado actual y valores exactos en production-status.json / estado-publico.json. Se ha pedido al usuario editar los dos TXT anteriores para publicar los de producción. Los anteriores ya no son necesarios para staging.

No se ha emitido aún producción ni cambiado nginx o los nombres de las webs. Después de emitir quedan la validación de cadena pública, copia privada cifrada y decisión de renovación desatendida.


## Certificado real emitido y validado — 02/11/2026

Producción completada (exit0), sesión 4c9285e254ed4739ae727ee9f3784235. Cubre bearsfamily.es y *.bearsfamily.es. Emisor Let's Encrypt YE1. Vigente hasta 31/01/2027 a las 20:03:29 UTC (21:03:29 en Madrid). Verificados SAN, vigencia, clave correspondiente, permisos privados y cadena pública con comprobación del nombre grafana.bearsfamily.es mediante OpenSSL.

Estado privado persistente en pi5: /var/lib/homelab-apps/certificates/production/config/live/bearsfamily.es/ (en el contenedor: /acme/production/config/live/bearsfamily.es/). No copiar privkey.pem, cuentas ni registros privados a Git, OneDrive o al chat.

Copia cifrada AES256 en /var/backups/homelab-certificates/acme-20261102T210232Z.tar.gpg. Se comprobó descifrado aislado, correspondencia de clave y conservación de cuentas. Contraseña únicamente en /root/.config/homelab-certificates/backup-passphrase. Copia local en pi5, todavía sin respaldo externo ni programación periódica.

La creación inicial está completada. Los dos TXT de esta validación ya pueden eliminarse; no eliminar otros registros DNS. nginx sigue con su certificado anterior y las webs conservan .aa. Este certificado no cubre .aa. No se ha ejecutado la migración de dominio ni instalado el nuevo certificado en nginx.

Renovación automática pendiente: el método actual requiere nuevos TXT manuales y no permite renovación desatendida. DonDNS para actualizar A no sustituye una integración DNS-01 con escritura TXT. Resolver esta integración y la instalación/distribución antes de considerar completado el ciclo de vida de certificados.
