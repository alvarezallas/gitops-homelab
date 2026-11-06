"""Private local speech/LLM gateway, carried to pi5 through a pinned SSH tunnel."""
import os,pathlib,json,time,threading,socket,select,tempfile,gc,base64,hashlib,logging,contextlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parent
CFG=json.loads((ROOT/'secrets/config.json').read_text(encoding='utf-8'))
os.environ.update(HF_HUB_DISABLE_TELEMETRY='1',HF_HUB_DISABLE_SYMLINKS_WARNING='1',HF_HUB_OFFLINE='1',HF_HOME=str(ROOT/'models/huggingface'))
DLL=[]
for p in (ROOT/'venv/Lib/site-packages/nvidia').glob('*/bin'):
 DLL.append(os.add_dll_directory(str(p)));os.environ['PATH']=str(p)+os.pathsep+os.environ['PATH']
import httpx,paramiko
from fastapi import FastAPI,Request,UploadFile,File,Form,HTTPException
from fastapi.responses import JSONResponse,StreamingResponse
from faster_whisper import WhisperModel
app=FastAPI(docs_url=None,redoc_url=None,openapi_url=None)
GPU=ROOT.parent/'agent-pc/media.lock'
log=logging.getLogger('speakr')
@app.middleware('http')
async def auth(req,call_next):
 import secrets
 provided=req.headers.get('authorization','')
 legacy=secrets.compare_digest(provided,'Bearer '+CFG['api_key'])
 n8n=bool(CFG.get('n8n_api_key')) and secrets.compare_digest(provided,'Bearer '+CFG['n8n_api_key'])
 if not (legacy or n8n):return JSONResponse({'error':'unauthorized'},status_code=401)
 if n8n and req.url.path not in ['/health','/v1/models','/v1/chat/completions']:return JSONResponse({'error':'forbidden'},status_code=403)
 req.state.client_role='n8n' if n8n else 'speakr'
 return await call_next(req)
