#!/usr/bin/python3
"""Install validated certificates locally; never export a private key."""
import pathlib,subprocess,os,hashlib,shutil,tempfile,fcntl,sys,json
P=pathlib.Path
SOURCE=P('/var/lib/homelab-apps/certificates/production/config/live/bearsfamily.es')
BASE=P('/etc/nginx/tls/bearsfamily.es')
def run(a):
 p=subprocess.run(a,capture_output=True,timeout=40)
 if p.returncode:raise RuntimeError('TLS validation/deployment command failed: '+a[0])
 return p.stdout
def pointer(path):
 tmp=BASE/'current.next'
 tmp.unlink(missing_ok=True);tmp.symlink_to(path);os.replace(tmp,BASE/'current')
assert os.geteuid()==0
assert sys.argv[1:] in [[],['--stage-only']]
stage=sys.argv[1:]==['--stage-only']
os.umask(0o077)
with open('/run/lock/homelab-nginx-deploy.lock','w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX)
 for f in ['cert.pem','chain.pem','fullchain.pem','privkey.pem']:assert (SOURCE/f).is_file()
 run(['openssl','x509','-in',str(SOURCE/'cert.pem'),'-checkend','86400','-noout'])
 for h in ['bearsfamily.es','argocd.bearsfamily.es','grafana.bearsfamily.es','prometheus.bearsfamily.es','qbittorrent.bearsfamily.es','pgadmin.bearsfamily.es','semaphore.bearsfamily.es','onthemanga.bearsfamily.es','wireguard.bearsfamily.es']:
  run(['openssl','verify','-CApath','/etc/ssl/certs','-untrusted',str(SOURCE/'chain.pem'),'-verify_hostname',h,str(SOURCE/'cert.pem')])
 certpub=run(['openssl','x509','-in',str(SOURCE/'cert.pem'),'-pubkey','-noout'])
 assert certpub==run(['openssl','pkey','-in',str(SOURCE/'privkey.pem'),'-pubout'])
 fp=hashlib.sha256(run(['openssl','x509','-in',str(SOURCE/'cert.pem'),'-outform','DER'])).hexdigest()
 BASE.mkdir(parents=True,exist_ok=True,mode=0o700);BASE.chmod(0o700)
 dest=BASE/'releases'/fp;dest.parent.mkdir(exist_ok=True,mode=0o700)
 old=(BASE/'current').resolve() if (BASE/'current').exists() else None
 if old==dest:
  print(json.dumps({'changed':False,'fingerprint_sha256':fp}));sys.exit(0)
 if not dest.exists():
  temp=P(tempfile.mkdtemp(prefix='candidate-',dir=dest.parent))
  for f in ['cert.pem','chain.pem','fullchain.pem','privkey.pem']:
   shutil.copyfile(SOURCE/f,temp/f);(temp/f).chmod(0o600)
  temp.rename(dest)
 pointer(dest)
 try:
  run(['nginx','-t','-q'])
  if not stage:
   run(['systemctl','reload','nginx'])
   for h in ['bearsfamily.es','argocd.bearsfamily.es','grafana.bearsfamily.es','prometheus.bearsfamily.es','qbittorrent.bearsfamily.es','pgadmin.bearsfamily.es','semaphore.bearsfamily.es','onthemanga.bearsfamily.es','wireguard.bearsfamily.es']:
    run(['curl','--silent','--show-error','--max-time','10','--resolve',h+':443:127.0.0.1','--output','/dev/null','https://'+h+'/'])
   run(['python3','/home/alvarense/gitops-homelab/automation/certificates/validate.py','production'])
   run(['python3','/home/alvarense/gitops-homelab/automation/certificates/backup.py'])
 except BaseException:
  if old:
   pointer(old);run(['nginx','-t','-q']);run(['systemctl','reload','nginx'])
  else:(BASE/'current').unlink(missing_ok=True)
  raise
 print(json.dumps({'changed':True,'fingerprint_sha256':fp,'staged_only':stage,'previous':str(old) if old else None}))
