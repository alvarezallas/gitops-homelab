#!/usr/bin/env python3
"""Manual DNS publication with automatic checks; no DNS credentials used."""
import json,os,pathlib,secrets,socket,struct,sys,time
def txt_records(name,server):
 ident=secrets.randbelow(65536);packet=struct.pack('!HHHHHH',ident,0x0100,1,0,0,0)+b''.join(bytes([len(x)])+x.encode() for x in name.rstrip('.').split('.'))+b'\0'+struct.pack('!HH',16,1)
 try:
  with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as sock:
   sock.settimeout(4);sock.sendto(packet,(server,53));data=sock.recvfrom(4096)[0]
  rid,flags,qd,an,_,_=struct.unpack('!HHHHHH',data[:12])
  if rid!=ident or flags&15 or flags&0x0200:return set()
  def skip(pos):
   for _ in range(128):
    n=data[pos]
    if n&0xc0==0xc0:return pos+2
    pos+=1
    if not n:return pos
    pos+=n
   raise ValueError('Invalid DNS name')
  pos=12
  for _ in range(qd):pos=skip(pos)+4
  values=set()
  for _ in range(an):
   pos=skip(pos);typ,cls,ttl,length=struct.unpack('!HHIH',data[pos:pos+10]);pos+=10;end=pos+length
   if typ==16 and cls==1:
    p=pos;parts=[]
    while p<end:n=data[p];p+=1;parts.append(data[p:p+n]);p+=n
    values.add(b''.join(parts).decode('utf-8'))
   pos=end
  return values
 except (OSError,ValueError,IndexError,struct.error,UnicodeError):return set()
def write(path,obj):
 tmp=path.with_suffix('.tmp');tmp.write_text(json.dumps(obj,indent=2)+'\n');tmp.chmod(0o600);tmp.replace(path)
def main():
 os.umask(0o077)
 phase=os.environ['ACME_PHASE'];runid=os.environ['ACME_RUN_ID'];assert phase in ['staging','production'] and runid.isalnum()
 base=pathlib.Path('/acme')/phase/'runs'/runid;base.mkdir(parents=True,mode=0o700,exist_ok=True)
 domain=os.environ.get('CERTBOT_DOMAIN') or os.environ.get('CERTBOT_IDENTIFIER');assert domain and domain.removeprefix('*.')=='bearsfamily.es'
 value=os.environ['CERTBOT_VALIDATION'];assert value and len(value)<1024
 request={'type':'TXT','name':'_acme-challenge.bearsfamily.es','host':'_acme-challenge','value':value}
 path=base/'requests.json';items=json.loads(path.read_text()) if path.exists() else []
 if request not in items:items.append(request)
 write(path,items)
 remaining=int(os.environ.get('CERTBOT_REMAINING_CHALLENGES','0'))
 write(base/'status.json',{'phase':phase,'status':'collecting_requests' if remaining else 'waiting_dns','record_count':len(items),'remaining':remaining})
 if remaining:return
 expected={x['value'] for x in items};deadline=time.monotonic()+3600
 while time.monotonic()<deadline:
  if all(expected<=txt_records(request['name'],server) for server in ['1.1.1.1','8.8.8.8']):
   write(base/'status.json',{'phase':phase,'status':'dns_verified','record_count':len(items)});return
  time.sleep(5)
 write(base/'status.json',{'phase':phase,'status':'dns_timeout','record_count':len(items)});raise SystemExit('DNS validation timed out; existing services unchanged')
if __name__=='__main__':main()
