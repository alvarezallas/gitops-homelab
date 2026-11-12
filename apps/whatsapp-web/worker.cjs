'use strict';
const http=require('http'),crypto=require('crypto'),fs=require('fs'),path=require('path');
const ROOT=__dirname;if(process.platform==='win32')process.env.PLAYWRIGHT_BROWSERS_PATH=path.join(ROOT,'browsers');
const {chromium}=require('playwright');
const PRIVATE=process.env.DATA_DIR||path.join(ROOT,'private'),cfg=JSON.parse(fs.readFileSync(process.env.CONFIG_FILE||path.join(PRIVATE,'config.json'),'utf8'));
const CP=path.join(PRIVATE,'checkpoint.json');let ctx,page,ready=false,busy=false,stopping=false,lastError=null,xvfb;
const ownEvidence=/\((?:Tú|You)\)|(?:message yourself|mensajes? a ti mismo|envía mensajes a este mismo número)/i;
const equal=(a,b)=>crypto.timingSafeEqual(crypto.createHash('sha256').update(a||'').digest(),crypto.createHash('sha256').update(b||'').digest());
function json(res,status,obj){res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(obj));}
function checkpoint(d){const temp=CP+'.tmp';fs.writeFileSync(temp,JSON.stringify(d));fs.renameSync(temp,CP);}
async function queue(action,body){const r=await fetch(cfg.queue_url+'/'+action,{method:'POST',redirect:'error',headers:{'Content-Type':'application/json','X-Bears-Queue':cfg.queue_token},body:JSON.stringify(body),signal:AbortSignal.timeout(60000)});if(!r.ok)throw new Error('queue_http_'+r.status);return r.json();}
async function linked(){
 if(!page||page.isClosed())return false;
 if(await page.locator('[data-ref] canvas').isVisible().catch(()=>false))return false;
 for(const selector of ['#pane-side','#side','#main'])if(await page.locator(selector).isVisible().catch(()=>false))return true;
 return await page.getByText(/^(?:Envía mensajes a (?:este mismo número|ti mismo)\.?|Message yourself|Mensajes a ti mismo)$/i).isVisible().catch(()=>false);
}
async function self(){
 if(!await linked())throw new Error('session_not_linked');
 const h=page.locator('#main header');if(await h.isVisible().catch(()=>false)&&ownEvidence.test(await h.innerText()))return;
 let entry=page.getByText(/^(?:Envía mensajes a (?:este mismo número|ti mismo)\.?|Message yourself|Mensajes a ti mismo)$/i);
 if(!await entry.isVisible().catch(()=>false)){
  const b=page.getByRole('button',{name:/^(Nuevo chat|New chat)$/i});
  if(await b.count()!==1)throw new Error('new_chat_not_unique');await b.click({timeout:10000});
 }
 await entry.first().waitFor({state:'visible',timeout:15000});
 if(await entry.count()!==1)throw new Error('self_entry_not_unique');await entry.click({timeout:10000});
 await page.locator('#main header').waitFor({timeout:15000});
 if(!ownEvidence.test(await page.locator('#main header').innerText()))throw new Error('self_header_not_verified');
}
function marker(id){return 'BF-DIGEST:'+crypto.createHash('sha256').update(id).digest('hex').slice(0,12);}
async function confirmed(id){
 const containers=page.locator('#main [data-testid="msg-container"]').filter({hasText:marker(id)});
 const receiptLabel=/^\s*(?:Enviado|Entregado|Leído|Sent|Delivered|Read)\s*$/i;
 if(await containers.count()===1){
  const receipt=containers.locator('[data-testid="msg-meta"]').getByLabel(receiptLabel);
  if(await receipt.count()===1&&await receipt.isVisible())return true;
 }
 const bubble=page.locator('#main [data-testid^="conv-msg-"], #main .message-out').filter({hasText:marker(id)});
 for(let i=0;i<await bubble.count();i++){
  const item=bubble.nth(i);
  if(!await item.locator('[data-icon="tail-out"]').count()&&!await item.evaluate(e=>e.classList.contains('message-out')))continue;
  const legacy=item.locator('[data-icon="msg-check"], [data-icon="msg-dblcheck"], [data-icon="msg-dblcheck-ack"]');
  if(await legacy.first().isVisible().catch(()=>false))return true;
  const meta=item.locator('[data-testid="msg-meta"]');
  if(await meta.getByLabel(/^\s*(?:Enviado|Entregado|Leído|Sent|Delivered|Read)\s*$/i).first().isVisible().catch(()=>false))return true;
 }
 return false;
}
async function dismissWelcome(){
 const d=page.getByRole('dialog');if(await d.count()!==1)return;
 if(!(await d.innerText()).includes('Novedades en WhatsApp Web'))return;
 const b=d.getByRole('button',{name:'Continuar',exact:true});if(await b.count()===1)await b.click({timeout:10000});
}

