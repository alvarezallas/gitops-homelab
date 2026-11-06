#!/usr/bin/env python3
"""Consistent n8n + state backups, encrypted before copying to NAS."""
import pathlib,subprocess,json,datetime,os,hashlib,tarfile,tempfile,fcntl,argparse,re
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
ROOT=pathlib.Path('/var/lib/homelab-apps/n8n');P=ROOT/'private';K=['kubectl','--kubeconfig=/etc/kubernetes/admin.conf'];MAGIC=b'N8NBK1'
def run(a,data=None,timeout=180):
 r=subprocess.run(a,input=data,stdin=subprocess.DEVNULL if data is None else None,capture_output=True,timeout=timeout)
 if r.returncode:raise RuntimeError('Failed '+a[0]+': '+r.stderr.decode(errors='replace')[-400:])
 return r.stdout
def pg(args,data=None):return run(K+['-n','databases','exec','-i','homelab-postgres-1','-c','postgres','--']+args,data)
def crypt(src,dst,key,decode=False):
 with src.open('rb') as f,dst.open('wb') as out:
  if decode:
   assert f.read(6)==MAGIC;nonce=f.read(12);f.seek(-16,2);tag=f.read(16);left=f.tell()-16-18;f.seek(18);c=Cipher(algorithms.AES(key),modes.GCM(nonce,tag)).decryptor()
  else:
   nonce=os.urandom(12);out.write(MAGIC+nonce);left=src.stat().st_size;c=Cipher(algorithms.AES(key),modes.GCM(nonce)).encryptor()
  c.authenticate_additional_data(MAGIC)
  while left:
   b=f.read(min(left,1024*1024));assert b;left-=len(b);out.write(c.update(b))
  out.write(c.finalize())
  if not decode:out.write(c.tag)
def restore_test(plain):
 with tempfile.TemporaryDirectory(dir=P,prefix='verify-') as t:
  t=pathlib.Path(t)
  with tarfile.open(plain) as tar:tar.extractall(t,filter='data')
  cfg=json.loads((t/'private/config.json').read_text());secret=json.loads((t/'private/k8s-secret.json').read_text());import base64
  assert cfg['encryption_key']==base64.b64decode(secret['data']['N8N_ENCRYPTION_KEY']).decode()
  counts={}
  for source in ['n8n','automation_state']:
   db='n8n_restorecheck_'+os.urandom(5).hex()
   pg(['createdb','-U','postgres','-O','n8n_app' if source=='n8n' else 'automation_state_app',db])
   try:
    pg(['pg_restore','-U','postgres','--no-owner','--no-acl','--role','n8n_app' if source=='n8n' else 'automation_state_app','--exit-on-error','-d',db],(t/(source+'.dump')).read_bytes())
    q='SELECT count(*) FROM workflow_entity;' if source=='n8n' else 'SELECT count(*) FROM agent_reports;'
    counts[source]=int(pg(['psql','-X','-At','-U','postgres','-d',db,'-c',q]).strip())
    if source=='n8n':
     expected_credentials=int(pg(['psql','-X','-At','-U','postgres','-d',db,'-c','SELECT count(*) FROM credentials_entity;']).strip())
     # Isolated CLI Pod: no web server, no scheduler, no Service, no tool executions.
     name='n8n-restorecheck-'+os.urandom(4).hex()
     original=json.loads(run(K+['-n','n8n','get','deploy','n8n','-o','json']))['spec']['template']['spec']
     import copy
     spec=copy.deepcopy(original);c=spec['containers'][0];spec['restartPolicy']='Never'
     spec['volumes']=[v for v in spec['volumes'] if v['name']!='data']+[{'name':'isolated-data','emptyDir':{}}]
     c['volumeMounts']=[v for v in c['volumeMounts'] if v['name']!='data']+[{'name':'isolated-data','mountPath':'/home/node/.n8n'}]
     for e in c['env']:
      if e['name']=='DB_POSTGRESDB_DATABASE':e['value']=db
     for field in ['startupProbe','readinessProbe','livenessProbe','ports']:c.pop(field,None)
     c['resources']={'requests':{'cpu':'100m','memory':'256Mi'},'limits':{'cpu':'1','memory':'768Mi'}}
     c['command']=['/bin/sh','-c'];c['args']=['n8n export:credentials --all --decrypted --output=/tmp/credentials.json >/tmp/export.log 2>&1 && node -e '+'''\"const f=require('fs');const a=JSON.parse(f.readFileSync('/tmp/credentials.json'));if(a.length<2||a.some(x=>typeof x.data!=='object'))process.exit(2);f.unlinkSync('/tmp/credentials.json');console.log('DECRYPTED_CREDENTIALS_OK:'+a.length)\"''']
     pod={'apiVersion':'v1','kind':'Pod','metadata':{'name':name,'namespace':'n8n','labels':{'app':'n8n-isolated-restorecheck'}},'spec':spec}
     run(K+['apply','-f','-'],json.dumps(pod).encode())
     try:
      run(K+['-n','n8n','wait','--for=jsonpath={.status.phase}=Succeeded','pod/'+name,'--timeout=180s'],timeout=200)
      log=run(K+['-n','n8n','logs',name]).decode();assert 'DECRYPTED_CREDENTIALS_OK:'+str(expected_credentials) in log
      counts['decrypted_credentials']=expected_credentials
     finally:run(K+['-n','n8n','delete','pod',name,'--wait=true','--timeout=40s'])
   finally:pg(['dropdb','-U','postgres',db])
  assert counts['n8n']>=1 and counts['automation_state']>=1
  return {'isolated_database_restore':True,'isolated_credential_decryption':True,'encryption_key_matches_secret':True,'restored_row_counts':counts,'pvc_archive_verified':(t/'data/config').exists()}
