#!/usr/bin/env python3
import pathlib,json,urllib.request,base64,subprocess,time,datetime,fcntl,socket,struct,secrets,shutil
P=pathlib.Path('/var/lib/homelab-apps/adguard-home/private')
def query(host,port=53,tcp=False):
 ident=secrets.randbits(16);q=struct.pack('!6H',ident,256,1,0,0,0)+b''.join(bytes([len(x)])+x.encode() for x in host.split('.'))+b'\0'+struct.pack('!HH',1,1)
 with socket.socket(socket.AF_INET,socket.SOCK_STREAM if tcp else socket.SOCK_DGRAM) as s:
  s.settimeout(4)
  if tcp:
   s.connect(('192.168.1.163',port));s.sendall(struct.pack('!H',len(q))+q)
   def recv(n):
    data=b''
    while len(data)<n:
     chunk=s.recv(n-len(data));assert chunk;data+=chunk
    return data
   b=recv(struct.unpack('!H',recv(2))[0])
  else:s.sendto(q,('192.168.1.163',port));b=s.recvfrom(65535)[0]
 assert struct.unpack('!H',b[:2])[0]==ident and b[3]&15==0
 return b
def health():
 with open('/run/lock/homelab-adguard-backup.lock','a') as lock:
  try:fcntl.flock(lock,fcntl.LOCK_SH|fcntl.LOCK_NB)
  except BlockingIOError:return {'healthy':True,'maintenance':True}
  d=json.loads((P/'credentials.json').read_text());h={'Authorization':'Basic '+base64.b64encode((d['username']+':'+d['password']).encode()).decode()}
  with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:30094/control/filtering/status',headers=h),timeout=5) as f:filters=json.load(f)
  assert filters['enabled'] and any(x['enabled'] and x.get('rules_count',0)>0 for x in filters['filters'])
  a=query('example.org');b=query('example.org',tcp=True);private=query('bearsfamily.es');blocked=query('pagead2.googlesyndication.com');direct=query('pagead2.googlesyndication.com',port=30553)
  assert socket.inet_aton('192.168.1.163') in private
  assert blocked[-4:]==b'\x00\x00\x00\x00' and direct[-4:]==b'\x00\x00\x00\x00'
  disk=shutil.disk_usage('/var/lib/homelab-apps/adguard-home');assert disk.free>1024**3,'Less than 1 GiB free'
  r={'healthy':True,'time':datetime.datetime.now(datetime.timezone.utc).isoformat(),'public_dns_udp_tcp':True,'private_dns':True,'blocking':True,'filter_rules':sum(x.get('rules_count',0) for x in filters['filters'] if x['enabled']),'free_disk_gib':round(disk.free/1024**3,2)}
  (P/'health-latest.json').write_text(json.dumps(r,indent=2));return r
if __name__=='__main__':
 try:print(json.dumps(health()))
 except Exception as e:
  r={'healthy':False,'error':type(e).__name__,'time':datetime.datetime.now(datetime.timezone.utc).isoformat()};(P/'health-latest.json').write_text(json.dumps(r));print(json.dumps(r));raise
