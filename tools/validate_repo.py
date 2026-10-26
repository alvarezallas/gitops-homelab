#!/usr/bin/env python3
"""Valida estructura, ownership, ausencia de Secrets y guardas GitOps. Requiere PyYAML."""
import pathlib,json,sys,re
import yaml
R=pathlib.Path(__file__).resolve().parents[1]
def require(test,message):
 if not test:raise RuntimeError(message)
def validate():
 config=json.loads((R/'repo-config.json').read_text());owners={};count=0;apps=[]
 for group in sorted((R/'platform').iterdir()):
  k=yaml.safe_load((group/'kustomization.yaml').read_text(encoding='utf-8'))
  for name in k['resources']:
   p=(group/name).resolve();require(p.is_relative_to(group.resolve()),'Recurso fuera de su aplicación')
   for o in yaml.safe_load_all(p.read_text(encoding='utf-8')):
    if not o:continue
    count+=1;require(o['kind']!='Secret','Secret no permitido en Git: '+str(p));require('status' not in o,'status de ejecución en manifiesto')
    meta=o['metadata'];require(not set(meta)&{'uid','resourceVersion','managedFields','creationTimestamp'},'Metadatos de ejecución en '+str(p))
    key=(o['apiVersion'],o['kind'],meta.get('namespace',''),meta['name']);require(key not in owners,'Recurso gestionado por dos Applications: '+str(key));owners[key]=group.name
    if o['kind'] in ('PersistentVolume','PersistentVolumeClaim','StorageClass','Namespace','CustomResourceDefinition'):
     opts=meta.get('annotations',{}).get('argocd.argoproj.io/sync-options','');require('Prune=false' in opts and 'Delete=false' in opts,'Falta protección de dato/recurso crítico')
    if o['kind']=='PersistentVolume':require(o['spec']['nfs']['server']=='192.168.1.164' and o['spec']['persistentVolumeReclaimPolicy']=='Retain','PV no apunta al NAS/Retain')
 for p in (R/'clusters/home').glob('*.yaml'):
  o=yaml.safe_load(p.read_text(encoding='utf-8'))
  if o['kind']!='Application':continue
  apps.append(o);spec=o['spec'];require(not spec['syncPolicy'].get('automated'),'Auto-sync no previsto durante adopción')
  require('ServerSideApply=true' in spec['syncPolicy']['syncOptions'],'SSA requerido')
  require(spec['destination']['server']=='https://kubernetes.default.svc','Destino diferente del clúster local')
  require(spec['source']['repoURL']==config['repoURL'],'URL inconsistente')
  require(not o['metadata'].get('finalizers'),'Finalizer de borrado en Application')
 require(len(apps)==6,'Deben existir seis Applications hijas')
 project=yaml.safe_load((R/'bootstrap/project.yaml').read_text(encoding='utf-8'))
 require(project['spec']['sourceRepos']==[config['repoURL']],'Proyecto no restringido al repo elegido')
 require(project==yaml.safe_load((R/'clusters/home/project.yaml').read_text(encoding='utf-8')),'Copias bootstrap/proyecto gestionado difieren')
 for p in R.rglob('*'):
  if not p.is_file() or '.git' in p.parts or '.venv' in p.parts or '__pycache__' in p.parts:continue
  data=p.read_text(encoding='utf-8',errors='ignore')
  if p.suffix in ('.yaml','.yml'):
   for o in yaml.safe_load_all(data):
    if isinstance(o,dict):require(o.get('kind')!='Secret','Secret incluso fuera del path sincronizado: '+str(p))
  require('-----BEGIN '+'OPENSSH PRIVATE KEY-----' not in data and '-----BEGIN '+'PRIVATE KEY-----' not in data,'Clave privada encontrada')
 print(json.dumps({'resources':count,'child_applications':len(apps),'remote_configured':config['configured'],'secrets_in_git':False,'resource_ownership_unique':True,'result':'OK'},indent=2))
if __name__=='__main__':
 try:validate()
 except (RuntimeError,KeyError,ValueError) as e:print('ERROR: '+str(e),file=sys.stderr);sys.exit(2)
