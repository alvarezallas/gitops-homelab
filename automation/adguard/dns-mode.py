#!/usr/bin/env python3
"""Fixed-target, reversible dnsmasq upstream switch for the installed filter."""
import pathlib,subprocess,os,json,urllib.request,base64,argparse,tempfile
ROOT=pathlib.Path('/var/lib/homelab-apps/adguard-home');P=pathlib.Path('/etc/dnsmasq.d/homelab.conf');BACK=ROOT/'private/dnsmasq-before-cutover.conf'
def run(a):return subprocess.check_output(a,text=True,stderr=subprocess.STDOUT,timeout=15)
def answers(host,qtype='A',port=53):
 return sorted(run(['dig','@192.168.1.163','-p',str(port),host,qtype,'+short','+time=3','+tries=1']).strip().splitlines())
def replace(data):
 st=P.stat()
 with tempfile.NamedTemporaryFile(dir=P.parent,delete=False) as f:
  tmp=pathlib.Path(f.name);f.write(data);os.fchmod(f.fileno(),st.st_mode&0o777);os.fchown(f.fileno(),st.st_uid,st.st_gid)
 os.replace(tmp,P)
def apply(mode):
 assert os.geteuid()==0 and P.resolve()==P
 current=P.read_bytes();text=current.decode()
 if mode=='status':return {'mode':'enabled' if 'server=192.168.1.163#30553' in text.splitlines() else 'bypass'}
 old='server=80.58.61.250';new='server=192.168.1.163#30553'
 if mode=='enable':
  d=json.loads((ROOT/'private/credentials.json').read_text());h={'Authorization':'Basic '+base64.b64encode((d['username']+':'+d['password']).encode()).decode()}
  with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:30094/control/status',headers=h),timeout=10) as f:assert json.load(f)['protection_enabled']
  assert '0.0.0.0' in answers('pagead2.googlesyndication.com',port=30553)
  if new in text.splitlines():return {'mode':'enabled','changed':False}
  assert text.splitlines().count(old)==1
  # Reject other global upstreams in the active included .conf files.
  for p in P.parent.glob('*.conf'):
   for line in p.read_text().splitlines():
    if line.strip().startswith('server=') and not line.strip().startswith('server=/'):assert p==P and line.strip()==old,'Unexpected global upstream'
  if not BACK.exists():BACK.write_bytes(current);BACK.chmod(0o600)
  candidate=text.replace(old,new,1).encode()
 else:
  assert BACK.exists()
  # Preserve any subsequently added private records while restoring only the known upstream.
  if old in text.splitlines():return {'mode':'bypass','changed':False}
  assert text.splitlines().count(new)==1
  candidate=text.replace(new,old,1).encode()
 before={x:answers(x,'TXT' if x.startswith('_acme') else 'A') for x in ['bearsfamily.es','notas.bearsfamily.es','adguard.bearsfamily.es','vpn.bearsfamily.es','_acme-challenge.bearsfamily.es']}
 try:
  replace(candidate);run(['dnsmasq','--test','--conf-file='+str(P)]);run(['dnsmasq','--test']);run(['systemctl','restart','dnsmasq'])
  assert answers('example.org')
  for host,value in before.items():assert answers(host,'TXT' if host.startswith('_acme') else 'A')==value,(host,'DNS changed unexpectedly')
  if mode=='enable':assert '0.0.0.0' in answers('pagead2.googlesyndication.com')
 except BaseException:
  replace(current);run(['systemctl','restart','dnsmasq']);raise
 result={'mode':'enabled' if mode=='enable' else 'bypass','changed':True,'private_records_preserved':True,'vpn_and_acme_preserved':True}
 (ROOT/'private/dns-mode-latest.json').write_text(json.dumps(result));return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('mode',choices=['status','enable','bypass']);args=p.parse_args();print(json.dumps(apply(args.mode)))
