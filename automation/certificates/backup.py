#!/usr/bin/env python3
"""One-time encrypted backup; keys never leave pi5 unencrypted."""
import pathlib,json,os,subprocess,secrets,tarfile,io,tempfile,time
ROOT=pathlib.Path('/var/lib/homelab-acme-operations');STATE=pathlib.Path('/var/lib/homelab-apps/certificates')
assert os.geteuid()==0
for phase in ['staging','production']:
 a=json.loads((ROOT/(phase+'-active.json')).read_text());r=json.loads((ROOT/a['runid']/'result.json').read_text());assert r['exit_code']==0
info=json.loads((ROOT/'public/production-certificate.json').read_text());assert info['key_matches'] and info['system_ca_chain_and_hostname_valid']
os.umask(0o077);keys=pathlib.Path('/root/.config/homelab-certificates');keys.mkdir(mode=0o700,exist_ok=True,parents=True);passfile=keys/'backup-passphrase'
if not passfile.exists():passfile.write_text(secrets.token_urlsafe(48)+'\n');passfile.chmod(0o600)
backup=pathlib.Path('/var/backups/homelab-certificates');backup.mkdir(mode=0o700,exist_ok=True,parents=True)
buf=io.BytesIO()
with tarfile.open(fileobj=buf,mode='w') as tar:tar.add(STATE,arcname='acme')
archive=backup/('acme-'+time.strftime('%Y%m%dT%H%M%SZ',time.gmtime())+'.tar.gpg')
def gpg(args,data=None):
 p=subprocess.run(['gpg','--batch','--yes','--pinentry-mode','loopback','--passphrase-file',str(passfile),*args],input=data,capture_output=True,timeout=90)
 if p.returncode:raise RuntimeError('Private backup encryption/decryption failed; inspect on pi5')
 return p.stdout
gpg(['--symmetric','--cipher-algo','AES256','--output',str(archive)],buf.getvalue());archive.chmod(0o600)
decoded=gpg(['--decrypt',str(archive)])
with tempfile.TemporaryDirectory(prefix='acme-restore-test-',dir='/root') as tmp:
 with tarfile.open(fileobj=io.BytesIO(decoded),mode='r') as tar:tar.extractall(tmp,filter='data')
 base=pathlib.Path(tmp)/'acme/production/config/live/bearsfamily.es'
 certpub=subprocess.check_output(['openssl','x509','-in',str(base/'cert.pem'),'-pubkey','-noout'])
 keypub=subprocess.check_output(['openssl','pkey','-in',str(base/'privkey.pem'),'-pubout'],stderr=subprocess.DEVNULL)
 assert certpub==keypub
 fp=subprocess.check_output(['openssl','x509','-in',str(base/'cert.pem'),'-noout','-fingerprint','-sha256'],text=True).strip().split('=',1)[1].replace(':','').lower()
 assert fp==info['fingerprint_sha256']
 for phase in ['staging','production']:
  accounts=pathlib.Path(tmp)/'acme'/phase/'config/accounts';assert list(accounts.rglob('private_key.json'))
result={'encrypted_backup':str(archive),'encryption':'GnuPG AES256','passphrase_location':str(passfile),'isolated_decryption_and_key_match_verified':True,'account_state_included':True,'nginx_unchanged':True,'automated_renewal_configured':False}
(ROOT/'public/backup-verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
