#!/usr/bin/env python3
"""Validate ACME output without exporting private keys or account data."""
import argparse,json,pathlib,subprocess,tempfile
K=['kubectl','--kubeconfig=/etc/kubernetes/admin.conf'];ROOT=pathlib.Path('/var/lib/homelab-acme-operations')
def run(args,stdin=None,t=30):
 p=subprocess.run(args,input=stdin,capture_output=True,text=True,timeout=t)
 if p.returncode:raise RuntimeError('Certificate validation command failed; inspect privately on pi5')
 return p.stdout
def validate(phase):
 state=json.loads((ROOT/(phase+'-active.json')).read_text());result=json.loads((ROOT/state['runid']/'result.json').read_text());assert result['exit_code']==0,'ACME phase not successful'
 pods=json.loads(run(K+['get','pods','-n','certificates','-l','app=certbot-manual','-o','json']))['items'];pod=next(p['metadata']['name'] for p in pods if all(x.get('ready') for x in p['status'].get('containerStatuses',[])))
 name='bearsfamily-es-test' if phase=='staging' else 'bearsfamily.es';base='/acme/'+phase+'/config/live/'+name
 script=r'''
import pathlib,json,hashlib,datetime,stat
from cryptography import x509
from cryptography.hazmat.primitives import serialization,hashes
p=pathlib.Path(BASE)
cert=x509.load_pem_x509_certificate((p/'cert.pem').read_bytes());key=serialization.load_pem_private_key((p/'privkey.pem').read_bytes(),password=None)
names=cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value.get_values_for_type(x509.DNSName)
assert set(names)=={'bearsfamily.es','*.bearsfamily.es'}
def pub(k):return k.public_bytes(serialization.Encoding.DER,serialization.PublicFormat.SubjectPublicKeyInfo)
assert pub(cert.public_key())==pub(key.public_key())
now=datetime.datetime.now(datetime.timezone.utc);assert cert.not_valid_before_utc<=now<cert.not_valid_after_utc
assert (p/'privkey.pem').stat().st_mode&0o077==0
print(json.dumps({'dns_names':names,'issuer':cert.issuer.rfc4514_string(),'not_before':cert.not_valid_before_utc.isoformat(),'not_after':cert.not_valid_after_utc.isoformat(),'fingerprint_sha256':cert.fingerprint(hashes.SHA256()).hex(),'key_matches':True,'private_key_permissions_restricted':True}))
'''.replace('BASE',repr(base))
 info=json.loads(run(K+['exec','-i','-n','certificates',pod,'--','python','-'],script))
 with tempfile.TemporaryDirectory(prefix='homelab-acme-public-') as temp:
  for file in ['cert.pem','chain.pem','fullchain.pem']:
   body=run(K+['exec','-n','certificates',pod,'--','cat',base+'/'+file]);(pathlib.Path(temp)/file).write_text(body)
  args=['openssl','verify','-CApath','/etc/ssl/certs','-untrusted',temp+'/chain.pem','-verify_hostname','grafana.bearsfamily.es',temp+'/cert.pem']
  test=subprocess.run(args,capture_output=True,text=True,timeout=20);info['system_ca_chain_and_hostname_valid']=test.returncode==0
  if phase=='production':assert test.returncode==0,'Production chain/hostname verification failed'
  if phase=='staging':assert test.returncode!=0,'Staging unexpectedly trusted: inspect before proceeding'
 info['phase']=phase;info['staging_not_for_browser']=phase=='staging'
 public=ROOT/'public';public.mkdir(mode=0o700,exist_ok=True);(public/(phase+'-certificate.json')).write_text(json.dumps(info,indent=2)+'\n')
 print(json.dumps(info,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('phase',choices=['staging','production']);validate(p.parse_args().phase)
