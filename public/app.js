const $ = id => document.getElementById(id);
let pc, dc, mic, sid, socket, timer, started, muted = false, closing = false, generation = 0;
const captions = new Map();
let lastTest = null, allStats = null, ratingsEnabled = false;
const settingIds = ['voice-select', 'language-select', 'tester-code'];
function remember(key, value){try{localStorage.setItem(key,value);}catch{}}
function saved(key){try{return localStorage.getItem(key);}catch{return null;}}
function settingsLocked(locked){for(const id of settingIds)$(id).disabled=locked;}
async function api(path, data) {
  const r = await fetch(path, {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(data)});
  if (!r.ok) { let message = await r.text(); try {message=JSON.parse(message).error || message;} catch {} throw new Error(message); }
  return r.json();
}
const action = data => api(`/api/session/${encodeURIComponent(sid)}/action`,data);
function setStatus(text){ $('status').textContent=text; }
function cleanup(){
  generation++; clearInterval(timer); socket?.close(); dc?.close(); pc?.close(); mic?.getTracks().forEach(t=>t.stop());
  $('audio').srcObject=null; document.body.classList.remove('live');
  for(const id of ['mute','stop','revise']) $(id).disabled=true;
  $('start').disabled=false; $('start').textContent='Neues Gespräch';
  $('approvals').replaceChildren(); sid=null; muted=false; closing=false; $('mute').textContent='Mikrofon ausschalten';
  settingsLocked(false);
}
function caption(e){
  const who=e.type.includes('input_transcript')?'Du':'Activi';
  const key=who+':'+(e.item_id || e.turn_id || e.segment_id || 'current');
  let node=captions.get(key);
  if(!node){
    $('transcript').querySelector('.empty')?.remove(); node=document.createElement('div'); node.className='line';
    const label=document.createElement('b'); label.textContent=who;
    const p=document.createElement('p'); node.append(label,p); $('transcript').append(node); captions.set(key,node);
  }
  node.querySelector('p').textContent+=e.delta || '';
  $('transcript').scrollTop=$('transcript').scrollHeight;
}
function approval(e){
  $('approvals').querySelector('.empty')?.remove();
  if(document.getElementById('approval_'+e.id))return;
  const box=document.createElement('div'); box.className='approval'; box.id='approval_'+e.id;
  const title=document.createElement('b'); title.textContent='Demo-Ticket bestätigen';
  const text=document.createElement('p'); text.textContent=`Referenz: ${e.args.customer_ref}\nPriorität: ${e.args.priority}\n${e.args.issue}`;
  box.append(title,text);
  for(const [label,approved] of [['Bestätigen',true],['Ablehnen',false]]){
    const b=document.createElement('button'); b.textContent=label; if(approved)b.className='approve';
    b.onclick=async()=>{box.querySelectorAll('button').forEach(x=>x.disabled=true); try{await action({action:'approve',id:e.id,approved});}catch(err){$('error').textContent=err.message; box.querySelectorAll('button').forEach(x=>x.disabled=false);}};
    box.append(b);
  }
  $('approvals').append(box);
}
async function ice(peer){
  if(peer.iceGatheringState==='complete')return;
  await new Promise((resolve,reject)=>{
    const done=()=>{if(peer.iceGatheringState==='complete'){clearTimeout(t);peer.removeEventListener('icegatheringstatechange',done);resolve();}};
    const t=setTimeout(()=>{peer.removeEventListener('icegatheringstatechange',done);reject(new Error('Verbindungsaufbau dauert zu lange. Bitte erneut versuchen.'));},10000);
    peer.addEventListener('icegatheringstatechange',done);done();
  });
}
$('start').onclick=async()=>{
  $('start').disabled=true; $('error').textContent=''; setStatus('Mikrofon und Verbindung werden vorbereitet …');
  settingsLocked(true); lastTest=null; $('rating-fields').disabled=true;
  $('rating-form').reset();$('rating-message').textContent='';
  const attempt=++generation;
  try{
    const tester=$('tester-code').value.trim();
    if(ratingsEnabled && tester.length<3)throw new Error('Bitte einen persönlichen Testcode mit mindestens 3 Zeichen eingeben.');
    for(const id of settingIds)remember('activi-'+id,$(id).value);
    await api('/api/login',{password:$('password').value});
    mic=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true}});
    pc=new RTCPeerConnection(); pc.ontrack=e=>{$('audio').srcObject=e.streams[0]||new MediaStream([e.track]); $('audio').play().catch(()=>{$('audio').hidden=false;});};
    pc.onconnectionstatechange=()=>{if(pc?.connectionState==='failed'&&!closing){$('error').textContent='Audioverbindung unterbrochen. Bitte neu starten.';stop();}};
    mic.getTracks().forEach(t=>pc.addTrack(t,mic)); dc=pc.createDataChannel('oai-events');
    let readyResolve; const ready=new Promise(resolve=>readyResolve=resolve);
    dc.onmessage=({data})=>{let e;try{e=JSON.parse(data);}catch{return;}
      if(e.type==='session.started'){readyResolve();}
      if(['session.input_transcript.delta','session.output_transcript.delta'].includes(e.type))caption(e);
      if(e.type==='error')$('error').textContent=e.error?.message||'Voice-Dienst meldet einen Fehler';
      if(e.type==='session.closed')setStatus('Gespräch abgeschlossen');
    };
    await pc.setLocalDescription(await pc.createOffer());await ice(pc);
    const result=await api('/api/session',{sdp:pc.localDescription.sdp,voice:$('voice-select').value,
      language:$('language-select').value,tester_code:tester});sid=result.session_id;
    lastTest=result.test_id?result:null;
    $('rating-context').textContent=lastTest?`${result.voice} · ${config.languages[result.language]} · ${result.version}`:'Bewertungsdatenbank ist noch nicht eingerichtet.';
    await pc.setRemoteDescription({type:'answer',sdp:result.sdp});
    socket=new WebSocket(`${location.protocol==='https:'?'wss':'ws'}://${location.host}/api/session/${encodeURIComponent(sid)}/events`);
    socket.onmessage=({data})=>{const e=JSON.parse(data);
      if(e.type==='approval')approval(e);
      if(e.type==='approval_closed')document.getElementById('approval_'+e.id)?.remove();
      if(e.type==='tool_result'){const p=document.createElement('p');p.textContent=e.result.status==='created'?`Demo-Ticket gespeichert: ${e.result.ticket_id}`:`Ticketstatus: ${e.result.status}`;$('results').append(p);}
      if(e.type==='backend_disconnected'){$('error').textContent='Aufgabenverbindung unterbrochen. Gespräch wird beendet.';stop();}
      if(e.type==='app_closed'){setStatus(e.usage_complete?'Gespräch abgeschlossen':'Gespräch beendet; finale Verbrauchsdaten fehlen');cleanup();}
    };
    let timeout;
    try{await Promise.race([ready,new Promise((_,reject)=>{timeout=setTimeout(()=>reject(new Error('Voice-Session wurde nicht rechtzeitig bereit.')),15000);})]);}finally{clearTimeout(timeout);}
    if(attempt!==generation)return;
    setStatus('Verbunden. Du kannst jetzt sprechen.');document.body.classList.add('live');
    $('rating-fields').disabled=!lastTest;
    for(const id of ['mute','stop','revise'])$(id).disabled=false;
    started=Date.now();timer=setInterval(()=>{const seconds=Math.floor((Date.now()-started)/1000);$('timer').textContent=`${String(Math.floor(seconds/60)).padStart(2,'0')}:${String(seconds%60).padStart(2,'0')}`;},1000);
  }catch(e){$('error').textContent=e.name==='NotAllowedError'?'Mikrofonzugriff wurde abgelehnt. Bitte in den Browsereinstellungen erlauben.':e.message;
    if(sid)try{await action({action:'close'});}catch{} lastTest=null;$('rating-fields').disabled=true;cleanup();setStatus('Verbindung konnte nicht gestartet werden');}
};
async function stop(){
  if(closing)return;closing=true;$('stop').disabled=true;setStatus('Gespräch wird beendet …');
  mic?.getTracks().forEach(t=>t.enabled=false);
  if(sid){try{await action({action:'close'});}catch(e){$('error').textContent=e.message;}}
  cleanup();setStatus('Gespräch beendet');
}
$('stop').onclick=stop;
$('mute').onclick=()=>{muted=!muted;mic?.getAudioTracks().forEach(t=>t.enabled=!muted);$('mute').textContent=muted?'Mikrofon einschalten':'Mikrofon ausschalten';};
$('revise').onclick=async()=>{try{await action({action:'revise'});$('approvals').replaceChildren();setStatus('Aufgabe zurückgesetzt. Beschreibe dein neues Anliegen.');}catch(e){$('error').textContent=e.message;}};
$('login').onsubmit=async e=>{e.preventDefault();try{await api('/api/login',{password:$('password').value});$('login').hidden=true;$('start').disabled=false;await loadStats();}catch(err){$('error').textContent=err.message;}};
window.addEventListener('pagehide',()=>{if(sid)navigator.sendBeacon(`/api/session/${encodeURIComponent(sid)}/action`,new Blob([JSON.stringify({action:'close'})],{type:'application/json'}));mic?.getTracks().forEach(t=>t.stop());});
function renderStats(){
  if(!allStats)return;
  const rows=allStats.rows.filter(r=>r.language===$('stats-language').value);
  $('stats-summary').textContent=`${allStats.testers} verschiedene Testcodes insgesamt · ${allStats.ratings} Bewertungen · ${rows.length} bewertete Stimmen in dieser Sprache`;
  $('stats-caption').textContent=`Testversion ${allStats.version} · neueste Bewertung pro Testcode`;
  $('stats-rows').replaceChildren();
  if(!rows.length){const tr=document.createElement('tr'),td=document.createElement('td');td.colSpan=6;td.textContent='Noch keine Bewertungen in dieser Sprache.';tr.append(td);$('stats-rows').append(tr);return;}
  for(const row of rows){const tr=document.createElement('tr');
    for(const key of ['voice','testers','pronunciation','clarity','naturalness','overall']){
      const td=document.createElement('td');td.textContent=typeof row[key]==='number'&&key!=='testers'?row[key].toLocaleString('de-DE',{minimumFractionDigits:2,maximumFractionDigits:2}):row[key];tr.append(td);
    }$('stats-rows').append(tr);
  }
}
async function loadStats(){
  if(!ratingsEnabled){$('stats-summary').textContent='Gemeinsame Bewertungen werden verfügbar, sobald die dauerhafte Datenbank eingerichtet ist.';return;}
  try{const version=$('stats-version').value;const r=await fetch('/api/ratings'+(version?'?version='+encodeURIComponent(version):''));if(!r.ok)throw new Error(r.status===401?'Bitte anmelden, um die Statistik zu sehen.':'Statistik konnte nicht geladen werden.');allStats=await r.json();
    $('stats-version').replaceChildren(...allStats.versions.map(v=>{const o=document.createElement('option');o.value=v;o.textContent=v+(v===config.version?' (aktuell)':'');return o;}));
    $('stats-version').value=allStats.version;renderStats();}
  catch(e){$('stats-summary').textContent=e.message;}
}
$('rating-form').onsubmit=async e=>{
  e.preventDefault();if(!lastTest)return;const test=lastTest;$('rating-fields').disabled=true;
  try{await api('/api/ratings',{test_id:test.test_id,test_token:test.test_token,
    pronunciation:Number($('pronunciation').value),clarity:Number($('clarity').value),
    naturalness:Number($('naturalness').value),comment:$('rating-comment').value});
    $('rating-message').textContent='Gespeichert. Deine neueste Bewertung zählt einmal für diese Stimme und Sprache.';await loadStats();
  }catch(err){$('rating-message').textContent=err.message;}
  finally{if(lastTest===test)$('rating-fields').disabled=false;}
};
$('stats-language').onchange=renderStats;$('stats-version').onchange=loadStats;$('refresh-stats').onclick=loadStats;
const config=await fetch('/api/config').then(r=>r.json());ratingsEnabled=config.ratings_enabled;
$('voice-select').replaceChildren(...config.voices.map(v=>{const o=document.createElement('option');o.value=v;o.textContent=v[0].toUpperCase()+v.slice(1);return o;}));
for(const id of ['voice-select','language-select']){const value=saved('activi-'+id);if([...$(id).options].some(o=>o.value===value))$(id).value=value;}
$('tester-code').value=saved('activi-tester-code')||'tester-'+crypto.randomUUID().slice(0,12);remember('activi-tester-code',$('tester-code').value);
for(const id of settingIds)$(id).onchange=()=>remember('activi-'+id,$(id).value);
if(config.password_required){$('login').hidden=false;$('start').disabled=true;}else{await api('/api/login',{});}
if(!config.durable_ratings&&ratingsEnabled)$('rating-message').textContent='Lokaler Testbetrieb: Bewertungen sind nur auf diesem Server gespeichert.';
await loadStats();
