#!/usr/bin/env python3
"""DNS-01: create dedicated TXT records, remove only records created by this run."""
import json,os,pathlib,re,sys,time,urllib.request,urllib.parse
from dnscheck import txt_records,write
DOMAIN='bearsfamily.es';OWNER='_acme-challenge.'+DOMAIN
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None
class Provider:
 def __init__(self,cfg):self.cfg=cfg
 def call(self,action,**params):
  assert action in ['tool/hello','service/dnslist','service/dnscreate','service/dnsdelete']
  body={'apiuser':self.cfg['apiuser'],'apipasswd':self.cfg['apipasswd'],'serviceName':self.cfg.get('serviceName',DOMAIN),**params}
  req=urllib.request.Request('https://simple-api.dondominio.net/'+action+'/',data=urllib.parse.urlencode(body).encode(),headers={'Content-Type':'application/x-www-form-urlencoded'})
  try:
   with urllib.request.build_opener(NoRedirect).open(req,timeout=30) as f:d=json.load(f)
  except Exception:raise RuntimeError('DonDominio HTTPS/API request failed; credentials not logged') from None
  if d.get('success') is not True:raise RuntimeError('DonDominio API error code '+str(d.get('errorCode','unknown')))
  return d.get('responseData',{})
 def records(self):
  d=self.call('service/dnslist',pageLength=1000,page=1)
  if int(d.get('queryInfo',{}).get('total',0))>1000:raise RuntimeError('DNS zone too large for this narrowly scoped hook')
  return d.get('dns',[])
 def create(self,value):
  d=self.call('service/dnscreate',name=OWNER,type='TXT',value=value,ttl=60)
  matches=[r for r in d.get('dns',[]) if r.get('name','').rstrip('.')==OWNER and r.get('type')=='TXT' and r.get('value')==value]
  if len(matches)!=1:raise RuntimeError('Unexpected create response; inspect ACME record privately')
  return str(matches[0]['entityID'])
 def remove(self,item):
  for r in self.records():
   if str(r.get('entityID'))==item['id']:
    assert r.get('name','').rstrip('.')==OWNER and r.get('type')=='TXT' and r.get('value')==item['value'],'Refusing to delete an unrelated record'
    self.call('service/dnsdelete',entityID=item['id']);return
def main():
 os.umask(0o077);action=sys.argv[1];assert action in ['auth','cleanup']
 domain=os.environ.get('CERTBOT_DOMAIN') or os.environ.get('CERTBOT_IDENTIFIER');assert domain and domain.removeprefix('*.')==DOMAIN
 value=os.environ['CERTBOT_VALIDATION'];assert re.fullmatch(r'[A-Za-z0-9_-]{20,128}',value)
 runid=os.environ['ACME_RUN_ID'];assert re.fullmatch(r'[a-zA-Z0-9-]{1,80}',runid)
 folder=pathlib.Path('/acme/production/dns-api-runs')/runid;folder.mkdir(parents=True,exist_ok=True,mode=0o700);path=folder/'owned.json'
 items=json.loads(path.read_text()) if path.exists() else []
 provider=Provider(json.loads(pathlib.Path('/run/dondominio/credentials.json').read_text()))
 if action=='cleanup':
  for item in items:
   if item['value']==value:provider.remove(item)
  return
 if not any(i['value']==value for i in items):
  items.append({'value':value,'id':provider.create(value)});write(path,items)
 if int(os.environ.get('CERTBOT_REMAINING_CHALLENGES','0')):return
 expected={i['value'] for i in items};deadline=time.monotonic()+3600
 while time.monotonic()<deadline:
  if all(expected<=txt_records(OWNER,s) for s in ['1.1.1.1','8.8.8.8']):return
  time.sleep(15)
 raise RuntimeError('Timed out waiting for public TXT propagation')
if __name__=='__main__':
 try:main()
 except Exception as exc:
  print('DNS hook failed: '+str(exc)[:180],file=sys.stderr);sys.exit(1)