def copy_nas(enc):
 mount=pathlib.Path('/run/n8n-backup-target');mount.mkdir(exist_ok=True)
 assert subprocess.run(['mountpoint','-q',str(mount)]).returncode!=0
 run(['mount','-t','nfs','-o','nfsvers=4.2,soft,timeo=50,retrans=2','192.168.1.164:/mnt/d01tb/n8n-backups',str(mount)])
 try:
  code=r'''import pathlib,sys,os,re,datetime,hashlib,json
base=pathlib.Path('/run/n8n-backup-target');name=sys.argv[1];assert re.fullmatch(r'n8n-\d{8}T\d{6}Z\.n8b',name)
os.umask(0o077);target=base/name;tmp=base/(name+'.tmp')
with tmp.open('wb') as f:
 while b:=sys.stdin.buffer.read(1024*1024):f.write(b)
os.replace(tmp,target)
days={};weeks={};files=[p for p in sorted(base.glob('n8n-*.n8b'),reverse=True) if re.fullmatch(r'n8n-\d{8}T\d{6}Z\.n8b',p.name)]
for p in files:
 d=datetime.datetime.strptime(p.name[4:20],'%Y%m%dT%H%M%SZ');days.setdefault(d.date(),p);weeks.setdefault(d.isocalendar()[:2],p)
keep=set(list(days.values())[:7])|set(list(weeks.values())[:4])
for p in files:
 if p not in keep:p.unlink()
print(json.dumps({'file':name,'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}))
'''
  with enc.open('rb') as f:r=subprocess.run(['setpriv','--reuid=10001','--regid=10001','--clear-groups','python3','-c',code,enc.name],stdin=f,capture_output=True,timeout=180)
  assert r.returncode==0,r.stderr.decode()[-400:];d=json.loads(r.stdout);assert d['sha256']==hashlib.sha256(enc.read_bytes()).hexdigest();return d
 finally:run(['umount',str(mount)])
def backup(test=False):
 assert os.geteuid()==0;os.umask(0o077)
 with open('/run/lock/homelab-n8n-backup.lock','w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  cfg=json.loads((P/'config.json').read_text());key=hashlib.sha256(cfg['backup_key'].encode()).digest()
  stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');folder=P/'backups';folder.mkdir(exist_ok=True,mode=0o700);out=folder/('n8n-'+stamp+'.n8b')
  # Stop only n8n; DNS, PostgreSQL and other applications stay running.
  deploy=json.loads(run(K+['-n','n8n','get','deploy','n8n','-o','json']));assert deploy['spec']['replicas']==1
  import time
  for _ in range(30):
   active=int(pg(['psql','-X','-At','-U','postgres','-d','n8n','-c',"SELECT count(*) FROM execution_entity WHERE status IN ('running','new');"]).strip())
   if not active:break
   time.sleep(10)
  assert active==0,'Executions are still running: backup postponed without stopping n8n'
  with tempfile.TemporaryDirectory(dir=P,prefix='backup-') as t:
   t=pathlib.Path(t);scaled=False
   try:
    scaled=True;run(K+['-n','n8n','scale','deployment/n8n','--replicas=0']);run(K+['-n','n8n','wait','--for=delete','pod','-l','app=n8n','--timeout=100s'])
    for db in ['n8n','automation_state']:(t/(db+'.dump')).write_bytes(pg(['pg_dump','-U','postgres','-Fc','-d',db]))
    (t/'k8s-secret.json').write_bytes(run(K+['-n','n8n','get','secret','n8n-config','-o','json']))
    plain=t/'backup.tar.gz'
    with tarfile.open(plain,'w:gz') as tar:
     for db in ['n8n','automation_state']:tar.add(t/(db+'.dump'),arcname=db+'.dump')
     tar.add(ROOT/'data',arcname='data');tar.add(P/'config.json',arcname='private/config.json');tar.add(t/'k8s-secret.json',arcname='private/k8s-secret.json')
     for name in ['owner-metadata.json','agent-metadata.json']:
      if (P/name).exists():tar.add(P/name,arcname='private/'+name)
    crypt(plain,out,key)
   finally:
    if scaled:run(K+['-n','n8n','scale','deployment/n8n','--replicas=1']);run(K+['-n','n8n','rollout','status','deployment/n8n','--timeout=180s'])
   verified=t/'verified.tar.gz';crypt(out,verified,key,True);assert hashlib.sha256(plain.read_bytes()).digest()==hashlib.sha256(verified.read_bytes()).digest()
   result={'encrypted':True,'algorithm':'AES-256-GCM','integrity_verified':True,'nas':copy_nas(out)}
   if test:result.update(restore_test(verified))
   (P/'backup-latest.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
  for p in sorted(folder.glob('n8n-*.n8b'),reverse=True)[11:]:p.unlink()
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--restore-test',action='store_true');args=a.parse_args();backup(args.restore_test)
