# GitOps del homelab

Preparado26/10/2026 desde los manifiestos instalados y el estado real de CoreDNS/Argo. **Repositorio local sin remoto; no se ha aplicado ninguna Application ni transferido gestión al clúster.**

## Qué controla

| Application | Contenido |
|---|---|
| homelab-root | AppProject y seis Applications hijas |
| homelab-storage | Namespaces de descargas, StorageClass, tres PV NFS y PVC existente |
| homelab-flannel | CNI Flannel fijado por digest |
| homelab-coredns-config | ConfigMap CoreDNS, incluida zona bearsfamily.aa |
| homelab-monitoring | Prometheus, Grafana, kube-state-metrics y cuatro node-exporter |
| homelab-downloads | qBittorrent y sus Services, WebUI30081 |
| homelab-argocd | Argo CD3.5.6 gestionándose a sí mismo, excepto Secrets |

Argo ya tiene acceso Kubernetes interno con el ServiceAccount argocd-application-controller. Destino de todas las apps: https://kubernetes.default.svc. No copiar admin.conf, clave SSH del servidor o tokens del clúster al repo; no ejecutar argocd cluster add para volver a registrar este mismo clúster.

## Límites de «todo el clúster»

Git controla el estado declarativo de los servicios y add-ons anteriores. Ubuntu/Debian, arranque/cgroups, kubeadm, etcd, kubelet/containerd, kube-proxy y versiones base de CoreDNS siguen en el procedimiento de bootstrap/actualización. nginx/DNS de host, NAS, discos y backups también están fuera de Argo. host-config-reference contiene copias públicas como referencia, **no se sincroniza**. No confundir Git con copia de datos: históricos Prometheus/Grafana, sesiones de descargas, claves/certificados y etcd requieren backups independientes.

Los Secrets reales se mantienen fuera de Git, incluido grafana-admin, secretos de Argo, credenciales del repositorio y certificados. El AppProject prohíbe declarar Secret. En un clúster vacío se necesita primero el bootstrap existente que crea Argo y credenciales iniciales; este repo no reconstruye por sí solo las contraseñas ni los datos.

## 1. Crear y publicar el repositorio remoto

Crear en tu proveedor (por ejemplo GitHub) un repositorio **privado** llamado homelab-gitops, vacío y sin README generado. No se ha creado una cuenta o repositorio remoto por ti. En PowerShell:

```powershell
cd D:\Programas\Microsoft-VS-Code-work\cluster\gitops-homelab
python tools/configure_repo.py --url https://github.com/TU_CUENTA/homelab-gitops.git --branch main
git status
git add .
git commit -m "Preparar gestión GitOps del homelab"
git remote add origin https://github.com/TU_CUENTA/homelab-gitops.git
git push -u origin main
```

Sustituir TU_CUENTA por la cuenta real. El repo local ya está inicializado en main; no tiene commit si falta tu identidad Git. Si git commit lo pide, configurar **solo en este repo** tu nombre/correo reales con git config user.name y git config user.email. No se han inventado autores ni cambiado la configuración global. La URL del remoto y la de Argo deben ser la misma; si eliges SSH usa git@github.com:TU_CUENTA/homelab-gitops.git en ambos lugares. El script configure_repo no contiene credenciales, no aplica manifiestos y rechaza tokens dentro de la URL.

Autenticar Git mediante tu gestor de credenciales/GitHub; nunca poner PAT/contraseña en la URL ni subir claves privadas. OneDrive conserva una copia pública sin .git en ia-workspace/gitops-homelab. La copia operativa Git es la ruta de D:.

## 2. Dar a Argo acceso de lectura al repositorio

Es un permiso diferente al acceso al clúster, que ya tiene. Para un repo privado puedes usar **Settings → Repositories → Connect Repo** en https://argocd.bearsfamily.aa:

- HTTPS: URL sin credenciales y token de lectura del proveedor introducido solo en Argo; en GitHub limitarlo a ese repo y lectura de Contents. No pegar el token en chat, YAML o Git.
- SSH: crear una clave de despliegue dedicada, registrar su parte pública en el repositorio con acceso **solo lectura**, e introducir la privada únicamente en la conexión Argo. No reutilizar la clave servidor de las Raspberry. Verificar host key del proveedor; no desactivar verificación SSH/TLS.

Argo guarda esa conexión en un Secret del namespace argocd. Es normal que no esté en Git. El objetivo de este paso es **Connection status: Successful**, comprobado por Argo al clonar el repo. Un repo público no necesita credenciales de lectura, pero no es necesario publicar tu topología.

## 3. Crear Project y aplicación raíz