async function receipt(job,state){const r=await queue('receipt',{id:job.id,lease:job.lease,state});if(r.receipt?.id!==job.id)throw new Error('receipt_not_confirmed');fs.unlinkSync(CP);}
async function tick(){
 if(busy||stopping||!ready||fs.existsSync(path.join(PRIVATE,'delivery.paused')))return;busy=true;
 try{
  if(!await linked())return;
  await dismissWelcome();
  await self();
  if(fs.existsSync(CP)){
   const job=JSON.parse(fs.readFileSync(CP,'utf8'));await receipt(job,await confirmed(job.id)?'sent':'uncertain');return;
  }
  const result=await queue('claim',{lease:crypto.randomUUID()});const job=result.job;if(!job?.id)return;
  if(typeof job.body!=='string'||!job.body.trim()||job.body.length>3000)throw new Error('invalid_queued_body');
  checkpoint({id:job.id,lease:job.lease});
  try{
   if(await confirmed(job.id)){await receipt(job,'sent');return;}
   if (/^mail-story-[a-f0-9]{16}-image$/.test(job.id)) {
    await sendChapterImage(job);
   } else {
   const input=page.locator('#main footer [contenteditable="true"][role="textbox"]');
   if(await input.count()!==1)throw new Error('composer_not_unique');if((await input.innerText()).trim())throw new Error('existing_draft');
   const [title, ...bodyLines]=job.body.split('\n');
   await input.fill([title,'['+marker(job.id)+']',...bodyLines].join('\n'));
   if(!ownEvidence.test(await page.locator('#main header').innerText()))throw new Error('self_header_changed');
   await input.press('Enter');
   }
   for(let i=0;i<30;i++){if(await confirmed(job.id)){await receipt(job,'sent');lastError=null;return;}await page.waitForTimeout(1000);}
   throw new Error('send_result_not_confirmed');
  }catch(e){lastError=/^[a-z_]+$/.test(e.message)?e.message:'browser_operation_failed';if(fs.existsSync(CP))await receipt(job,'uncertain');}
 }catch(e){lastError=/^[a-z0-9_]+$/.test(e.message)?e.message:'worker_failed';}
 finally{busy=false;}
}
async function startBrowser(){
 if(process.platform==='linux'){
  if(process.env.WA_EXCLUSIVE_LOCKED!=='1')throw new Error('exclusive_profile_lock_required');
  // Deployment uses flock --no-fork before Node; the volume cannot have two workers.
  const profile=path.join(PRIVATE,'profile');fs.mkdirSync(profile,{recursive:true});
  for(const name of ['SingletonLock','SingletonCookie','SingletonSocket']){
   const f=path.join(profile,name);try{const s=fs.lstatSync(f);if(s.isSymbolicLink()||s.isFile())fs.unlinkSync(f);}catch(e){if(e.code!=='ENOENT')throw e;}
  }
  process.env.HOME=path.join(PRIVATE,'home');process.env.XDG_CONFIG_HOME=path.join(PRIVATE,'home/.config');process.env.XDG_CACHE_HOME=path.join(PRIVATE,'home/.cache');
  fs.mkdirSync(process.env.XDG_CONFIG_HOME,{recursive:true});fs.mkdirSync(process.env.XDG_CACHE_HOME,{recursive:true});
 }
 if(process.env.PW_XVFB==='1'){
  process.env.DISPLAY=':99';xvfb=require('child_process').spawn('/usr/bin/Xvfb',[':99','-screen','0','1280x900x24','-nolisten','tcp'],{stdio:'ignore'});
  for(let i=0;i<50&&!fs.existsSync('/tmp/.X11-unix/X99');i++)await new Promise(r=>setTimeout(r,200));
  if(!fs.existsSync('/tmp/.X11-unix/X99'))throw new Error('virtual_display_not_ready');
 }
 ctx=await chromium.launchPersistentContext(path.join(PRIVATE,'profile'),{...(process.platform==='linux'?{channel:'chromium'}:{}),headless:process.env.PW_HEADED!=='1',chromiumSandbox:true,locale:'es-ES',viewport:{width:1280,height:900},acceptDownloads:false});
 page=ctx.pages()[0]||await ctx.newPage();page.on('dialog',d=>d.dismiss());await page.goto('https://web.whatsapp.com/',{waitUntil:'domcontentloaded',timeout:90000});ready=true;
}
const HTML=`<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>BearsFamily · WhatsApp</title><style>body{font:16px system-ui;background:#0b141a;color:#d9fdd3;max-width:720px;margin:40px auto;padding:20px}img{max-width:300px;background:white}a{color:#8ce9bf}</style><h1>Vincular WhatsApp Web</h1><p>En tu móvil: WhatsApp → Dispositivos vinculados → Vincular un dispositivo.</p><p id="status">Iniciando…</p><img id="qr" alt="QR privado de WhatsApp" hidden><p>Perfil exclusivo del agente. Solo entrega al chat propio. No compartas esta página ni su contraseña.</p><script>async function update(){const s=await(await fetch('/status')).json();statusEl=document.getElementById('status');statusEl.textContent=s.linked?'Sesión vinculada. Esperando la prueba de entrega.':s.browser_ready?'Escanea el QR con tu móvil.':'Iniciando navegador…';const i=document.getElementById('qr');i.hidden=s.linked||!s.browser_ready;if(!i.hidden)i.src='/qr?t='+Date.now()}update();setInterval(update,12000)</script></html>`;
const chapterJob = /^mail-story-[a-f0-9]{16}$/;

