# Semaphore Community en el homelab

Una réplica ARM64 en pi5, PostgreSQL existente databases/homelab-postgres, base semaphore y propietario semaphore_app. TLS SQL verify-full y CA pública en ConfigMap semaphore/postgresql-ca, preparada por bootstrap separado. No crear una segunda base ni otro PV. Sin permisos de Kubernetes, acceso a hosts o socket del runtime. Argo manual, sin prune/force/Replace.

URL https://semaphore.bearsfamily.aa, usuario admin. NodePort 30090, nginx al localhost. Contraseña y cuatro claves persistentes en Secret semaphore-web-auth; contraseña SQL en semaphore-db-auth, copiada privadamente desde databases. Esas credenciales no están en este repositorio. Rotar contraseña SQL y copia consumida de forma coordinada; renovar la CA pública antes de retirar la anterior. El ConfigMap de CA no contiene ca.key.

La imagen oficial server-wrapper genera configuración efímera y ejecuta setup/migraciones al iniciar, reutilizando el administrador si existe. Los secretos de cifrado/cookies se fijan mediante Secret y no se regeneran al recrear el pod. El estado de la aplicación está en PostgreSQL; caché, configuración generada y home son reconstruibles. Credenciales de tipo archivo externas requerirán persistencia declarada por separado.

Máximo una tarea simultánea, tiempo máximo 300 s y Europe/Madrid. No hay programaciones de producción ni credenciales Git/SSH instaladas. Piloto local readonly de automation/semaphore/tasks mediante ConfigMap; cualquier acceso a hosts y despliegue automático nginx quedan para las fases 6/7. El override SSH comprueba huellas, frente al valor relajado de la imagen original.

La copia previa al bootstrap se cifra una sola vez en pi5 fuera de Git/OneDrive. Copias periódicas y recuperación completa todavía pendientes. Antes de actualizaciones, guardar base y claves juntas en un respaldo privado recuperable; volver a una imagen anterior no revierte migraciones.

Fuentes: https://github.com/semaphoreui/semaphore/releases/tag/v2.19.17 y https://semaphoreui.com/docs/admin-guide/installation/docker
