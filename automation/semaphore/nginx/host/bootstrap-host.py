#!/usr/bin/python3
# Run only after authorization; creates host privileges and a private Kubernetes Secret.

import json,subprocess,pathlib,os,tempfile,base64,importlib.machinery,importlib.util
P=pathlib.Path
public={p.name:p.read_text() for p in pathlib.Path(__file__).parent.iterdir() if p.is_file() and p.name!='bootstrap-host.py'}
K=['kubectl','--kubeconfig=/etc/kubernetes/admin.conf']
R='/home/alvarense/nginx-sites-available'
def run(args,stdin=None,timeout=60,ok=True):
 p=subprocess.run(args,input=stdin,capture_output=True,text=True,timeout=timeout)
 if ok and p.returncode:raise RuntimeError('Failed '+args[0]+' code='+str(p.returncode)+' '+p.stderr[-500:])
 return p
def git(*args):return run(['runuser','-u','alvarense','--','git','-c','core.hooksPath=/dev/null','-C',R,*args]).stdout.strip()
def write(path,text,mode=0o644):
 p=P(path);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text);p.chmod(mode)
assert not git('status','--porcelain')
git('pull','--ff-only')
assert not P('/var/lib/homelab-nginx/current').exists(),'Already migrated; inspect before retry'
initial=git('rev-parse','HEAD')
oldlinks={x:os.readlink(x) if P(x).is_symlink() else None for x in ['/etc/nginx/sites-available','/etc/nginx/sites-enabled']}
assert oldlinks['/etc/nginx/sites-available']==R
assert oldlinks['/etc/nginx/sites-enabled'] is None
assert set(p.name for p in P('/etc/nginx/sites-enabled').iterdir())=={'00-maps.conf','default.conf','argocd.conf','grafana.conf','prometheus.conf','qbittorrent.conf','pgadmin.conf','semaphore.conf'}
write('/usr/local/sbin/homelab-nginx-deploy',public['homelab-nginx-deploy.py'],0o755)
write('/usr/local/libexec/homelab-nginx-ssh',public['homelab-nginx-ssh'],0o755)
write('/etc/systemd/system/homelab-nginx-recover.service',public['homelab-nginx-recover.service'])
write('/etc/logrotate.d/homelab-nginx-deploy','/var/log/homelab-nginx-deploy.jsonl {\n weekly\n rotate 12\n compress\n missingok\n notifempty\n create 0640 root adm\n}\n')
run(['python3','-m','py_compile','/usr/local/sbin/homelab-nginx-deploy'])
loader=importlib.machinery.SourceFileLoader('nginx_deploy','/usr/local/sbin/homelab-nginx-deploy');spec=importlib.util.spec_from_loader(loader.name,loader);m=importlib.util.module_from_spec(spec);loader.exec_module(m)
m.BASE.mkdir(exist_ok=True,mode=0o755);m.RELEASES.mkdir(exist_ok=True,mode=0o755)
# Prepare a stable content pointer before changing the portal root in the source checkout.
# Keep the old immutable copy as migration evidence, never mark its pre-migration root as final.
import tarfile,io
archive=subprocess.run(['runuser','-u','alvarense','--','git','-C',R,'archive','--format=tar',initial],capture_output=True,check=True).stdout
stage=m.BASE/'migration-source';stage.mkdir(mode=0o755)
with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
 for member in tf.getmembers():
  assert member.isfile() or member.isdir()
  assert '..' not in P(member.name).parts and not member.name.startswith('/')
  tf.extract(member,stage,filter='data')