async function chapterReview(id) {
 if (busy) return { state: 'busy' };
 busy = true;
 try {
  if (!await linked()) return { state: 'unlinked' };
  await self();
  if (!await confirmed(id)) return { state: 'awaiting_delivery' };
  if (fs.existsSync(chapterImagePath(id)) && !await confirmed(`${id}-image`)) return { state: 'awaiting_image' };
  const reference = marker(id);
  const code = id.slice(-8).toUpperCase();
  const optionReferences = { ok: marker(`${id}-ok-option`), no: marker(`${id}-no-option`) };
  const decision = await page.locator('#main [data-testid="msg-container"]').evaluateAll((rows, args) => {
   const bodySelector = '[data-pre-plain-text] .selectable-text, .copyable-text .selectable-text';
   const quoteSelector = '[data-testid*="quoted"], [data-testid*="reply-preview"]';
   const draft = rows.findIndex(row => [...row.querySelectorAll(bodySelector)].some(node =>
    !node.closest(quoteSelector) && node.innerText.includes(`[${args.reference}]`)));
   if (draft < 0) return null;
   const optionsSeen = new Set();
   for (const row of rows.slice(draft + 1)) {
    const ownMessage = row.closest('.message-out') || row.querySelector('[data-icon="tail-out"]');
    if (!ownMessage) continue;
    const quote = [...row.querySelectorAll(quoteSelector)].some(node =>
     node.innerText.includes(`[${args.reference}]`) || node.innerText.includes(`Revision ${args.code}`));
    const parts = [...row.querySelectorAll(bodySelector)].filter(node => !node.closest(quoteSelector));
    const body = [...new Set(parts.map(node => node.innerText.trim()).filter(Boolean))].join(' ').replace(/\s+/g, ' ').toUpperCase();
    const option = /^(OK|NO) ([A-F0-9]{8})-OP(?: \[(BF-DIGEST:[A-F0-9]{12})\])?$/.exec(body);
    if (option && option[2] === args.code) {
     const answer = option[1].toLowerCase();
     const expectedMarker = args.optionReferences[answer].toUpperCase();
     if (option[3] === expectedMarker && !optionsSeen.has(answer)) {
      optionsSeen.add(answer);
      continue;
     }
     if (optionsSeen.has(answer) && (!option[3] || option[3] === expectedMarker)) return answer;
    }
    if (body === `OK ${args.code}` || (quote && body === 'OK')) return 'ok';
    if (body === `NO ${args.code}` || (quote && body === 'NO')) return 'no';
   }
   return null;
  }, { reference, code, optionReferences });
  return decision ? { state: 'answered', decision } : { state: 'awaiting_reply' };
 } finally {
  busy = false;
 }
}

