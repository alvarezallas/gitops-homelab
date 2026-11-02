# HTTPS público .es y renovación de certificados

Estado a 02/11/2026: migración web y certificado nginx ACTIVOS. Renovación DNS automática PREPARADA, PAUSADA por falta de credenciales de API general de DonDominio. No considerar finalizada esa parte.

Acceso principal: https://bearsfamily.es/ . Desde el menú se accede a Argo, Grafana, Prometheus, pgAdmin, Semaphore, WireGuard, On The Manga y qBittorrent, todos bajo bearsfamily.es. Acceso privado LAN/VPN; no se han abierto puertos web en el router.

Certificado Let's Encrypt válido para bearsfamily.es y *.bearsfamily.es hasta 31/01/2027 21:03:29 Europe/Madrid. Se verificó la cadena con la confianza predeterminada de Python en Windows para los nueve nombres y respuestas HTTP200/302. Cuatro nodos Ready y catorce Applications Synced/Healthy. El DNS habitual de Windows, pi5 y pods devuelve .163 para las aplicaciones y 83.61.157.59 para vpn.bearsfamily.es. DDNS y clientes WireGuard conservados.

## Configuración activa

- DNS privado: /etc/dnsmasq.d/homelab.conf, registros .es explícitos, sin wildcard que capture vpn. CoreDNS reenvía .es a .163. Se conserva compatibilidad DNS .aa.
- nginx usa /etc/nginx/tls/bearsfamily.es/current/{fullchain.pem,privkey.pem}. Copias versionadas por huella en releases/, root0700/clave0600. Cuenta/estado ACME permanecen en el PVC acme-state de certificates, en pi5 /var/lib/homelab-apps/certificates. Ninguna clave se copia a Git o OneDrive.
- Vhosts .aa temporales redirigen a .es con el certificado antiguo. Ese certificado antiguo puede seguir mostrando avisos si se entra por .aa; utilizar directamente .es. No se ha instalado una raíz nueva en Windows.
- Se actualizaron las URLs canónicas de Argo, Grafana, Prometheus, Semaphore y OnTheManga, enlaces del dashboard y del welcome. Usuarios, contraseñas y sus identificadores siguen iguales, incluidos los logins admin@bearsfamily.aa y la carpeta de CA de pgAdmin. Esos identificadores no son sitios web.
- Publicador nginx: comprobaciones por release, confianza pública para .es y confianza anterior para rollback .aa. Incluye OnTheManga y WireGuard. La tarea Semaphore cada minuto está reactivada; tarea4267 verificada correctamente.
- Distribución TLS: homelab-certificate-install.timer en pi5 comprueba cada15min el certificado del PVC. Valida nombres, cadena, vigencia y clave, cambia el puntero de forma atómica y recarga nginx; revierte si falla. Usa el mismo lock que el publicador de configuración. Tras cambios crea/verifica una copia cifrada. Probado arranque de la unidad con el certificado actual (sin cambios).

## Paso pendiente para completar renovación desatendida

1. Solicitar o comprobar acceso a la API general: https://dondominio.dev/es/api/ . DonDNS Key es distinta y solo actualiza IP. DonDominio exige cuenta autorizada, apiuser/apipasswd e IP de salida autorizada. Al tener IP dinámica, confirmar con soporte cómo mantener esa autorización; una allowlist obsoleta impediría renovar. No es necesario comprar otro certificado.
2. Cuando se disponga de las credenciales, entrar por SSH en pi5 y ejecutar:

```bash
sudo python3 /home/alvarense/gitops-homelab/automation/certificates/configure-api.py
```

El asistente pide la clave con entrada oculta, comprueba API/listado DNS, la guarda únicamente en Secret certificates/dondominio-dns-api y lanza un Job de ensayo DNS-01 de Let's Encrypt. No pegar claves en el chat, shell ni Git. El certificado de prueba no reemplaza el de nginx.
3. Tras PRUEBA CORRECTA, activar spec.suspend=false de platform/certificates/31-renew-cronjob.yaml en GitOps y sincronizar homelab-certificates. Aún no se ha hecho: faltan credenciales y prueba real. Horario preparado03:17 y15:17 Europe/Madrid, Forbid y sin reintentos automáticos de fallo. No se fuerza una emisión diaria: certbot renew decide cuándo corresponde.
4. Verificar primer Job real y distribución de una renovación. La prueba completa extremo a extremo sigue pendiente. Si falla el ensayo, inspeccionar privadamente /var/lib/homelab-apps/certificates/production/automation/ y el estado del Job; no publicar logs privados.

El hook crea únicamente TXT del desafío y borra solo los IDs que él creó y cuyo nombre/tipo/valor coinciden. No sustituye la zona completa ni toca A, MX, CNAME o TXT de otros usos. Cinco pruebas offline verifican propiedad/borrado y rechazo de redirecciones HTTP de credenciales. Manifiestos validados con dry-run de Kubernetes. No se afirma integración real de API mientras falten credenciales.

## Recuperación

Rollback privado en pi5: /var/lib/homelab-domain-migration/20261102 contiene el publicador anterior, DNS anterior y puntero de release. Config nginx anterior3af2e53e60cf47ee376e149570d3b4c9c97159cd conservada. Los materiales TLS antiguos se conservan. El publicador nuevo puede seleccionar y validar releases antiguas; volver también URLs de aplicaciones si se revierte completamente la migración. No formatear datos ni sustituir la CA de PostgreSQL o Argo upstream.

Consulta:

```bash
sudo systemctl status homelab-certificate-install.timer
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n certificates get cronjobs,jobs
```

Fuentes: https://dondominio.dev/es/api/docs/api/ y https://eff-certbot.readthedocs.io/en/stable/using.html .
