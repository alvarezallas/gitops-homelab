#!/usr/bin/env python3
"""Root-only, consistent manual backup and optional isolated restore verification."""
import subprocess,pathlib,json,datetime,os,tempfile,tarfile,hashlib,argparse
K=['kubectl','--kubeconfig=/etc/kubernetes/admin.conf']
ROOT=pathlib.Path('/var/lib/homelab-apps/speakr')
def digest(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while chunk:=f.read(1024*1024):h.update(chunk)
 return h.hexdigest()
def run(args,data=None):
 p=subprocess.run(args,input=data,capture_output=True,timeout=240)
 if p.returncode:raise RuntimeError('Backup command failed: '+args[0])
 return p.stdout
def sql(s,db='postgres'):
 return run(K+['exec','-i','-n','databases','homelab-postgres-1','-c','postgres','--','psql','-X','-At','-v','ON_ERROR_STOP=1','-d',db,'-f','-'],s.encode()).decode().strip()
def backup(test=False):
 assert os.geteuid()==0
 os.umask(0o077)
 ns='speakr'
 deploy=json.loads(run(K+['get','deploy','speakr','-n',ns,'-o','json']))
 assert deploy['spec']['replicas']==1
 out=ROOT/'backups'/datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');out.mkdir(parents=True,mode=0o700)
 mount=pathlib.Path('/run/speakr-backup-source');mount.mkdir(mode=0o755,exist_ok=True)
 assert subprocess.run(['mountpoint','-q',str(mount)]).returncode!=0,'Backup mount already active; inspect'
 mounted=False;scaled=False
 try:
  run(K+['scale','deployment/speakr','-n',ns,'--replicas=0']);scaled=True
  run(K+['wait','-n',ns,'--for=delete','pod','-l','app=speakr','--timeout=90s'])
  run(['mount','-t','nfs','-o','ro,nfsvers=4.2,hard','192.168.1.164:/mnt/d01tb/speakr',str(mount)]);mounted=True
  with (out/'database.dump').open('wb') as f:
   p=subprocess.run(K+['exec','-n','databases','homelab-postgres-1','-c','postgres','--','pg_dump','-Fc','-d','speakr'],stdout=f,stderr=subprocess.PIPE,timeout=300)
   assert p.returncode==0,'Database dump failed'
  (out/'secret.json').write_bytes(run(K+['get','secret','speakr-config','-n',ns,'-o','json']))
  (out/'ca.json').write_bytes(run(K+['get','configmap','postgresql-ca','-n',ns,'-o','json']))
  with (out/'audio-and-instance.tar.gz').open('wb') as f:
   p=subprocess.run(['setpriv','--reuid=10001','--regid=10001','--clear-groups','tar','--numeric-owner','-czf','-','-C',str(mount),'.'],stdout=f,stderr=subprocess.PIPE,timeout=300)
   assert p.returncode==0,'Audio archive failed'
  checks={p.name:digest(p) for p in out.iterdir() if p.is_file()}
  (out/'SHA256SUMS.json').write_text(json.dumps(checks,indent=2))
  result={'backup':str(out),'database':'speakr','audio_backup':True,'secret_backup_private':True,'restore_test':False}
  if test:
   db='speakr_restorecheck_'+datetime.datetime.now().strftime('%H%M%S')
   assert not sql("SELECT datname FROM pg_database WHERE datname='"+db+"';")
   sql('CREATE DATABASE '+db+' OWNER speakr_app TEMPLATE template0;')
   try:
    with (out/'database.dump').open('rb') as f:
     p=subprocess.run(K+['exec','-i','-n','databases','homelab-postgres-1','-c','postgres','--','pg_restore','--exit-on-error','--no-owner','--role=speakr_app','-d',db],stdin=f,capture_output=True,timeout=300)
     assert p.returncode==0,'Database restore failed'
    original=sql('SELECT count(*) FROM recording;',db='speakr');restored=sql('SELECT count(*) FROM recording;',db=db);assert original==restored
    with tempfile.TemporaryDirectory(dir=ROOT,prefix='restorecheck-') as tmp:
     with tarfile.open(out/'audio-and-instance.tar.gz') as archive:archive.extractall(tmp,filter='data')
     source_hashes=json.loads(run(['setpriv','--reuid=10001','--regid=10001','--clear-groups','python3','-c',"import pathlib,json,hashlib;p=pathlib.Path('/run/speakr-backup-source');print(json.dumps({str(x.relative_to(p)):hashlib.sha256(x.read_bytes()).hexdigest() for x in (p/'uploads').rglob('*') if x.is_file()}))"]))
     for rel,expected in source_hashes.items():assert digest(pathlib.Path(tmp)/rel)==expected
    result.update(restore_test=True,recordings_restored=int(restored),audio_checksums_verified=True)
   finally:sql('DROP DATABASE '+db+';')
  (ROOT/'backup-latest.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
 finally:
  if mounted:run(['umount',str(mount)])
  if scaled:
   run(K+['scale','deployment/speakr','-n',ns,'--replicas=1'])
   run(K+['rollout','status','deployment/speakr','-n',ns,'--timeout=180s'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--restore-test',action='store_true');args=p.parse_args();backup(args.restore_test)