const chapterImageDir = path.join(PRIVATE, 'chapter-images');
const pngSignature = Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]);
const maxChapterImageBytes = 5 * 1024 * 1024;

function chapterImagePath(id) {
 if (!chapterJob.test(id)) throw new Error('invalid_chapter_reference');
 return path.join(chapterImageDir, `${id}.png`);
}

async function uploadChapterImage(req, res, url) {
 const id = url.searchParams.get('id') || '';
 if (!chapterJob.test(id) || req.headers['content-type'] !== 'image/png') {
  return json(res, 400, { error: 'invalid_chapter_image' });
 }
 const size = Number(req.headers['content-length']);
 if (!Number.isSafeInteger(size) || size < 33 || size > maxChapterImageBytes) {
  return json(res, 413, { error: 'chapter_image_size' });
 }
 const chunks = [];
 let read = 0;
 for await (const chunk of req) {
  read += chunk.length;
  if (read > size) return json(res, 413, { error: 'chapter_image_size' });
  chunks.push(chunk);
 }
 const png = Buffer.concat(chunks);
 if (read !== size || !png.subarray(0, 8).equals(pngSignature) || png.toString('ascii', 12, 16) !== 'IHDR') {
  return json(res, 400, { error: 'invalid_chapter_image' });
 }
 const digest = content => crypto.createHash('sha256').update(content).digest('hex');
 const filename = chapterImagePath(id);
 fs.mkdirSync(chapterImageDir, { recursive: true, mode: 0o700 });
 const temporary = `${filename}.${crypto.randomUUID()}.tmp`;
 try {
  fs.writeFileSync(temporary, png, { flag: 'wx', mode: 0o600 });
  try { fs.linkSync(temporary, filename); } catch (error) { if (error.code !== 'EEXIST') throw error; }
 } finally {
  fs.rmSync(temporary, { force: true });
 }
 if (digest(fs.readFileSync(filename)) !== digest(png)) return json(res, 409, { error: 'chapter_image_already_set' });
 return json(res, 200, { id, sha256: digest(png) });
}

async function sendChapterImage(job) {
 const id = job.id.slice(0, -'-image'.length);
 const image = chapterImagePath(id);
 if (!fs.existsSync(image)) throw new Error('chapter_image_missing');
 const attach = page.getByRole('button', { name: /^(?:Adjuntar|Attach)$/i });
 await attach.click({ timeout: 10000 });
 const gallery = page.getByText(/^(?:Fotos y v[ií]deos|Photos & videos)$/i, { exact: true });
 const [chooser] = await Promise.all([
  page.waitForEvent('filechooser', { timeout: 10000 }),
  gallery.click({ timeout: 10000 }),
 ]);
 await chooser.setFiles(image);
 const caption = page.locator('[contenteditable="true"][role="textbox"]:visible').filter({ hasNotText: /\S/ });
 const previewCaption = caption.locator('xpath=self::*[not(ancestor::footer)]');
 await previewCaption.fill(`${job.body}\n[${marker(job.id)}]`, { timeout: 10000 });
 const send = page.getByRole('button', { name: /^(?:Enviar(?: 1 seleccionado)?|Send(?: 1 selected)?)$/i }).filter({ visible: true });
 await send.click({ timeout: 10000 });
}

