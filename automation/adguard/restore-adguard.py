#!/usr/bin/env python3
"""Inspect by default; explicit --execute restores only this application's state."""
import pathlib,argparse,tempfile,tarfile,json,os,subprocess,shutil,datetime,sys
sys.path.insert(0,'/usr/local/lib/homelab-adguard')
from backup_adguard import decrypt
ROOT=pathlib.Path('/var/lib/homelab-apps/adguard-home');PRIV=ROOT/'private';K=['kubectl','--kubeconfig=/etc/kubernetes/admin.conf']
def run(a):return subprocess.check_output(a,text=True,stderr=subprocess.STDOUT,timeout=180)
def restore(path,execute=False):
 import yaml
 assert os.geteuid()==0
 os.umask(0o077)
 path=pathlib.Path(path).resolve();assert path.is_file() and path.suffix=='.agh' and path.is_relative_to(PRIV/'backups'),'Use a local encrypted backup under the private backup directory'
 with tempfile.TemporaryDirectory(dir=PRIV,prefix='restore-production-') as tmp:
  temp=pathlib.Path(tmp);plain=temp/'data.tar.gz';decrypt(path,plain,(PRIV/'backup-key.bin').read_bytes())
  unpack=temp/'unpack';unpack.mkdir()
  with tarfile.open(plain) as tar:tar.extractall(unpack,filter='data')
  assert {p.name for p in unpack.iterdir()}=={'conf','work','access'}
  cfg=yaml.safe_load((unpack/'conf/AdGuardHome.yaml').read_text());assert cfg['users'] and cfg['dns']['port']==5353
  assert cfg['http']['address']=='0.0.0.0:3000' and not cfg.get('dhcp',{}).get('enabled')
  result={'backup':path.name,'integrity_verified':True,'schema_version':cfg['schema_version'],'execute':execute}
  if not execute:print(json.dumps(result));return
  # Preserve the present state first. No existing app data is deleted.
  saved=PRIV/('before-restore-'+datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%SZ'));saved.mkdir(mode=0o700)
  run(['/usr/local/sbin/homelab-adguard-dns','bypass'])
  run(K+['scale','deployment/adguard-home','-n','dns-filter','--replicas=0']);run(K+['wait','-n','dns-filter','--for=delete','pod','-l','app=adguard-home','--timeout=90s'])
  moved=[]
  try:
   for name in ['conf','work']:
    (ROOT/name).rename(saved/name);moved.append(name);shutil.copytree(unpack/name,ROOT/name)
    for p in [ROOT/name,*(ROOT/name).rglob('*')]:os.chown(p,10001,10001)
   shutil.copyfile(PRIV/'credentials.json',saved/'credentials.json');shutil.copyfile(unpack/'access/credentials.json',PRIV/'credentials.json');(PRIV/'credentials.json').chmod(0o600)
   run(K+['scale','deployment/adguard-home','-n','dns-filter','--replicas=1']);run(K+['rollout','status','deployment/adguard-home','-n','dns-filter','--timeout=180s'])
   run(['/usr/local/sbin/homelab-adguard-dns','enable'])
   result.update(restored=True,previous_state=str(saved));print(json.dumps(result))
  except BaseException:
   run(K+['scale','deployment/adguard-home','-n','dns-filter','--replicas=0']);run(K+['wait','-n','dns-filter','--for=delete','pod','-l','app=adguard-home','--timeout=90s'])
   for name in moved:
    failed=saved/('failed-'+name)
    if (ROOT/name).exists():(ROOT/name).rename(failed)
    (saved/name).rename(ROOT/name)
   if (saved/'credentials.json').exists():shutil.copyfile(saved/'credentials.json',PRIV/'credentials.json')
   run(K+['scale','deployment/adguard-home','-n','dns-filter','--replicas=1']);run(K+['rollout','status','deployment/adguard-home','-n','dns-filter','--timeout=180s']);run(['/usr/local/sbin/homelab-adguard-dns','enable']);raise
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('backup');p.add_argument('--execute',action='store_true');a=p.parse_args();restore(a.backup,a.execute)
