#!/usr/bin/env python3
"""Prerequisites only on pi5; never changes disks, routers or existing state."""
import argparse,os,pathlib,socket,subprocess
p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');a=p.parse_args()
if not a.execute:raise SystemExit('Review first. Run as root with --execute on pi5.')
assert os.geteuid()==0 and socket.gethostname()=='pi5','Only root on pi5'
mods=['wireguard','nf_tables','nft_chain_nat','nft_reject_ipv6']
for m in mods:subprocess.run(['modprobe',m],check=True)
pathlib.Path('/etc/modules-load.d/homelab-wireguard.conf').write_text('\n'.join(mods)+'\n')
state=pathlib.Path('/var/lib/homelab-apps/wireguard')
if not state.exists():state.mkdir(parents=True,mode=0o700)
assert state.is_dir() and not state.is_symlink(),'Unexpected storage path'
assert state.stat().st_uid==0 and state.stat().st_mode & 0o077 ==0,'Existing state permissions require review'
print('Host prerequisites ready; private state preserved. No deployment or credentials changed.')
