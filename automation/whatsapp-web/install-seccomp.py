#!/usr/bin/env python3
"""Install only the reviewed Playwright profile on pi5; never alter the host default."""
import pathlib,json,hashlib,os,socket,platform
assert os.geteuid()==0,'Run on pi5 with sudo'
assert socket.gethostname()=='pi5' and platform.machine()=='aarch64','Profile reviewed for pi5 ARM64'
source=pathlib.Path(__file__).with_name('whatsapp-playwright.json')
expected='c0876da1973903283594311df211b0b14dbfd7a8c20aa937ff0d2b5e18ed2452'
assert hashlib.sha256(source.read_bytes()).hexdigest()==expected,'Unexpected profile contents'
profile=json.loads(source.read_text());assert profile['defaultAction']=='SCMP_ACT_ERRNO'
assert profile['syscalls'][-1]=={'names':['clone','unshare','setns','chroot'],'action':'SCMP_ACT_ALLOW','args':[]}
target=pathlib.Path('/var/lib/kubelet/seccomp/whatsapp-playwright.json');target.parent.mkdir(parents=True,exist_ok=True)
if target.exists():assert target.read_bytes()==source.read_bytes(),'Existing profile differs; review before replacement'
else:
 tmp=target.with_suffix('.json.tmp');tmp.write_bytes(source.read_bytes());tmp.chmod(0o644);os.replace(tmp,target)
print('Reviewed Localhost profile ready. No default seccomp or AppArmor setting changed.')
