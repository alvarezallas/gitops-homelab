#!/usr/bin/python3
"""Run on pi5 as root after host/GitOps activation. Never prints auth or Secret data."""
import argparse
import base64
import http.cookiejar
import json
import socket
import ssl
import subprocess
import time
import urllib.error
import urllib.request

parser=argparse.ArgumentParser()
parser.add_argument('action',choices=['configure','run','enable','disable','status'])
args=parser.parse_args()
K=['kubectl','--kubeconfig=/etc/kubernetes/admin.conf']
secret=json.loads(subprocess.check_output(K+['-n','semaphore','get','secret','semaphore-web-auth','-o','json']))
password=base64.b64decode(secret['data']['password']).decode()
original=socket.getaddrinfo
socket.getaddrinfo=lambda host,*a,**kw:original('127.0.0.1' if host=='semaphore.bearsfamily.aa' else host,*a,**kw)
ctx=ssl.create_default_context(cafile='/etc/nginx/tls/homelab.crt')
op=urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx),urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
base='https://semaphore.bearsfamily.aa'
headers={'Content-Type':'application/json','Accept':'application/json','X-Requested-With':'XMLHttpRequest','Origin':base,'Referer':base+'/'}

def api(path,data=None,method=None):
    req=urllib.request.Request(base+'/api'+path,data=None if data is None else json.dumps(data).encode(),headers=headers,method=method)
    try:
        with op.open(req,timeout=20) as response:
            raw=response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        raise RuntimeError('Semaphore API error '+str(exc.code)+' '+path) from None

api('/auth/login',{'auth':'admin','password':password},'POST')
project=next(p for p in api('/projects') if p['name']=='Homelab')
assert project['max_parallel_tasks']==1
pid=project['id'];prefix='/project/'+str(pid)
name='nginx - sincronizar main'
tpl=next((t for t in api(prefix+'/templates') if t['name']==name),None)
schedule=next((s for s in api(prefix+'/schedules') if s['name']=='nginx main cada minuto'),None)
if args.action=='configure':
    repo=next(r for r in api(prefix+'/repositories') if r['name']=='Tareas locales Homelab')
    group=next(e for e in api(prefix+'/environment') if e['name']=='Zona horaria Homelab')
    payload={'project_id':pid,'name':name,'app':'bash','playbook':'nginx-sync.sh','repository_id':repo['id'],'environment_ids':[group['id']],'type':'','autorun':False,'allow_parallel_tasks':False,'allow_override_args_in_task':False,'allow_override_branch_in_task':False}
    if tpl:
        payload['id']=tpl['id'];api(prefix+'/templates/'+str(tpl['id']),payload,'PUT')
    else:tpl=api(prefix+'/templates',payload,'POST')
    payload={'project_id':pid,'template_id':tpl['id'],'name':'nginx main cada minuto','type':'','cron_format':'* * * * *','active':False}
    if schedule:
        payload['id']=schedule['id'];api(prefix+'/schedules/'+str(schedule['id']),payload,'PUT')
    else:schedule=api(prefix+'/schedules',payload,'POST')
    print(json.dumps({'project_id':pid,'template_id':tpl['id'],'schedule_id':schedule['id'],'active':False}))
elif args.action=='run':
    assert tpl is not None,'Configure the template first'
    task=api(prefix+'/tasks',{'template_id':tpl['id'],'debug':False,'dry_run':False},'POST')
    tid=task['id'];deadline=time.monotonic()+230
    while time.monotonic()<deadline:
        task=api(prefix+'/tasks/'+str(tid))
        if task['status'] in ['success','error','stopped']:break
        time.sleep(2)
    output=api(prefix+'/tasks/'+str(tid)+'/output')
    text='\n'.join(o.get('output','') for o in output)
    assert password not in text
    print(json.dumps({'task_id':tid,'status':task['status'],'output':text[-7000:]}))
    assert task['status']=='success','nginx task failed; schedule remains disabled until explicitly enabled'
elif args.action in ['enable','disable']:
    assert tpl is not None and schedule is not None
    schedule['active']=args.action=='enable'
    api(prefix+'/schedules/'+str(schedule['id']),schedule,'PUT')
    print(json.dumps({'schedule_id':schedule['id'],'active':schedule['active'],'cron':schedule['cron_format']}))
else:
    print(json.dumps({'template_id':None if tpl is None else tpl['id'],'schedule':None if schedule is None else {k:schedule[k] for k in ['id','name','active','cron_format','template_id']}}))
