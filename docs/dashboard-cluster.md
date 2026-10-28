# Dashboard del clúster bearsfamily

URL: https://grafana.bearsfamily.aa/d/bearsfamily-cluster
Carpeta Homelab, dashboard Bearsfamily · Estado completo del clúster, UID bearsfamily-cluster.

Actualización30s, muestreo30s, tasas de la cabecera promediadas en1min. Arriba CPU en núcleos utilizados, RAM y discos raíz en bytes, RX/TX de interfaces físicas y nodos Ready. Se muestran capacidades y salud (pods no Ready, reinicios, objetivos caídos, PVC sin enlazar, presión de nodo), seguido de consumo actual por nodo. Los filtros Namespace/Pod afectan a los históricos inferiores.

Históricos por pod: CPU en mCPU, working set RAM, RX/TX, lectura y escritura de bloques, reinicios. Las nuevas métricas cAdvisor empiezan a almacenarse al desplegar este cambio: no se recupera consumo antiguo que Prometheus no recogía. Las tasas requieren al menos dos muestras. El rango inicial es1h y la retención existente es15d.

Red de pods: max por pod/interfaz para evitar duplicar sandbox, sum por pod y exclusión de hostNetwork por no poder atribuir el tráfico compartido. El tráfico agregado de nodos incluye LAN entre nodos; no es tráfico WAN. Para hostNetwork consultar las métricas del nodo.

Disco: la cabecera suma solo / en los cuatro nodos. NAS192.168.1.164 queda fuera porque no tiene exporter. Los kubelets actuales no exponen container_fs_usage_bytes: los gráficos por pod son I/O de bloques y no espacio ocupado, y no miden tráfico/capacidad NFS. Un request PVC tampoco es capacidad usada. Los huecos se muestran como Sin datos, no se rellenan con valores inventados.

Prometheus obtiene las seis familias cAdvisor necesarias mediante HTTPS al API server y proxy de los cuatro nodos. Usa ServiceAccount monitoring/prometheus, credencial proyectada y CA del clúster; no se desactiva TLS ni se guardan tokens en Git. ClusterRole homelab-prometheus-metrics permite get nodes/proxy exclusivamente para pi5/pi3b1/pi3b2/pi3b3. Aunque se usa para métricas, nodes/proxy habilita acceso al proxy de esos kubelets: tratar esta identidad como sensible y no reutilizarla para otras aplicaciones.

Dashboard y provider se provisionan desde ConfigMap, carpeta Homelab. allowUiUpdates=false; modificar platform/monitoring/16-configmap-grafana-cluster-dashboard.yaml en Git. La copia JSON exportable se guarda en ia-workspace/dashboards/bearsfamily-cluster-dashboard.json. No se publican credenciales Grafana en Git.

Sincronización manual de homelab-monitoring, sin Prune/Force/Replace ni automatización habilitada. Se añaden ConfigMaps/RBAC y se actualizan solo configuración de Prometheus, datasource y monturas Grafana. Los datos de hostPath y credenciales existentes se conservan. La sincronización produce un reinicio de cada Deployment Recreate.

Fuentes: https://kubernetes.io/docs/concepts/cluster-administration/system-metrics/ y https://grafana.com/docs/grafana/latest/administration/provisioning/.