m.CURRENT.symlink_to(stage)
default=P(R)/'default.conf';text=default.read_text();assert 'root '+R+';' in text
default.write_text(text.replace('root '+R+';','root /var/lib/homelab-nginx/current;'))
run(['chown','alvarense:alvarense',str(default)])
git('diff','--check');git('add','default.conf');git('commit','-m','Servir el portal desde releases atomicas para Semaphore');git('push','origin','main')
sha=git('rev-parse','HEAD')
candidate=m.archive(sha)
# Validate before replacing host links. Backup original sites-enabled as a dated directory.
backup=P('/etc/nginx/sites-enabled.before-semaphore-20261030');assert not backup.exists()
try:
 m.switch(sha)
 P('/etc/nginx/sites-enabled').rename(backup)
 P('/etc/nginx/sites-enabled').symlink_to(m.CURRENT/'sites-enabled')
 tmp=P('/etc/nginx/sites-available.next');tmp.symlink_to(m.CURRENT);os.replace(tmp,'/etc/nginx/sites-available')
 m.reload_nginx();checks=m.probes(sha)
 m.write_json(m.STATE,{'applied':sha,'previous':None,'rejected':None,'migration_from':initial})
 m.audit('migration-complete',applied=sha,previous=initial,https=checks,reload=True)
except BaseException:
 if P('/etc/nginx/sites-enabled').is_symlink():P('/etc/nginx/sites-enabled').unlink()
 if backup.exists():backup.rename('/etc/nginx/sites-enabled')
 tmp=P('/etc/nginx/sites-available.restore');tmp.symlink_to(R);os.replace(tmp,'/etc/nginx/sites-available')
 m.reload_nginx()
 raise
if run(['getent','passwd','semaphore-nginx'],ok=False).returncode:
 run(['useradd','--system','--create-home','--home-dir','/var/lib/semaphore-nginx','--shell','/bin/sh','semaphore-nginx'])
write('/etc/sudoers.d/semaphore-nginx','semaphore-nginx ALL=(root) NOPASSWD: /usr/bin/timeout --signal=TERM --kill-after=10s 170s /usr/local/sbin/homelab-nginx-deploy\n',0o440)
run(['visudo','-cf','/etc/sudoers.d/semaphore-nginx'])
write('/etc/ssh/sshd_config.d/40-semaphore-nginx.conf','Match User semaphore-nginx\n    AuthorizedKeysFile /etc/ssh/authorized_keys/%u\n    PasswordAuthentication no\n    KbdInteractiveAuthentication no\n    AuthenticationMethods publickey\n    AllowTcpForwarding no\n    AllowAgentForwarding no\n    PermitTTY no\n    X11Forwarding no\nMatch all\n')
existing=run(K+['-n','semaphore','get','secret','semaphore-nginx-ssh','-o','json'],ok=False)
assert existing.returncode,'Dedicated SSH secret exists; do not regenerate identity'
with tempfile.TemporaryDirectory(prefix='semaphore-nginx-key-',dir='/run') as td:
 key=P(td)/'id_ed25519'
 run(['ssh-keygen','-q','-t','ed25519','-N','','-C','semaphore-nginx-deploy','-f',str(key)])
 pub=key.with_suffix('.pub').read_text().strip()
 secret={'apiVersion':'v1','kind':'Secret','metadata':{'name':'semaphore-nginx-ssh','namespace':'semaphore'},'type':'Opaque','data':{'id_ed25519':base64.b64encode(key.read_bytes()).decode()}}
 # Never include kubectl stderr/stdin in an exception for private operations.
 p=subprocess.run(K+['apply','-f','-'],input=json.dumps(secret),text=True,capture_output=True,timeout=30)
 assert p.returncode==0,'Private Secret bootstrap failed (output suppressed)'
 write('/etc/ssh/authorized_keys/semaphore-nginx','restrict,from="10.244.0.0/16,192.168.1.163",command="/usr/local/libexec/homelab-nginx-ssh" '+pub+'\n',0o644)
 run(['ssh-keygen','-lf',str(key)+'.pub'])
run(['sshd','-t']);run(['systemctl','reload','ssh']);run(['systemctl','daemon-reload']);run(['systemctl','enable','homelab-nginx-recover.service'])
hostpub=P('/etc/ssh/ssh_host_ed25519_key.pub').read_text().split()
known='192.168.1.163 '+hostpub[0]+' '+hostpub[1]+'\n'
print(json.dumps({'migration_commit':sha,'previous_commit':initial,'https':checks,'known_hosts':known,'secret':'semaphore/semaphore-nginx-ssh','ssh_user':'semaphore-nginx','sites_available':str(P('/etc/nginx/sites-available').resolve()),'sites_enabled':str(P('/etc/nginx/sites-enabled').resolve())}))