const server=http.createServer(async(req,res)=>{
 try{
  if(!equal(req.headers.authorization,'Basic '+Buffer.from('bearsfamily:'+cfg.admin_password).toString('base64'))){res.writeHead(401,{'WWW-Authenticate':'Basic realm="BearsFamily WhatsApp"','Cache-Control':'no-store'});return res.end();}
  const u=new URL(req.url,'http://127.0.0.1');
  if (req.method === 'POST' && u.pathname === '/chapter-image') return await uploadChapterImage(req, res, u);
  if(req.method!=='GET')return json(res,405,{error:'method_not_allowed'});
  if(u.pathname==='/status')return json(res,200,{browser_ready:ready,linked:await linked(),busy,last_error:lastError,checkpoint:fs.existsSync(CP)});
  if (u.pathname === '/chapter-review') {
   if (req.method !== 'GET') return json(res, 405, { error: 'method_not_allowed' });
   const id = u.searchParams.get('id') || '';
   if (!chapterJob.test(id)) return json(res, 400, { error: 'invalid_chapter_reference' });
   return json(res, 200, await chapterReview(id));
  }
  if(u.pathname==='/diagnostics'){
   const selected=await page.locator('button,[role="button"]').evaluateAll(es=>es.map(e=>({name:e.getAttribute('aria-label')||e.getAttribute('title')||'',visible:!!e.getClientRects().length})).filter(x=>/^(Nuevo chat|New chat)(\b|$)/i.test(x.name)));
   const selfTexts=await page.getByText(/(?:mismo número|mensajes a ti mismo|message yourself)/i).evaluateAll(es=>es.filter(e=>e.getClientRects().length).map(e=>({tag:e.tagName,text:e.textContent.trim().slice(0,140)})));
   const remember=await page.getByRole('checkbox').evaluateAll(es=>es.map(e=>({checked:e.checked??e.getAttribute('aria-checked'),label:e.getAttribute('aria-label')||e.closest('label')?.textContent?.trim()||''})));
   const storage=await page.evaluate(async()=>({databases:(await indexedDB.databases()).map(d=>({name:d.name,version:d.version})),localStorageItems:localStorage.length}));
   return json(res,200,{url:new URL(page.url()).origin,pane_side:await page.locator('#pane-side').count(),side:await page.locator('#side').count(),main:await page.locator('#main').count(),qr:await page.locator('[data-ref] canvas').count(),new_chat_buttons:selected,self_entries:selfTexts,dialogs:await page.getByRole('dialog').count(),remember_session:remember,storage});
  }
  if(u.pathname==='/qr'){
   if(!ready||await linked())return json(res,404,{error:'qr_not_available'});
   const qr=page.locator('[data-ref] canvas, canvas[aria-label*="QR"]');if(await qr.count()!==1)return json(res,503,{error:'waiting_for_qr'});
   res.writeHead(200,{'Content-Type':'image/png','Cache-Control':'no-store'});return res.end(await qr.screenshot());
  }
  res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','X-Frame-Options':'DENY'});res.end(HTML);
 }catch(e){json(res,503,{error:'not_ready'});}
});
(async()=>{server.listen(Number(process.env.PORT||18996),process.env.LISTEN_HOST||'127.0.0.1');await startBrowser();setInterval(tick,60000);await tick();})().catch(e=>{console.error('whatsapp_start_failed:'+e.name+': '+e.message);process.exit(1)});
async function stop(){stopping=true;server.close();if(ctx)await ctx.close().catch(()=>{});if(xvfb)xvfb.kill('SIGTERM');process.exit(0)}
process.on('SIGTERM',stop);process.on('SIGINT',stop);
