#!/usr/bin/env python3
"""Interactive root helper on pi5. Secrets go only to Kubernetes through stdin."""
import argparse,base64,getpass,json,os,pathlib,sqlite3,subprocess,sys,time
K=['kubectl','--kubeconfig=/etc/kubernetes/admin.conf'];R=pathlib.Path('/home/alvarense/gitops-homelab')
def run(a,data=None,t=60):
 p=subprocess.run(a,input=data,text=True,capture_output=True,timeout=t)
 if p.returncode:raise RuntimeError('Command failed; credentials and private output suppressed')
 return p.stdout
def git(*args):return run(['runuser','-u','alvarense','--','git','-C',str(R),*args])
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--activate',action='store_true',help='Retry using the Secret already supplied; no credential prompt');a=p.parse_args()
 if os.geteuid()!=0:raise RuntimeError('Run with sudo on pi5')
 print('Target: vpn.bearsfamily.es only. Use your DonDNS Key, never the account password.')
 if not a.activate:
  if not sys.stdin.isatty():raise RuntimeError('Interactive terminal required')
  username=input('DonDominio username: ').strip();key=getpass.getpass('DonDNS Key (hidden): ').strip()
  if not username or not key or any(c in username+key for c in '\r\n'):raise RuntimeError('Invalid credentials')
  secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':'dondns-credentials','namespace':'wireguard'},'type':'Opaque','data':{'username':base64.b64encode(username.encode()).decode(),'apikey':base64.b64encode(key.encode()).decode()}}
  run(K+['apply','--server-side','--field-manager=dondns-operator','-f','-'],json.dumps(secret));key=None;secret=None
  print('Credentials stored only in Kubernetes Secret wireguard/dondns-credentials.')
 cron=json.loads(run(K+['get','cronjob','dondns','-n','wireguard','-o','json']))
 jobname='dondns-activate-'+str(int(time.time()))
 job={'apiVersion':'batch/v1','kind':'Job','metadata':{'name':jobname,'namespace':'wireguard'},'spec':cron['spec']['jobTemplate']['spec']}
 job['spec']['template']['spec']['containers'][0].setdefault('env',[]).append({'name':'DONDNS_FORCE_UPDATE','value':'true'})
 run(K+['create','-f','-'],json.dumps(job));deadline=time.monotonic()+145
 while time.monotonic()<deadline:
  j=json.loads(run(K+['get','job',jobname,'-n','wireguard','-o','json']))
  if j.get('status',{}).get('succeeded'):break
  if any(v.get('type')=='Failed' and v.get('status')=='True' for v in j.get('status',{}).get('conditions',[])):break
  time.sleep(3)
 else:raise RuntimeError('Verification timed out. CronJob remains paused; inspect the Job.')
 if not j.get('status',{}).get('succeeded'):
  # Updater output contains only fixed error codes, hostname and public IP.
  logs=run(K+['logs','job/'+jobname,'-n','wireguard','--tail=5'])
  for l in logs.splitlines():
   try:msg=json.loads(l)
   except ValueError:continue
   if msg.get('status')=='error':print('DonDNS verification: '+msg.get('reason','failed'))
  raise RuntimeError('Not activated. Review active domain, A record vpn, and DonDNS Key. Retry this command with --activate; no need to paste the key again.')
 # Persist the activation in Git, avoiding an operational flag that Argo would undo.
 if git('status','--porcelain').strip():raise RuntimeError('GitOps has pending edits; leave paused and ask the operator to complete activation.')
 rel='platform/wireguard/31-dondns-cronjob.yaml';file=R/rel;manifest=json.loads(file.read_text());manifest['spec']['suspend']=False;file.write_text(json.dumps(manifest,indent=2)+'\n')
 git('diff','--check');git('add',rel)
 diff=git('diff','--cached','--name-only').strip()
 if diff:git('commit','-m','Activar DonDNS validado para vpn.bearsfamily.es')
 git('push','origin','main')
 sha=git('rev-parse','HEAD').strip()
 patch={'operation':{'sync':{'revision':sha,'prune':False,'syncOptions':['ServerSideApply=true','DisableClientSideApplyMigration=true']}}}
 app=json.loads(run(K+['get','app','homelab-wireguard','-n','argocd','-o','json']))
 if app.get('operation'):raise RuntimeError('An Argo operation is running; sync the new commit manually when finished.')
 run(K+['annotate','app','homelab-wireguard','-n','argocd','argocd.argoproj.io/refresh=hard','--overwrite'])
 run(K+['patch','app','homelab-wireguard','-n','argocd','--type=merge','-p',json.dumps(patch)])
 # Host is metadata, not a key; a single atomic SQLite update preserves all peers.
 db=sqlite3.connect('/var/lib/homelab-apps/wireguard/wg-easy.db',timeout=10)
 with db:
  assert db.execute('select count(*) from user_configs_table where id=?',('wg0',)).fetchone()[0]==1
  db.execute('update user_configs_table set host=? where id=?',('vpn.bearsfamily.es','wg0'))
 db.close()
 print('DonDNS verified; GitOps activation requested. New client profiles use vpn.bearsfamily.es:51820.')
 print('Re-download existing client profiles or edit only their Endpoint; preserve their keys.')
 print('Check: sudo kubectl --kubeconfig=/etc/kubernetes/admin.conf -n wireguard get cronjob dondns')
if __name__=='__main__':
 try:main()
 except Exception as e:
  # This helper never puts credentials in command arguments or printed errors.
  print(str(e),file=sys.stderr);sys.exit(1)
