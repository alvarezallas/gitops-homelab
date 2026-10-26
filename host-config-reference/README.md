# Configuración de host como referencia

nginx y dnsmasq viven en Ubuntu de pi5, fuera de Kubernetes. Argo CD no aplica estos archivos. Los certificados privados no se incluyen. Las ClusterIP de la copia son una instantánea: el instalador entrypoint vuelve a consultarlas al aplicarse; no usar la copia sin comprobarlas.

El instalador operativo completo se mantiene fuera de los directorios de Applications. No dar privilegios de host a un pod para ejecutar kubeadm, montar/formatear discos o escribir certificados. Un cambio de estas configuraciones necesita el procedimiento de host existente o, en una fase posterior, automatización de configuración autorizada.
