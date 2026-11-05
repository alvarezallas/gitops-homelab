#!/usr/bin/env python3
"""Consistent encrypted AdGuard backups; plaintext and key never leave private storage."""
import pathlib,os,subprocess,json,datetime,hashlib,tempfile,tarfile,shutil,time,base64,urllib.request,fcntl,re,argparse
from cryptography.hazmat.primitives.ciphers import Cipher,algorithms,modes
ROOT=pathlib.Path('/var/lib/homelab-apps/adguard-home');PRIV=ROOT/'private';K=['kubectl','--kubeconfig=/etc/kubernetes/admin.conf'];MAGIC=b'AGHBK1'
def run(a,data=None,timeout=180):
 p=subprocess.run(a,input=data,capture_output=True,timeout=timeout)
 if p.returncode:raise RuntimeError('Command failed: '+a[0])
 return p.stdout
def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  while chunk:=f.read(1024*1024):h.update(chunk)
 return h.hexdigest()
def encrypt(src,dst,key):
 nonce=os.urandom(12);enc=Cipher(algorithms.AES(key),modes.GCM(nonce)).encryptor();enc.authenticate_additional_data(MAGIC)
 with src.open('rb') as f,dst.open('wb') as out:
  out.write(MAGIC+nonce)
  while chunk:=f.read(1024*1024):out.write(enc.update(chunk))
  out.write(enc.finalize());out.write(enc.tag)
def decrypt(src,dst,key):
 with src.open('rb') as f:
  assert f.read(6)==MAGIC;nonce=f.read(12);f.seek(-16,2);tag=f.read(16);remaining=f.tell()-16-18;f.seek(18)
  dec=Cipher(algorithms.AES(key),modes.GCM(nonce,tag)).decryptor();dec.authenticate_additional_data(MAGIC)
  with dst.open('wb') as out:
   while remaining:
    chunk=f.read(min(1024*1024,remaining));assert chunk;remaining-=len(chunk);out.write(dec.update(chunk))
   out.write(dec.finalize())
def auth_api(url):
 d=json.loads((PRIV/'credentials.json').read_text());h={'Authorization':'Basic '+base64.b64encode((d['username']+':'+d['password']).encode()).decode()}
 with urllib.request.urlopen(urllib.request.Request(url,headers=h),timeout=15) as f:return json.load(f)
