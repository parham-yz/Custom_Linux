'use strict';
const $ = id => document.getElementById(id);
let state = {}, messages = [], lastMessages = '', lastJobs = '', lastUpdates = '', loadedRun = '';
const busy = () => state.active && !['completed','failed','cancelled'].includes(state.active.status);
async function request(path, body) {
  const response = await fetch('/api/' + path, body === undefined ? {} : {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
  const value = await response.json();
  if (!response.ok) throw new Error(value.error || 'Please try again.');
  return value;
}
function error(message) { $('error').textContent = message; $('error').hidden = !message; }
function el(tag, text, cls) { const n=document.createElement(tag); if(text!==undefined)n.textContent=text; if(cls)n.className=cls; return n; }
function button(text, fn) { const b=el('button',text,'text-button'); b.onclick=async()=>{b.disabled=true;try{await fn();await refresh();}catch(e){error(e.message);}finally{b.disabled=false;}}; return b; }
function empty(node, title, body) { node.replaceChildren();const e=el('div',undefined,'empty');e.append(el('strong',title),el('span',body));node.append(e); }
function date(value) { return new Intl.DateTimeFormat('en-GB',{dateStyle:'medium',timeStyle:'short',timeZone:'Europe/Berlin'}).format(new Date(value)); }
async function view(name) {
  document.querySelectorAll('.view').forEach(n=>n.hidden=n.id!==name);
  document.querySelectorAll('.nav').forEach(n=>{n.classList.toggle('active',n.dataset.view===name);n.removeAttribute('aria-current');if(n.dataset.view===name)n.setAttribute('aria-current','page');});
  document.body.classList.toggle('chat-focus',name==='conversation');
  if(name==='memory')try{const m=await request('memory');$('user-memory').textContent=m['USER.md'].replaceAll('\n§\n','\n\n')||'Your preferences will appear here as Hermes learns about you.';$('agent-memory').textContent=m['MEMORY.md'].replaceAll('\n§\n','\n\n')||'Nothing stored here yet. You can ask Hermes to remember something.';}catch(e){error(e.message);}
  if(name==='conversation')$('message').focus();
}
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>view(b.dataset.view));
function renderMessages() {
  const rows=messages.map(m=>({role:m.role,content:m.content}));
  if(busy()) {rows.push({role:'user',content:state.active.message}); if(state.active.text)rows.push({role:'assistant',content:state.active.text});}
  const serial=JSON.stringify(rows);if(serial===lastMessages)return;lastMessages=serial;
  const log=$('messages'), bottom=log.scrollHeight-log.scrollTop-log.clientHeight<90;
  log.replaceChildren();
  if(!rows.length){const p=el('div',undefined,'chat-empty');p.append(el('strong','Hello. I’m Hermes.'),el('span','Tell me what you want to remember, what needs following up, or where you could use a hand.'));log.append(p);}
  for(const m of rows){const node=el('article',undefined,'message '+m.role);node.append(el('div',m.role==='user'?'YOU':'HERMES','who'),el('div',m.content,'content'));log.append(node);}
  if(bottom)log.scrollTop=log.scrollHeight;
}
function renderJobs() {
  const jobs=(state.jobs||[]).filter(j=>j.enabled||j.state==='paused').sort((a,b)=>(a.next_run_at||'z').localeCompare(b.next_run_at||'z'));
  const serial=JSON.stringify(jobs);if(serial===lastJobs)return;lastJobs=serial;
  const node=$('jobs');node.replaceChildren();
  if(!jobs.length)return empty(node,'A little more headspace.','Add a reminder, or ask Hermes to remember something for later. Your calendar will appear after account setup.');
  for(const job of jobs){const n=el('article',undefined,'item');n.append(el('div',job.name,'item-title'),el('div',job.state==='paused'?'Paused':job.next_run_at?date(job.next_run_at):job.schedule_display,'item-date'));
    const controls=el('div',undefined,'item-actions');controls.append(button(job.state==='paused'?'Resume':'Pause',()=>request('job',{id:job.id,action:job.state==='paused'?'resume':'pause'})),button('Remove',async()=>{if(confirm('Remove this reminder?\n'+job.name))await request('job',{id:job.id,action:'delete'});}));n.append(controls);node.append(n);}
}
function renderUpdates() {
  const updates=(state.updates||[]).filter(i=>!i.read && (!i.snoozed_until||i.snoozed_until*1000<=Date.now()));
  $('attention-count').textContent=updates.length;
  const serial=JSON.stringify(updates);if(serial===lastUpdates)return;lastUpdates=serial;
  const node=$('updates');node.replaceChildren();
  if(!updates.length)return empty(node,'Nothing waiting here.','Scheduled reminders and follow-ups appear here. Email has not been connected yet.');
  for(const item of updates){const n=el('article',undefined,'item');n.append(el('div',item.title,'item-title'),el('div',item.body,'item-body'),el('div',date(item.time*1000),'item-date'));const c=el('div',undefined,'item-actions');c.append(button('Handled',()=>request('update',{id:item.id,action:'read'})),button('Tomorrow',()=>request('update',{id:item.id,action:'snooze'})));n.append(c);node.append(n);}
}
async function loadMessages(){try{messages=(await request('messages')).messages;renderMessages();}catch(e){error(e.message);}}
async function refresh(){
  state=await request('state');
  for(const [key,value] of Object.entries(state.palette||{}))document.documentElement.style.setProperty('--'+key,value);
  const bg=state.palette?.bg;if(bg){const n=parseInt(bg.slice(1,3),16);document.documentElement.style.colorScheme=n>150?'light':'dark';}
  $('health').textContent=!state.online?'Reconnecting':busy()?'Working with you':'Ready';$('health').classList.toggle('offline',!state.online);
  $('welcome').hidden=state.introduced;$('pause').textContent=state.paused?'Resume alerts':'Pause alerts';
  $('alert-status').textContent=state.paused?'Alerts paused':state.quiet?'Quiet hours · Alerts waiting until morning':'Alerts on · Quiet hours 22:00–08:00';
  $('send').disabled=!!busy()||!state.online;$('stop').hidden=!busy();
  $('working').hidden=!busy();$('working').textContent=state.active?.approval?'Waiting for your decision':state.active?.tool?'Working · '+state.active.tool.replaceAll('_',' '):'Thinking…';
  $('approval').hidden=!state.active?.approval;$('approval-detail').textContent=state.active?.approval?.command||'';
  $('allow').hidden=!(state.active?.approval?.choices||[]).includes('once');
  if(state.active?.status==='failed')error(state.active.error||'Hermes could not finish this response. Try again.');
  const finished=state.active&&!busy()?state.active.id+state.active.status:'';
  if(finished&&finished!==loadedRun){loadedRun=finished;await loadMessages();}
  renderJobs();renderUpdates();renderMessages();
}
async function send(text){error('');await request('chat',{message:text});$('message').value='';await refresh();$('messages').scrollTop=$('messages').scrollHeight;}
$('chat-form').onsubmit=async e=>{e.preventDefault();const text=$('message').value.trim();if(!text||busy())return;$('send').disabled=true;try{await send(text);}catch(e){error(e.message);$('send').disabled=false;}};
$('message').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey&&!e.isComposing){e.preventDefault();$('chat-form').requestSubmit();}};
$('stop').onclick=async()=>{try{await request('stop',{});await refresh();}catch(e){error(e.message);}};
$('pause').onclick=async()=>{try{await request('pause',{paused:!state.paused});await refresh();}catch(e){error(e.message);}};
for(const [id,choice] of [['allow','once'],['deny','deny']])$(id).onclick=async()=>{try{await request('approval',{choice});await refresh();}catch(e){error(e.message);}};
async function prompt(text){await view('conversation');$('message').value=text;$('message').focus();}
$('intro').onclick=async()=>{await view('conversation');try{await send('Let’s get acquainted. Start from what you already know about me, then ask one useful question at a time about what I need help keeping track of.');}catch(e){error(e.message);}};
$('plan-day').onclick=()=>prompt('Help me plan my day from what we know and the commitments I have shared. Be clear about accounts that are not connected.');
$('review-memory').onclick=()=>prompt('Let’s review what you remember about me and correct anything that is out of date.');
document.querySelectorAll('.setup').forEach(b=>b.onclick=()=>prompt('Help me plan connecting my '+b.dataset.account+'. Start by asking which account I want to use. Remember our agreed permissions.'));
$('add-reminder').onclick=()=>{const t=new Date(Date.now()+3600000);t.setMinutes(Math.ceil(t.getMinutes()/5)*5,0,0);const parts=Object.fromEntries(new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Berlin',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(t).map(p=>[p.type,p.value]));$('reminder-time').value=`${parts.year}-${parts.month}-${parts.day}T${parts.hour}:${parts.minute}`;$('reminder-dialog').showModal();$('reminder-text').focus();};
$('close-dialog').onclick=()=>$('reminder-dialog').close();
$('reminder-dialog').onclick=e=>{if(e.target===$('reminder-dialog')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}};
$('reminder-form').onsubmit=async e=>{e.preventDefault();const b=e.submitter;b.disabled=true;$('reminder-error').hidden=true;try{await request('reminders',{text:$('reminder-text').value,when:$('reminder-time').value});$('reminder-dialog').close();$('reminder-text').value='';await refresh();}catch(e){$('reminder-error').textContent=e.message;$('reminder-error').hidden=false;}finally{b.disabled=false;}};
const hour=Number(new Intl.DateTimeFormat('en-GB',{timeZone:'Europe/Berlin',hour:'numeric',hourCycle:'h23'}).format(new Date()));
$('greeting').textContent=(hour<12?'Good morning.':hour<18?'Good afternoon.':'Good evening.');
$('date').textContent=new Intl.DateTimeFormat('en-GB',{weekday:'short',day:'numeric',month:'short',timeZone:'Europe/Berlin'}).format(new Date());
async function poll(){try{await refresh();}catch(e){$('health').textContent='Reconnecting';$('health').classList.add('offline');}setTimeout(poll,1500);}
loadMessages();poll();