@contextlib.contextmanager
def gpu_slot():
 deadline=time.monotonic()+1200
 while True:
  try:fd=os.open(GPU,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.close(fd);break
  except FileExistsError:
   if time.monotonic()>deadline:raise HTTPException(503,'GPU occupied; retry later')
   time.sleep(2)
 try:
  # Respect work submitted directly to ComfyUI before claiming its memory.
  while True:
   try:
    q=httpx.get('http://127.0.0.1:8188/queue',timeout=4).json()
    busy=bool(q.get('queue_running') or q.get('queue_pending'))
   except httpx.RequestError:busy=False
   if not busy:break
   if time.monotonic()>deadline:raise HTTPException(503,'ComfyUI occupied; retry later')
   time.sleep(2)
  try:httpx.post('http://127.0.0.1:8188/free',json={'unload_models':True,'free_memory':True},timeout=30)
  except httpx.RequestError:pass
  yield
 finally:GPU.unlink(missing_ok=True)
def unload_ollama():
 try:httpx.post('http://127.0.0.1:11434/api/generate',json={'model':'qwen3.5:4b','keep_alive':0},timeout=60)
 except httpx.RequestError:pass
@app.get('/health')
def health():return {'status':'ok','asr':'medium','device':'cuda','diarization':False}
@app.get('/v1/models')
def models(req:Request):return {'object':'list','data':[{'id':m,'object':'model','owned_by':'homelab'} for m in (['qwen3.5:4b'] if req.state.client_role=='n8n' else ['whisper-1','qwen3.5:4b'])]}
@app.post('/v1/embeddings')
async def embeddings(req:Request):
 body=await req.json()
 if body.get('model')!='embeddinggemma:300m':raise HTTPException(400,'Embedding model not configured')
 data=body.get('input')
 if not isinstance(data,(str,list)):raise HTTPException(400,'Invalid input')
 if isinstance(data,list) and len(data)>128:raise HTTPException(413,'Maximum 128 chunks')
 async with httpx.AsyncClient(timeout=180) as client:
  r=await client.post('http://127.0.0.1:11434/api/embed',json={'model':'embeddinggemma:300m','input':data,'options':{'num_gpu':0},'keep_alive':0})
  r.raise_for_status();result=r.json()
 return {'object':'list','model':'embeddinggemma:300m','data':[{'object':'embedding','index':i,'embedding':e} for i,e in enumerate(result['embeddings'])],'usage':{'prompt_tokens':result.get('prompt_eval_count',0),'total_tokens':result.get('prompt_eval_count',0)}}
@app.post('/v1/audio/transcriptions')
def transcribe(file:UploadFile=File(...),model:str=Form('whisper-1'),language:str=Form('es'),response_format:str=Form('verbose_json'),prompt:str=Form('')):
 if model!='whisper-1':raise HTTPException(400,'Model not configured')
 path=None;wm=None
 try:
  with tempfile.NamedTemporaryFile(dir=ROOT/'tmp',suffix=pathlib.Path(file.filename or '.audio').suffix,delete=False) as f:
   path=pathlib.Path(f.name);total=0
   while chunk:=file.file.read(1024*1024):
    total+=len(chunk)
    if total>250*1024*1024:raise HTTPException(413,'Maximum audio size 250 MiB')
    f.write(chunk)
  with gpu_slot():
   unload_ollama()
   wm=WhisperModel('medium',device='cuda',compute_type='int8_float16',download_root=str(ROOT/'models/whisper'),local_files_only=True,cpu_threads=8,num_workers=1)
   segs,info=wm.transcribe(str(path),language=language or 'es',beam_size=5,vad_filter=True,word_timestamps=True,initial_prompt=prompt or None,condition_on_previous_text=False)
   ss=[];words=[]
   for i,s in enumerate(segs):
    ss.append({'id':i,'start':s.start,'end':s.end,'text':s.text,'avg_logprob':s.avg_logprob,'no_speech_prob':s.no_speech_prob,'compression_ratio':s.compression_ratio,'temperature':s.temperature,'tokens':s.tokens,'seek':s.seek})
    words.extend({'word':w.word,'start':w.start,'end':w.end} for w in (s.words or []))
   result={'task':'transcribe','language':info.language,'duration':info.duration,'text':''.join(s['text'] for s in ss).strip(),'segments':ss,'words':words}
   del wm;wm=None;gc.collect()
  return result
 finally:
  if wm is not None:del wm;gc.collect()
  if path:path.unlink(missing_ok=True)
@app.post('/v1/chat/completions')
async def chat(req:Request):
 body=await req.json()
 if body.get('model')!='qwen3.5:4b':raise HTTPException(400,'Model not configured')
 if req.state.client_role=='n8n':
  body['max_tokens']=min(int(body.pop('max_completion_tokens',body.get('max_tokens',2048))),2048)
  body['think']=False
  body['temperature']=0.1
 # Execute synchronous work in a worker thread; streaming iterator holds the GPU slot.
 from starlette.concurrency import run_in_threadpool
 if body.get('stream'):
  def stream():
   with gpu_slot():
    try:
     with httpx.Client(timeout=1200) as client:
      with client.stream('POST','http://127.0.0.1:11434/v1/chat/completions',json=body) as r:
       r.raise_for_status()
       for chunk in r.iter_bytes():yield chunk
    finally:unload_ollama()
  return StreamingResponse(stream(),media_type='text/event-stream')
 def complete():
  with gpu_slot():
   try:
    r=httpx.post('http://127.0.0.1:11434/v1/chat/completions',json=body,timeout=1200);r.raise_for_status();return r.json()
   finally:unload_ollama()
 return await run_in_threadpool(complete)
class Pin(paramiko.MissingHostKeyPolicy):
 def missing_host_key(self,client,host,key):
  fp='SHA256:'+base64.b64encode(hashlib.sha256(key.asbytes()).digest()).decode().rstrip('=')
  if key.get_name()!='ssh-ed25519' or fp!=CFG['ssh_fingerprint']:raise paramiko.SSHException('Host key mismatch')
def forward(chan):
 try:
  with socket.create_connection(('127.0.0.1',18995),timeout=15) as sock:
   sock.settimeout(None)
   while True:
    ready,_,_=select.select([chan,sock],[],[],60)
    for source in ready:
     data=source.recv(65536)
     if not data:return
     (sock if source is chan else chan).sendall(data)
 finally:chan.close()
def tunnel():
 while True:
  c=paramiko.SSHClient();c.set_missing_host_key_policy(Pin())
  try:
   c.connect('192.168.1.163',username='alvarense',key_filename=str(ROOT/'secrets/tunnel'),look_for_keys=False,allow_agent=False,timeout=15)
   t=c.get_transport();t.set_keepalive(20)
   t.request_port_forward('127.0.0.1',18995,handler=lambda ch,origin,server:threading.Thread(target=forward,args=(ch,),daemon=True).start())
   log.info('Private SSH tunnel connected')
   while t.is_active():time.sleep(5)
  except Exception as e:log.warning('Tunnel retry: %s',type(e).__name__)
  finally:c.close()
  time.sleep(10)
def ollama_watch():
 agent=ROOT.parent/'agent-pc'
 while True:
  try:httpx.get('http://127.0.0.1:11434/api/version',timeout=4).raise_for_status()
  except (httpx.RequestError,httpx.HTTPStatusError):
   env=os.environ.copy();env.update(OLLAMA_MODELS=str(agent/'models/ollama'),OLLAMA_HOST='127.0.0.1:11434',OLLAMA_NO_CLOUD='1',OLLAMA_CONTEXT_LENGTH='32768',OLLAMA_NUM_PARALLEL='1')
   with (ROOT/'ollama.log').open('ab') as log_file:
    subprocess.Popen([str(agent/'ollama/ollama.exe'),'serve'],env=env,stdout=log_file,stderr=log_file,creationflags=subprocess.CREATE_NO_WINDOW)
  time.sleep(30)
if __name__=='__main__':
 import uvicorn
 (ROOT/'tmp').mkdir(exist_ok=True)
 threading.Thread(target=tunnel,daemon=True).start()
 threading.Thread(target=ollama_watch,daemon=True).start()
 uvicorn.run(app,host='127.0.0.1',port=18995,access_log=False)
