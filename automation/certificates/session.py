#!/usr/bin/env python3
"""Host operator for bounded manual-DNS sessions; private config/logs stay on pi5."""
import argparse,json,os,pathlib,subprocess,sys,time,uuid
K=['kubectl','--kubeconfig=/etc/kubernetes/admin.conf'];ROOT=pathlib.Path('/var/lib/homelab-acme-operations')
def getpod():
 d=json.loads(subprocess.check_output(K+['get','pods','-n','certificates','-l','app=certbot-manual','-o','json']))
 ready=[p for p in d['items'] if p.get('status',{}).get('containerStatuses') and all(x.get('ready') for x in p['status']['containerStatuses'])]
 if len(ready)!=1:raise RuntimeError('Expected one ready ACME client')
 return ready[0]['metadata']['name']
def start(phase,config):
 os.umask(0o077);ROOT.mkdir(mode=0o700,parents=True,exist_ok=True)
 state=ROOT/(phase+'-active.json')
 if state.exists():
  old=json.loads(state.read_text());result=ROOT/old['runid']/'result.json'
  if not result.exists():raise RuntimeError('A session is already pending; inspect it instead of duplicating requests')
  if json.loads(result.read_text()).get('exit_code')==0:raise RuntimeError('Phase already succeeded; validate existing certificate instead of reissuing')
 runid=uuid.uuid4().hex;folder=ROOT/runid;folder.mkdir(mode=0o700)
 (folder/'config.json').write_text(json.dumps({'phase':phase,'email':config.get('email'),'pod':getpod()})+'\n')
 log=(folder/'private-session.log').open('wb')
 process=subprocess.Popen([sys.executable,__file__,'supervise',phase,runid],stdout=log,stderr=log,start_new_session=True,close_fds=True);log.close()
 state.write_text(json.dumps({'phase':phase,'runid':runid,'pid':process.pid})+'\n');state.chmod(0o600)
 print(json.dumps({'phase':phase,'runid':runid,'started':True,'waits_for_manual_txt':True}))
def supervise(phase,runid):
 folder=ROOT/runid;cfg=json.loads((folder/'config.json').read_text());base='/acme/'+phase
 args=K+['exec','-n','certificates',cfg['pod'],'--','env','ACME_PHASE='+phase,'ACME_RUN_ID='+runid,'certbot','certonly','--non-interactive','--agree-tos','--manual','--manual-auth-hook','/opt/acme/auth.sh','--preferred-challenges','dns','--server',('https://acme-staging-v02.api.letsencrypt.org/directory' if phase=='staging' else 'https://acme-v02.api.letsencrypt.org/directory'),'--config-dir',base+'/config','--work-dir',base+'/work','--logs-dir',base+'/logs','--cert-name',('bearsfamily-es-test' if phase=='staging' else 'bearsfamily.es'),'-d','bearsfamily.es','-d','*.bearsfamily.es']
 if cfg.get('email'):args+=['--email',cfg['email']]
 else:args+=['--register-unsafely-without-email']
 try:code=subprocess.run(args,timeout=3720).returncode
 except subprocess.TimeoutExpired:code=124
 (folder/'result.json').write_text(json.dumps({'phase':phase,'runid':runid,'exit_code':code})+'\n')
def status(phase):
 state=ROOT/(phase+'-active.json')
 if not state.exists():print(json.dumps({'phase':phase,'status':'not_started'}));return
 s=json.loads(state.read_text());folder=ROOT/s['runid'];cfg=json.loads((folder/'config.json').read_text());report={'phase':phase,'runid':s['runid']}
 result=folder/'result.json'
 if result.exists():report.update(json.loads(result.read_text()));report['status']='succeeded' if report['exit_code']==0 else 'failed'
 for name in ['requests.json','status.json']:
  p=subprocess.run(K+['exec','-n','certificates',cfg['pod'],'--','cat','/acme/'+phase+'/runs/'+s['runid']+'/'+name],capture_output=True,text=True,timeout=20)
  if p.returncode==0:report['requests' if name=='requests.json' else 'dns_status']=json.loads(p.stdout)
 print(json.dumps(report,indent=2))
def main():
 assert os.geteuid()==0,'Run as root on pi5'
 parser=argparse.ArgumentParser();parser.add_argument('action',choices=['start','status','supervise']);parser.add_argument('phase',choices=['staging','production']);parser.add_argument('runid',nargs='?');args=parser.parse_args()
 if args.action=='start':start(args.phase,json.load(sys.stdin))
 elif args.action=='supervise':supervise(args.phase,args.runid)
 else:status(args.phase)
if __name__=='__main__':main()