def restore_check(plain):
 # Restore into a separate work subdirectory; bind only loopback, no Service or host port.
 import yaml
 with tempfile.TemporaryDirectory(dir=PRIV,prefix='restore-') as tmp:
  temp=pathlib.Path(tmp)
  with tarfile.open(plain) as tar:tar.extractall(temp,filter='data')
  backup_conf=temp/'conf/AdGuardHome.yaml';assert backup_conf.exists()
  cfg=yaml.safe_load(backup_conf.read_text());assert cfg['users'] and cfg['filters']
  name='restorecheck-'+os.urandom(5).hex();dest=ROOT/'work'/name;dest.mkdir(mode=0o700);os.chown(dest,10001,10001)
  cfg['http']['address']='127.0.0.1:13001';cfg['dns']['bind_hosts']=['127.0.0.1'];cfg['dns']['port']=15353
  for section in ['querylog','statistics']:cfg[section]['dir_path']=''
  dstconf=dest/'conf';shutil.copytree(temp/'conf',dstconf)
  shutil.copytree(temp/'work',dest/'work')
  (dstconf/'AdGuardHome.yaml').write_text(yaml.safe_dump(cfg,sort_keys=False))
  for p in [dest,*dest.rglob('*')]:os.chown(p,10001,10001)
  inside='/opt/adguardhome/work/'+name
  log=PRIV/'restorecheck.log';pf=None;proc=None
  try:
   with log.open('wb') as output:
    proc=subprocess.Popen(K+['exec','-n','dns-filter','deployment/adguard-home','--','/runtime/AdGuardHome','--no-check-update','-c',inside+'/conf/AdGuardHome.yaml','-w',inside+'/work','--pidfile',inside+'/pid'],stdout=output,stderr=output)
    pod=json.loads(run(K+['get','pods','-n','dns-filter','-l','app=adguard-home','-o','json']))['items'][0]['metadata']['name']
    pf=subprocess.Popen(K+['port-forward','-n','dns-filter','pod/'+pod,'13002:13001','--address=127.0.0.1'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    ready=False
    for _ in range(50):
     try:
      status=auth_api('http://127.0.0.1:13002/control/status')
      if status['dns_port']==15353:ready=True;break
     except Exception:pass
     time.sleep(.3)
    assert ready,'Restored instance did not start'
    filters=auth_api('http://127.0.0.1:13002/control/filtering/status');assert filters['enabled'] and filters['filters'][0]['rules_count']>0
    # Use the restored DNS process inside the pod, never advertise it on the LAN.
    q=run(K+['exec','-n','dns-filter',pod,'--','/bin/busybox','nslookup','pagead2.googlesyndication.com','127.0.0.1:15353']).decode();assert '0.0.0.0' in q,q
   return {'isolated_restore':True,'restored_login':True,'restored_dns_blocking':True,'no_lan_publication':True}
  finally:
   if pf:pf.terminate();pf.wait(timeout=10)
   try:
    if (dest/'pid').exists():
     pid=(dest/'pid').read_text().strip();assert pid.isdigit()
     run(K+['exec','-n','dns-filter','deployment/adguard-home','--','/bin/sh','-c',f'kill -TERM {pid}'])
    if proc:proc.wait(timeout=20)
   finally:
    if proc and proc.poll() is None:proc.terminate()
    assert dest.parent==ROOT/'work' and dest.name.startswith('restorecheck-');shutil.rmtree(dest)
def offsite(enc):
 mount=pathlib.Path('/run/adguard-backup-target');mount.mkdir(mode=0o755,exist_ok=True)
 assert subprocess.run(['mountpoint','-q',str(mount)]).returncode!=0
 run(['mount','-t','nfs','-o','nfsvers=4.2,soft,timeo=50,retrans=2','192.168.1.164:/mnt/d01tb/adguard-backups',str(mount)])
 try:
  writer="""import pathlib,sys,hashlib,os,re,datetime,json
os.umask(0o077);base=pathlib.Path('/run/adguard-backup-target');name=sys.argv[1];assert re.fullmatch(r'adguard-\\d{8}T\\d{6}Z\\.agh',name)
tmp=base/(name+'.tmp');target=base/name
with tmp.open('wb') as f:
 while chunk:=sys.stdin.buffer.read(1024*1024):f.write(chunk)
os.replace(tmp,target)
files=sorted([p for p in base.glob('adguard-*.agh') if re.fullmatch(r'adguard-\\d{8}T\\d{6}Z\\.agh',p.name)],reverse=True)
days={};weeks={}
for p in files:
 d=datetime.datetime.strptime(p.name[8:24],'%Y%m%dT%H%M%SZ');days.setdefault(d.date(),p);weeks.setdefault(d.isocalendar()[:2],p)
keep=set(list(days.values())[:7])|set(list(weeks.values())[:4])
for p in files:
 if p not in keep:p.unlink()
h=hashlib.sha256()
with target.open('rb') as f:
 while chunk:=f.read(1024*1024):h.update(chunk)
print(json.dumps({'name':name,'sha256':h.hexdigest(),'daily_retention':7,'weekly_retention':4}))
"""
  with enc.open('rb') as f:
   p=subprocess.run(['setpriv','--reuid=10001','--regid=10001','--clear-groups','python3','-c',writer,enc.name],stdin=f,capture_output=True,timeout=180)
  assert p.returncode==0,p.stderr.decode()[-800:]
  result=json.loads(p.stdout);assert result['sha256']==sha(enc);return result
 finally:run(['umount',str(mount)])
def backup(test=False):
 assert os.geteuid()==0;os.umask(0o077)
 with open('/run/lock/homelab-adguard-backup.lock','w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  deploy=json.loads(run(K+['get','deployment','adguard-home','-n','dns-filter','-o','json']));assert deploy['spec']['replicas']==1
  enabled=json.loads(run(['/usr/local/sbin/homelab-adguard-dns','status']))['mode']=='enabled'
  folder=PRIV/'backups';folder.mkdir(mode=0o700,exist_ok=True);stamp=datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ');out=folder/('adguard-'+stamp+'.agh')
  plain=folder/('plain-'+stamp+'.tar.gz');scaled=False
  try:
   if enabled:run(['/usr/local/sbin/homelab-adguard-dns','bypass'])
   scaled=True;run(K+['scale','deployment/adguard-home','-n','dns-filter','--replicas=0']);run(K+['wait','-n','dns-filter','--for=delete','pod','-l','app=adguard-home','--timeout=90s'])
   with tarfile.open(plain,'w:gz') as tar:
    for name in ['conf','work']:tar.add(ROOT/name,arcname=name)
    tar.add(PRIV/'credentials.json',arcname='access/credentials.json')
   key=(PRIV/'backup-key.bin').read_bytes();encrypt(plain,out,key)
  finally:
   if scaled:
    run(K+['scale','deployment/adguard-home','-n','dns-filter','--replicas=1']);run(K+['rollout','status','deployment/adguard-home','-n','dns-filter','--timeout=180s'])
   if enabled:run(['/usr/local/sbin/homelab-adguard-dns','enable'])
  try:
   verified=folder/('verified-'+stamp+'.tar.gz');decrypt(out,verified,key);assert sha(plain)==sha(verified)
   result={'encrypted':True,'algorithm':'AES-256-GCM','integrity_verified':True,'nas':offsite(out)}
   if test:result.update(restore_check(verified))
   (PRIV/'backup-latest.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
   # Keep at most eleven encrypted local recovery copies. Offsite retains daily+weekly sets.
   for p in sorted(folder.glob('adguard-*.agh'),reverse=True)[11:]:p.unlink()
  finally:
   plain.unlink(missing_ok=True)
   if 'verified' in locals():verified.unlink(missing_ok=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--restore-test',action='store_true');a=p.parse_args();backup(a.restore_test)
