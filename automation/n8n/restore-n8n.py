#!/usr/bin/env python3
"""Inspect by default. Decrypt only to private storage; never overwrite production."""
import argparse,pathlib,json,hashlib,tarfile,tempfile,os,importlib.machinery,importlib.util
p=argparse.ArgumentParser();p.add_argument('backup');p.add_argument('--extract-to');p.add_argument('--verify-databases',action='store_true');a=p.parse_args()
assert os.geteuid()==0;os.umask(0o077)
loader=importlib.machinery.SourceFileLoader('n8n_backup','/usr/local/sbin/backup-n8n');spec=importlib.util.spec_from_loader(loader.name,loader);b=importlib.util.module_from_spec(spec);loader.exec_module(b)
cfg=json.loads((b.P/'config.json').read_text());key=hashlib.sha256(cfg['backup_key'].encode()).digest();src=pathlib.Path(a.backup).resolve();assert src.is_file()
with tempfile.TemporaryDirectory(dir=b.P,prefix='restore-inspect-') as t:
 plain=pathlib.Path(t)/'backup.tar.gz';b.crypt(src,plain,key,True)
 with tarfile.open(plain) as tar:
  names=set(tar.getnames());assert {'n8n.dump','automation_state.dump','private/config.json','private/k8s-secret.json'}<=names
  result={'authenticated_decryption':True,'files':len(names),'production_unchanged':True}
  if a.extract_to:
   dest=pathlib.Path(a.extract_to).resolve();assert dest.parent==b.P and dest.name.startswith('recovery-') and not dest.exists(),'Use a new private/recovery-* directory'
   dest.mkdir(mode=0o700);tar.extractall(dest,filter='data')
   secret=json.loads((dest/'private/k8s-secret.json').read_text());secret={k:secret[k] for k in ['apiVersion','kind','type','data']};secret['metadata']={'name':'n8n-config','namespace':'n8n'};(dest/'private/k8s-secret.json').write_text(json.dumps(secret))
   private=json.loads((dest/'private/config.json').read_text());sql=[]
   for role,keyname in [('n8n_app','db_password'),('automation_state_app','state_password')]:
    password=private[keyname].replace("'","''");sql.append('CREATE ROLE '+role+" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD '"+password+"';")
   (dest/'private/roles-new-cluster.sql').write_text('\n'.join(sql)+'\n');result['extracted_to']=str(dest)
 if a.verify_databases:result.update(b.restore_test(plain))
 print(json.dumps(result))
