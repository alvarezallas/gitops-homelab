#!/usr/bin/env python3
"""Run Certbot renewal in the cluster; logs stay on the private ACME volume."""
import os,pathlib,subprocess,uuid,fcntl,json,sys,datetime
os.umask(0o077);base=pathlib.Path('/acme/production');dry='--dry-run' in sys.argv
with (base/'renewal-job.lock').open('w') as lock:
 fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
 runid=uuid.uuid4().hex;env=dict(os.environ,ACME_RUN_ID=runid)
 logdir=base/'automation';logdir.mkdir(mode=0o700,exist_ok=True)
 args=['certbot','renew','--non-interactive','--cert-name','bearsfamily.es','--config-dir',str(base/'config'),'--work-dir',str(base/'work'),'--logs-dir',str(base/'logs'),'--manual-auth-hook','/opt/renew/auth.sh','--manual-cleanup-hook','/opt/renew/cleanup.sh','--no-random-sleep-on-renew']
 if dry:args+=['--dry-run']
 with (logdir/(runid+'.log')).open('w') as log:
  try:code=subprocess.run(args,env=env,stdout=log,stderr=log,timeout=4500).returncode
  except subprocess.TimeoutExpired:code=124
 report={'runid':runid,'dry_run':dry,'exit_code':code,'finished_at':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 (logdir/'last-result.json').write_text(json.dumps(report)+'\n')
 print(json.dumps(report));sys.exit(code)
