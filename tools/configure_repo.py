#!/usr/bin/env python3
"""Configura URL/rama sin guardar credenciales ni tocar el clúster."""
import argparse,json,pathlib,re,urllib.parse
ROOT=pathlib.Path(__file__).resolve().parents[1]
def validate_url(url):
 if re.fullmatch(r'git@[A-Za-z0-9.-]+:[A-Za-z0-9_./-]+',url):
  if '..' in url.split(':',1)[1].split('/'):raise ValueError('Ruta SSH inválida')
 elif url.startswith(('https://','ssh://')):
  p=urllib.parse.urlsplit(url)
  if not p.hostname or not p.path.strip('/') or p.password or p.query or p.fragment:raise ValueError('URL incompleta o con credenciales/query; no almacenar tokens en URL')
  if p.scheme=='https' and p.username:raise ValueError('HTTPS debe carecer de usuario/token en URL')
  if p.scheme=='ssh' and p.username not in (None,'git'):raise ValueError('Usar identidad git para SSH')
  if not re.fullmatch(r'[A-Za-z0-9_./:@+-]+',url.replace('https://','').replace('ssh://','')):raise ValueError('URL con caracteres no admitidos')
 else:raise ValueError('Usar HTTPS o SSH git@host:cuenta/repo.git')
 if any(x in url for x in ('example.invalid','USUARIO','TU_CUENTA')):raise ValueError('Sustituir la URL de ejemplo por el repositorio real')
 return url
def configure(url,branch):
 validate_url(url)
 if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]*',branch) or '..' in branch or branch.endswith(('/','.lock')):raise ValueError('Rama inválida')
 config=ROOT/'repo-config.json';old=json.loads(config.read_text());count=0
 for folder in ('bootstrap','clusters'):
  for file in (ROOT/folder).rglob('*.yaml'):
   text=file.read_text(encoding='utf-8');text=text.replace(old['repoURL'],url)
   text=re.sub(r'(?m)^(\s*targetRevision: )'+re.escape(old['branch'])+r'$',lambda m:m[1]+branch,text)
   file.write_text(text,encoding='utf-8',newline='\n');count+=1
 config.write_text(json.dumps({'repoURL':url,'branch':branch,'configured':True},indent=2)+'\n',encoding='utf-8')
 print('Configurados '+str(count)+' manifiestos. No se ha conectado Git ni aplicado cambios al clúster.')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--url',required=True);p.add_argument('--branch',default='main');a=p.parse_args()
 try:configure(a.url,a.branch)
 except ValueError as e:p.error(str(e))
