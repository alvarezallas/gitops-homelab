#!/usr/bin/python3
"""Private local snapshot with SQLite online backups and encryption verification."""
import pathlib,os,sqlite3,shutil,tempfile,tarfile,io,subprocess,secrets,time,json
assert os.geteuid()==0
root=pathlib.Path('/var/lib/homelab-apps/jellyfin/config');private=pathlib.Path('/root/.config/homelab-jellyfin');os.umask(0o077)
key=private/'backup-passphrase'
if not key.exists():key.write_text(secrets.token_urlsafe(48)+'\n');key.chmod(0o600)
dest=pathlib.Path('/var/backups/homelab-jellyfin');dest.mkdir(parents=True,exist_ok=True,mode=0o700)
db_count=0
with tempfile.TemporaryDirectory(prefix='jellyfin-snapshot-',dir='/root') as td:
 snap=pathlib.Path(td)/'config'
 shutil.copytree(root,snap,ignore=shutil.ignore_patterns('*.db','*.db-wal','*.db-shm','*.db-journal','log','logs'))
 for src in root.rglob('*.db'):
  target=snap/src.relative_to(root);target.parent.mkdir(parents=True,exist_ok=True)
  with sqlite3.connect(src.as_uri()+'?mode=ro',uri=True,timeout=30) as original,sqlite3.connect(target) as backup:
   original.backup(backup);assert backup.execute('PRAGMA quick_check').fetchone()[0]=='ok'
  db_count+=1
 assert db_count>0
 access=pathlib.Path(td)/'initial-access.json';shutil.copyfile(private/'initial-access.json',access)
 buf=io.BytesIO()
 with tarfile.open(fileobj=buf,mode='w:gz') as tf:tf.add(snap,arcname='config');tf.add(access,arcname='initial-access.json')
 filename=dest/('jellyfin-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'.tar.gz.gpg')
 args=['gpg','--batch','--yes','--pinentry-mode','loopback','--passphrase-file',str(key)]
 p=subprocess.run(args+['--symmetric','--cipher-algo','AES256','--output',str(filename)],input=buf.getvalue(),capture_output=True,timeout=90);assert p.returncode==0,'Private backup encryption failed'
 p=subprocess.run(args+['--decrypt',str(filename)],capture_output=True,timeout=90);assert p.returncode==0,'Private backup decryption verification failed'
 with tarfile.open(fileobj=io.BytesIO(p.stdout),mode='r:gz') as tf:
  names=tf.getnames();assert 'initial-access.json' in names and any(x.endswith('.db') for x in names)
result={'encrypted_backup':str(filename),'sqlite_online_backup_checked':db_count,'encryption':'GnuPG AES256','decryption_verified':True,'contains_private_credentials':True,'backup_remains_on_pi5':True,'scheduled_backup':False}
public=root.parent/'public';public.mkdir(exist_ok=True);(public/'backup.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