Solo después de publicar, configurar la URL real y obtener conexión Successful. Copiar el repo a ~/gitops-homelab en pi5 o clonarlo con tus propias credenciales. Desde SSH en pi5:

```bash
cd ~/gitops-homelab
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf apply --server-side -f bootstrap/project.yaml
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf apply --server-side -f bootstrap/root-application.yaml
sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n argocd get applications
```

**No aplicar mientras repo-config.json diga configured:false o la URL contenga example.invalid. No ejecutar kubectl apply -f . ni aplicar platform/ entero.** Estos comandos crean la raíz; todavía no sincronizan automáticamente servicios. En Argo abre homelab-root, comprueba Diff y pulsa Sync sin Prune. Creará las seis apps hijas y adoptará el Project desde clusters/home/project.yaml. El Project bootstrap es una copia inicial; validate_repo comprueba que ambas coinciden.

## 4. Adoptar lo existente, sin recrearlo

Antes, guardar un backup independiente y verificar servicios/PV/Secrets existentes. Esta adopción conserva nombres/namespaces y no usa Force, Replace ni borrado de PV/PVC. Para cada app: Refresh → Diff → revisar → Sync manual con Prune y Force desmarcados. Orden:

1. homelab-storage: PV12/PVC siguen Bound, NAS .164 y Retain; rechazar cualquier diff que cambie path/servidor/volumeName de forma inesperada.
2. homelab-flannel: comprobar cuatro Ready y red; no actualizar imagen en la primera adopción.
3. homelab-coredns-config: comprobar DNS interno, externo y bearsfamily.aa.
4. homelab-monitoring: seis targets up y Grafana datasource correcto.
5. homelab-downloads: web qBittorrent y PVC siguen funcionando; no restablecer contraseña ni editar archivos privados.
6. homelab-argocd **al final**: SSA habilitado, sesión/health funcionando y acceso SSH/kubectl alternativo disponible.

Las anotaciones sync-wave ordenan la creación de Applications en la raíz; **no sincronizan por sí mismas las hijas ni garantizan ese orden de ejecución**. Se sigue manualmente la lista anterior. Argo aplica SSA y puede tomar propiedad de campos ya gestionados por el instalador; revisar Diff antes de cada primera sincronización. ClientSideApplyMigration=false evita migración client-side innecesaria de estos recursos y CRDs grandes.

Namespaces, PV/PVC/StorageClass, CRDs, recursos Argo y componentes críticos llevan Prune=false/Delete=false. Las Applications no llevan finalizer de borrado en cascada. No hay automated ni prune ni selfHeal activados. Esto protege la adopción; las eliminaciones posteriores necesitan una decisión explícita. El Project es administrativo, permite recursos de clúster y namespace argocd: quien puede escribir y sincronizar este repo puede administrar el clúster. Restringir colaboradores y proteger main.

## 5. Trabajo diario

Editar YAML, revisar git diff, commit y push. Argo detecta OutOfSync; abrir Diff y Sync para aplicar. Comprobar Synced/Healthy y comportamiento real. Para deshacer cambios de configuración, git revert del commit y sincronizar. Un revert no restaura datos borrados ni bases incompatibles tras actualizar imágenes.

Cuando la adopción sea estable, puedes habilitar automated/selfHeal **por app** mediante un commit. Mantener storage/Argo/CNI y borrados bajo revisión; no activar prune global ni cambiar imágenes y ownership a la vez. Después de adoptar, no volver a ejecutar addons del instalador como otro gestor sobre esos mismos recursos; conservarlo para bootstrap/recuperación y actualizar Git como fuente del estado deseado.

## Validaciones y aceptación

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r tools/requirements-validation.txt
.\.venv\Scripts\python.exe tools/validate_repo.py
```

En pi5, kubectl kustomize platform/monitoring y los demás paths deben renderizar sin error. Las pruebas de preparación comprueban ownership único, ausencia de Secrets/metadata de ejecución, PV Retain/.164, sincronización manual y SSA. No equivalen a un sync remoto real: falta crear el remoto y conectar credenciales.

Aceptación final: repo Connection Successful; raíz más seis hijas visibles; cada hija Synced/Healthy tras su adopción; cuatro nodos Ready, seis targets up, DNS, UIs y PV12/PVC Bound. No declarar GitOps operativo solo porque se haya creado el repositorio local.

Referencias: [destino local y App of Apps](https://argo-cd.readthedocs.io/en/stable/operator-manual/declarative-setup/), [repositorios privados](https://argo-cd.readthedocs.io/en/stable/user-guide/private-repositories/), [SSA, migración y protección de borrado](https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/).
