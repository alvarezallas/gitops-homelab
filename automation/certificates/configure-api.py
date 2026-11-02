#!/usr/bin/python3
"""Interactive onboarding on pi5. Never place credentials in shell arguments or Git."""
import sys,os,json,getpass,pathlib,subprocess,time,datetime
from dondominio_hook import Provider
assert os.geteuid()==0,'Ejecuta con sudo en pi5'
K=['kubectl','--kubeconfig=/etc/kubernetes/admin.conf']
print('Introduce credenciales de la API general de DonDominio; DonDNS no sirve.')
cfg={'apiuser':input('Usuario API: ').strip(),'apipasswd':getpass.getpass('Clave API (oculta): '),'serviceName':input('Nombre del servicio [bearsfamily.es]: ').strip() or 'bearsfamily.es'}
assert cfg['apiuser'] and cfg['apipasswd']
try:
 p=Provider(cfg);p.call('tool/hello');p.records()
except Exception as exc:raise SystemExit(str(exc)) from None
secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':'dondominio-dns-api','namespace':'certificates'},'type':'Opaque','stringData':{'credentials.json':json.dumps(cfg)}}
r=subprocess.run(K+['apply','-f','-'],input=json.dumps(secret),capture_output=True,text=True);assert r.returncode==0,'No se pudo guardar el Secret privado'
cron=json.loads(subprocess.check_output(K+['-n','certificates','get','cronjob','certbot-renew','-o','json']))
spec=cron['spec']['jobTemplate']['spec'];spec['template']['spec']['containers'][0]['command']=['python','/opt/renew/runner.py','--dry-run']
name='certbot-dns-test-'+str(int(time.time()));job={'apiVersion':'batch/v1','kind':'Job','metadata':{'name':name,'namespace':'certificates'},'spec':spec}
r=subprocess.run(K+['create','-f','-'],input=json.dumps(job),capture_output=True,text=True);assert r.returncode==0,'No se pudo iniciar la prueba'
print('Credenciales guardadas solo en Kubernetes. Prueba DNS-01 iniciada: '+name,flush=True)
deadline=time.monotonic()+5000
while time.monotonic()<deadline:
 j=json.loads(subprocess.check_output(K+['-n','certificates','get','job',name,'-o','json']))
 if j.get('status',{}).get('succeeded'):
  print('PRUEBA CORRECTA. Comunica este resultado para activar el horario en GitOps. El certificado activo no se ha sustituido por uno de prueba.');sys.exit(0)
 if j.get('status',{}).get('failed'):raise SystemExit('La prueba ha fallado. No se activa el horario; revisar el registro privado en pi5.')
 time.sleep(10)
raise SystemExit('Espera agotada. No repetir: comprobar primero el estado del Job '+name)
