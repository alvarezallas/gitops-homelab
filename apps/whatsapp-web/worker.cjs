'use strict';
const http=require('http'),crypto=require('crypto'),fs=require('fs'),path=require('path');
const ROOT=__dirname;if(process.platform==='win32')process.env.PLAYWRIGHT_BROWSERS_PATH=path.join(ROOT,'browsers');
const {chromium}=require('playwright');
const PRIVATE=process.env.DATA_DIR||path.join(ROOT,'private'),cfg=JSON.parse(fs.readFileSync(process.env.CONFIG_FILE||path.join(PRIVATE,'config.json'),'utf8'));
const CP=path.join(PRIVATE,'checkpoint.json');let ctx,page,ready=false,busy=false,stopping=false,lastError=null;
const ownEvidence=/\((?:Tú|You)\)|(?:message yourself|mensajes? a ti mismo|envía mensajes a este mismo número)/i;
const equal=(a,b)=>crypto.timingSafeEqual(crypto.createHash('sha256').update(a||'').digest(),crypto.createHash('sha256').update(b||'').digest());
function json(res,status,obj){res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(obj));}
function checkpoint(d){const temp=CP+'.tmp';fs.writeFileSync(temp,JSON.stringify(d));fs.renameSync(temp,CP);}
async function queue(action,body){const r=await fetch(cfg.queue_url+'/'+action,{method:'POST',redirect:'error',headers:{'Content-Type':'application/json','X-Bears-Queue':cfg.queue_token},body:JSON.stringify(body),signal:AbortSignal.timeout(60000)});if(!r.ok)throw new Error('queue_http_'+r.status);return r.json();}
async function linked(){return !!page&&!page.isClosed()&&await page.locator('#pane-side').isVisible().catch(()=>false);}
async function self(){
 if(!await linked())throw new Error('session_not_linked');
 const h=page.locator('#main header');if(await h.isVisible().catch(()=>false)&&ownEvidence.test(await h.innerText()))return;
 let b=page.getByRole('button',{name:/^(Nuevo chat|New chat)$/i});
 if(await b.count()!==1)throw new Error('new_chat_not_unique');await b.click();
 let entry=page.getByText(/^(Envía mensajes a este mismo número\.?|Message yourself|Mensajes a ti mismo)$/i);
 if(await entry.count()!==1)throw new Error('self_entry_not_unique');await entry.click();
 await page.locator('#main header').waitFor({timeout:15000});
 if(!ownEvidence.test(await page.locator('#main header').innerText()))throw new Error('self_header_not_verified');
}
function marker(id){return 'BF-DIGEST:'+crypto.createHash('sha256').update(id).digest('hex').slice(0,12);}
async function confirmed(id){const bubble=page.locator('#main .message-out').filter({hasText:marker(id)});if(!await bubble.count())return false;return await bubble.locator('[data-icon="msg-check"], [data-icon="msg-dblcheck"], [data-icon="msg-dblcheck-ack"]').first().isVisible().catch(()=>false);}
async function receipt(job,state){const r=await queue('receipt',{id:job.id,lease:job.lease,state});if(r.receipt?.id!==job.id)throw new Error('receipt_not_confirmed');fs.unlinkSync(CP);}
async function tick(){
 if(busy||stopping||!ready)return;busy=true;
 try{
  if(!await linked())return;
  await self();
  if(fs.existsSync(CP)){
   const job=JSON.parse(fs.readFileSync(CP,'utf8'));await receipt(job,await confirmed(job.id)?'sent':'uncertain');return;
  }
  const result=await queue('claim',{lease:crypto.randomUUID()});const job=result.job;if(!job?.id)return;
  if(typeof job.body!=='string'||!job.body.trim()||job.body.length>3000)throw new Error('invalid_queued_body');
  checkpoint({id:job.id,lease:job.lease});
  try{
   if(await confirmed(job.id)){await receipt(job,'sent');return;}
   const input=page.locator('#main footer [contenteditable="true"][role="textbox"]');
   if(await input.count()!==1)throw new Error('composer_not_unique');if((await input.innerText()).trim())throw new Error('existing_draft');
   await input.fill(job.body+'\n['+marker(job.id)+']');
   if(!ownEvidence.test(await page.locator('#main header').innerText()))throw new Error('self_header_changed');
   await input.press('Enter');
   for(let i=0;i<30;i++){if(await confirmed(job.id)){await receipt(job,'sent');lastError=null;return;}await page.waitForTimeout(1000);}
   throw new Error('send_result_not_confirmed');
  }catch(e){lastError=/^[a-z_]+$/.test(e.message)?e.message:'browser_operation_failed';if(fs.existsSync(CP))await receipt(job,'uncertain');}
 }catch(e){lastError=/^[a-z0-9_]+$/.test(e.message)?e.message:'worker_failed';}
 finally{busy=false;}
}
async function startBrowser(){
 ctx=await chromium.launchPersistentContext(path.join(PRIVATE,'profile'),{...(process.platform==='linux'?{channel:'chromium'}:{}),headless:process.env.PW_HEADED!=='1',chromiumSandbox:true,locale:'es-ES',viewport:{width:1280,height:900},acceptDownloads:false});
 page=ctx.pages()[0]||await ctx.newPage();page.on('dialog',d=>d.dismiss());await page.goto('https://web.whatsapp.com/',{waitUntil:'domcontentloaded',timeout:90000});ready=true;
}
const HTML=`<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>BearsFamily · WhatsApp</title><style>body{font:16px system-ui;background:#0b141a;color:#d9fdd3;max-width:720px;margin:40px auto;padding:20px}img{max-width:300px;background:white}a{color:#8ce9bf}</style><h1>Vincular WhatsApp Web</h1><p>En tu móvil: WhatsApp → Dispositivos vinculados → Vincular un dispositivo.</p><p id="status">Iniciando…</p><img id="qr" alt="QR privado de WhatsApp" hidden><p>Perfil exclusivo del agente. Solo entrega al chat propio. No compartas esta página ni su contraseña.</p><script>async function update(){const s=await(await fetch('/status')).json();statusEl=document.getElementById('status');statusEl.textContent=s.linked?'Sesión vinculada. Esperando la prueba de entrega.':s.browser_ready?'Escanea el QR con tu móvil.':'Iniciando navegador…';const i=document.getElementById('qr');i.hidden=s.linked||!s.browser_ready;if(!i.hidden)i.src='/qr?t='+Date.now()}update();setInterval(update,12000)</script></html>`;
const server=http.createServer(async(req,res)=>{
 try{
  if(!equal(req.headers.authorization,'Basic '+Buffer.from('bearsfamily:'+cfg.admin_password).toString('base64'))){res.writeHead(401,{'WWW-Authenticate':'Basic realm="BearsFamily WhatsApp"','Cache-Control':'no-store'});return res.end();}
  if(req.method!=='GET')return json(res,405,{error:'method_not_allowed'});
  const u=new URL(req.url,'http://127.0.0.1');
  if(u.pathname==='/status')return json(res,200,{browser_ready:ready,linked:await linked(),busy,last_error:lastError,checkpoint:fs.existsSync(CP)});
  if(u.pathname==='/qr'){
   if(!ready||await linked())return json(res,404,{error:'qr_not_available'});
   const qr=page.locator('[data-ref] canvas, canvas[aria-label*="QR"]');if(await qr.count()!==1)return json(res,503,{error:'waiting_for_qr'});
   res.writeHead(200,{'Content-Type':'image/png','Cache-Control':'no-store'});return res.end(await qr.screenshot());
  }
  res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','X-Frame-Options':'DENY'});res.end(HTML);
 }catch(e){json(res,503,{error:'not_ready'});}
});
(async()=>{server.listen(Number(process.env.PORT||18996),process.env.LISTEN_HOST||'127.0.0.1');await startBrowser();setInterval(tick,60000);await tick();})().catch(e=>{console.error('whatsapp_start_failed:'+e.name+': '+e.message);process.exit(1)});
async function stop(){stopping=true;server.close();if(ctx)await ctx.close().catch(()=>{});process.exit(0)}
process.on('SIGTERM',stop);process.on('SIGINT',stop);
