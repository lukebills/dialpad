'use strict';
const $ = id => document.getElementById(id);
const token = location.hash.slice(1) || sessionStorage.getItem('dialpad-token') || '';
sessionStorage.setItem('dialpad-token', token);
history.replaceState(null, '', '/');
const controls = ['key1','key2','key3','key4','key5','key6','dial_ccw','dial_press','dial_cw'];
const shortcut = (key, modifiers=[]) => ({type:'shortcut',key,modifiers});
const names = {key1:'Key 1',key2:'Key 2',key3:'Key 3',key4:'Key 4',key5:'Key 5',key6:'Key 6',dial_ccw:'Dial · turn left',dial_press:'Dial · press',dial_cw:'Dial · turn right'};
let selected='key1', profile, devices=[], preview=null, recording=false, busy=false, revision=0;
let runtime=null, runtimePolling=false, cyclePending=false, savedFingerprint='';
const keyNames = ['NONE',...'ABCDEFGHIJKLMNOPQRSTUVWXYZ',...'1234567890', 'ENTER','ESCAPE','TAB','SPACE','BACKSPACE','DELETE','UP','DOWN','LEFT','RIGHT','HOME','END','PAGEUP','PAGEDOWN','MINUS','EQUAL','LEFTBRACKET','RIGHTBRACKET','BACKSLASH','SEMICOLON','QUOTE','GRAVE','COMMA','DOT','SLASH',...Array.from({length:24},(_,i)=>`F${i+1}`)];
const actions = {mouse:['wheel_up','wheel_down','middle_click','left_click','right_click'],media:['volume_up','volume_down','mute','play_pause','next','previous','stop','brightness_up','brightness_down']};
function option(value, text=value){return new Option(text,value);}
keyNames.forEach(k=>$('key').add(option(k,k==='NONE'?'No key · modifiers only':k)));
function message(text,error=false){$('message').textContent=text;$('message').className=error?'error':'';}
async function api(path,body){
 const response=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
 const result=await response.json();if(!response.ok)throw new Error(result.error||'Request failed.');return result;
}
function describe(action){if(action.type==='shortcut')return [...action.modifiers.map(m=>({cmd:'⌘ / Win',alt:'⌥ / Alt',ctrl:'Ctrl',shift:'Shift'}[m]||m)),...(action.key==='NONE'?[]:[action.key])].join(' + ');return (action.action||action.type).replaceAll('_',' ');}
function preset(){
 const mac=$('platform').value==='mac',kind=$('preset').value;
 const labels={key1:'Wispr Flow',key2:'Enter',key3:'Escape',key4:'New line',key5:'Paste',key6:kind==='claude'?'Transcript':kind==='desktop'?'Review':'Tab',dial_ccw:'Scroll up',dial_press:'Tab',dial_cw:'Scroll down'};
 const bindings={key1:shortcut(mac?'NONE':'SPACE',mac?['ctrl','cmd','alt']:['ctrl','cmd']),key2:shortcut('ENTER'),key3:shortcut('ESCAPE'),key4:shortcut('J',['ctrl']),key5:shortcut('V',mac?['cmd']:['ctrl','shift']),key6:kind==='claude'?shortcut('O',['ctrl']):shortcut('TAB'),dial_ccw:{type:'mouse',action:'wheel_up'},dial_press:shortcut('TAB'),dial_cw:{type:'mouse',action:'wheel_down'}};
 if(kind==='desktop'){bindings.key4=shortcut('ENTER',['shift']);bindings.key5=shortcut('V',mac?['cmd']:['ctrl']);bindings.key6=shortcut('G',['ctrl','shift']);}
 profile={version:1,name:(kind==='claude'?'Claude Code':kind==='codex'?'Codex terminal':'Codex desktop')+' · '+(mac?'Mac':'Windows'),layer:1,labels,bindings};
 configureFlow();
 render();message('Starting layout loaded. Nothing has been written to your keypad.');
}
function configureFlow(){
 const mac=$('platform').value==='mac',ptt=$('flow-mode').value==='ptt';
 profile.bindings.key1=shortcut(mac||ptt?'NONE':'SPACE',mac?(ptt?['ctrl','alt']:['ctrl','cmd','alt']):['ctrl','cmd']);
 profile.labels.key1=ptt?'Flow · hold to talk':'Wispr Flow';
 $('preset-note').textContent=mac?(ptt?'Your Flow push-to-talk shortcut is Control + Option (or Apple Fn). This key sends Control + Option only. Holding and releasing must be tested on this keypad before relying on push to talk.':'Your Flow hands-free shortcut is Control + Command + Option, with no extra key. Tap to start; tap again to stop and paste. Your other Flow triggers are Fn + Space, middle click, or double-tap Fn.'):(ptt?'Verify Control + Windows is assigned to push to talk in Flow. Holding and releasing must be tested on this keypad.':'Verify Control + Windows + Space is assigned to Hands-free mode in Flow. Tap to start; tap again to stop and paste.');
}
$('flow-mode').onchange=()=>{configureFlow();render();message('Flow binding updated in the editor only.');};
function invalidate(){preview=null;revision++;}
function render(){
 $('profile-name').value=profile.name;$('profile-title').textContent=profile.name;$('layer').value=profile.layer;
 $('keys').replaceChildren();
 controls.slice(0,6).forEach((c,i)=>{const b=document.createElement('button');b.className='key'+(selected===c?' selected':'');b.dataset.control=c;
 for(const [cls,text] of [['number','0'+(i+1)],['key-label',profile.labels[c]||names[c]],['key-shortcut',describe(profile.bindings[c])]]){const s=document.createElement('span');s.className=cls;s.textContent=text;b.append(s);}b.onclick=()=>select(c);$('keys').append(b);});
 document.querySelectorAll('.rotations button').forEach(b=>b.classList.toggle('selected',b.dataset.control===selected));$('dial-face').classList.toggle('selected',selected==='dial_press');
 editor();invalidate();
}
function select(c){selected=c;recording=false;render();}
function editor(){
 const a=profile.bindings[selected];$('control-title').textContent=names[selected];$('label').value=profile.labels[selected]||'';$('type').value=a.type;
 $('shortcut-fields').hidden=a.type!=='shortcut';$('action-field').hidden=a.type==='shortcut';
 if(a.type==='shortcut'){$('key').value=a.key.toUpperCase();document.querySelectorAll('.modifiers input').forEach(i=>i.checked=a.modifiers.includes(i.value));}
 else{$('action').replaceChildren();(actions[a.type]||[]).forEach(v=>$('action').add(option(v,v.replaceAll('_',' '))));$('action').value=a.action;}
 $('record').textContent=recording?'Press your shortcut…':'Record shortcut';
}
function updateAction(){
 const type=$('type').value;
 profile.bindings[selected]=type==='shortcut'?shortcut($('key').value,[...document.querySelectorAll('.modifiers input:checked')].map(i=>i.value)):{type,action:$('action').value};render();
}
$('type').onchange=()=>{const type=$('type').value;profile.bindings[selected]=type==='shortcut'?shortcut('ENTER'):{type,action:actions[type][0]};render();};
$('key').onchange=updateAction;$('action').onchange=updateAction;document.querySelectorAll('.modifiers input').forEach(i=>i.onchange=updateAction);
$('label').oninput=()=>{profile.labels[selected]=$('label').value;const label=$('keys').querySelector(`[data-control="${selected}"] .key-label`);if(label)label.textContent=$('label').value;invalidate();};
$('profile-name').oninput=()=>{profile.name=$('profile-name').value;$('profile-title').textContent=profile.name;invalidate();};$('layer').onchange=()=>{profile.layer=Number($('layer').value);invalidate();};
$('load-preset').onclick=preset;$('dial-face').onclick=()=>select('dial_press');document.querySelectorAll('.rotations button').forEach(b=>b.onclick=()=>select(b.dataset.control));
$('record').onclick=()=>{recording=!recording;editor();};
document.addEventListener('keydown',event=>{
 if(!recording)return;
 event.preventDefault();event.stopPropagation();if(['Control','Shift','Alt','Meta'].includes(event.key))return;
 const map={ArrowUp:'UP',ArrowDown:'DOWN',ArrowLeft:'LEFT',ArrowRight:'RIGHT',BracketLeft:'LEFTBRACKET',BracketRight:'RIGHTBRACKET',Backquote:'GRAVE',Period:'DOT'};
 const key=map[event.code]||event.code.replace(/^Key|^Digit/,'').toUpperCase();
 if(!keyNames.includes(key)){message('That key cannot be programmed with this editor. Choose it from the list if available.',true);recording=false;editor();return;}
 profile.bindings[selected]=shortcut(key,[...(event.ctrlKey?['ctrl']:[]),...(event.shiftKey?['shift']:[]),...(event.altKey?['alt']:[]),...(event.metaKey?['cmd']:[])]);recording=false;render();
},true);
async function refresh(){
 try{const data=await api('devices');devices=data.devices;$('device').replaceChildren();
 if(!devices.length){$('device').add(option('','No keypad found'));$('connection').textContent='Keypad not found';$('connection').className='status';}
 else{const candidates=devices.filter(d=>d.programmable);const shown=candidates.length?candidates:devices;shown.forEach((d,i)=>$('device').add(option(d.device_id||d.id,(d.programmable?'Mini keypad':'Input interface')+(shown.length>1?' '+(i+1):'')+' · 1189:8890')));$('connection').textContent=candidates.length?'Keypad connected':'Keypad found · access limited';$('connection').className='status connected';if(!candidates.length)message(shown[0].limitation,true);}
 $('preview').disabled=!devices.some(d=>d.programmable);invalidate();
 }catch(e){$('connection').textContent='Connection unavailable';$('preview').disabled=true;message(e.message,true);}
}
$('refresh').onclick=refresh;$('device').onchange=invalidate;$('scope').onchange=invalidate;
$('export').onclick=async()=>{try{await api('validate',{profile});const url=URL.createObjectURL(new Blob([JSON.stringify(profile,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=profile.name.replace(/[^\w -]/g,'').trim()+'.dialpad.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);message('Profile exported. Keep it to restore these app settings later.');}catch(e){message(e.message,true);}};
$('import').onclick=()=>$('file').click();$('file').onchange=async()=>{try{const file=$('file').files[0];if(!file)return;if(file.size>65536)throw new Error('Profile is too large.');const imported=JSON.parse(await file.text());await api('validate',{profile:imported});if(Object.values(imported.bindings).some(a=>!['shortcut','mouse','media'].includes(a.type)))throw new Error('This editor supports single shortcuts, mouse and media actions only.');imported.labels=Object.fromEntries(controls.map(c=>[c,typeof imported.labels?.[c]==='string'?imported.labels[c].slice(0,32):names[c]]));for(const a of Object.values(imported.bindings)){if(a.type==='shortcut'){a.key=a.key.toUpperCase();a.modifiers=(a.modifiers||[]).map(m=>m.toLowerCase());if(a.modifiers.some(m=>!['ctrl','shift','alt','cmd'].includes(m))||!keyNames.includes(a.key))throw new Error('Profile uses a key or modifier this editor cannot display.');}else if(a.type==='mouse' && a.modifiers?.length)throw new Error('Mouse modifiers are not supported by this editor. Remove them before importing.');else if(!actions[a.type].includes(a.action))throw new Error('Profile uses an action this editor cannot display.');}profile=imported;render();$('preset-note').textContent='Imported profile. Check that its dictation and terminal shortcuts match this computer.';message('Profile imported. Nothing has been written to the keypad.');}catch(e){message(e.message,true);}finally{$('file').value='';}};
$('preview').onclick=async()=>{try{const selectedControls=$('scope').value==='all'?[...controls]:[selected];const snapshot=structuredClone(profile), currentRevision=revision;const result=await api('preview',{profile:snapshot,controls:selectedControls,device_id:$('device').value});if(revision!==currentRevision){message('Settings changed while preparing the preview. Review them again.');return;}preview=result;$('review-content').textContent='Layer '+snapshot.layer+'\n\n'+selectedControls.map(c=>`${names[c]}  →  ${describe(snapshot.bindings[c])}`).join('\n');$('review').showModal();}catch(e){message(e.message,true);}};
$('apply').onclick=async()=>{if(!preview||busy)return;busy=true;$('apply').disabled=true;$('apply').textContent='Applying…';try{const result=await api('apply',{nonce:preview.nonce});message(result.result.message||'Transfer completed. Test your physical controls below.');}catch(e){message('Apply failed: '+e.message,true);}finally{busy=false;preview=null;$('apply').disabled=false;$('apply').textContent='Apply to keypad';$('review').close();refreshRuntime();}};
$('review').addEventListener('cancel',e=>{if(busy)e.preventDefault();});
$('test-input').onkeydown=e=>{$('test-event').textContent='Received: '+[...(e.ctrlKey?['Ctrl']:[]),...(e.altKey?['Alt']:[]),...(e.metaKey?['Command / Windows']:[]),...(e.shiftKey?['Shift']:[]),e.key].join(' + ');};
$('test-input').onwheel=e=>{$('test-event').textContent=e.deltaY<0?'Received: scroll up':'Received: scroll down';};
$('quit').onclick=async()=>{try{await api('quit',{});document.querySelector('main').replaceChildren(Object.assign(document.createElement('p'),{textContent:'Dialpad has quit. You can close this tab.'}));$('connection').textContent='Disconnected';}catch(e){message(e.message,true);}};
function showRuntime(data){
 runtime=data;
 $('save-setup').disabled=false;
 const fingerprint=JSON.stringify(data.profiles);
 if(fingerprint!==savedFingerprint){
 savedFingerprint=fingerprint;
 const previous=$('saved-setup').value;
 $('saved-setup').replaceChildren();
 data.profiles.forEach((p,i)=>$('saved-setup').add(option(String(i),`${i+1}. ${p.name}`)));
 if(!data.profiles.length)$('saved-setup').add(option('','No saved setups'));
 else if([...$('saved-setup').options].some(o=>o.value===previous))$('saved-setup').value=previous;
 }
 $('edit-setup').disabled=$('remove-setup').disabled=!data.profiles.length;
 $('enable-cycle').disabled=!data.ready||data.profiles.length<2;
 $('disable-cycle').disabled=!data.enabled;
 $('next-setup').disabled=!data.enabled||cyclePending;
 $('live-title').textContent=data.enabled?'◉ '+data.current.name:'◉ Setup cycling is off';
 $('live-keys').replaceChildren();
 if(data.current){controls.forEach(c=>{const row=document.createElement('div');row.textContent=(data.current.labels?.[c]||names[c])+' · '+describe(data.current.bindings[c]);$('live-keys').append(row);});}
 else $('live-keys').textContent=data.error||'Enable saved setups below to show the active layout. The editor may contain unapplied changes.';
 $('cycle-note').textContent=data.error||(data.enabled?'Cycling is on: '+data.cycle_names.join(' → ')+'. The layout above shows the last successful transfer; test the physical keys.':data.ready?'Desktop dial shortcut ready. Save at least two setups, then review and enable.':'Open the packaged desktop app to enable the global dial shortcut.');
}
async function refreshRuntime(){
 if(runtimePolling)return;runtimePolling=true;
 try{showRuntime(await api('setups'));}catch(e){$('cycle-note').textContent=e.message;$('live-title').textContent='◉ App disconnected';$('next-setup').disabled=true;$('enable-cycle').disabled=true;$('save-setup').disabled=true;}finally{runtimePolling=false;}
}
$('save-setup').onclick=async()=>{if(!runtime)return;try{const snapshot=structuredClone(profile);await api('validate',{profile:snapshot});const profiles=structuredClone(runtime.profiles);const index=profiles.findIndex(p=>p.name===snapshot.name);if(index<0)profiles.push(snapshot);else profiles[index]=snapshot;showRuntime(await api('setups/save',{profiles}));message('Setup saved on this computer. '+(runtime.enabled?'Review and enable again to use these edits in the cycle.':'Save another layout to build your cycle.'));}catch(e){message(e.message,true);}};
$('edit-setup').onclick=()=>{const saved=runtime?.profiles[Number($('saved-setup').value)];if(saved){profile=structuredClone(saved);profile.labels=profile.labels||{};render();message('Saved setup loaded into the editor. Save current setup after editing.');}};
$('remove-setup').onclick=async()=>{try{const profiles=structuredClone(runtime.profiles);profiles.splice(Number($('saved-setup').value),1);showRuntime(await api('setups/save',{profiles}));message('Saved setup removed. An enabled cycle keeps its reviewed layouts until stopped or enabled again.');}catch(e){message(e.message,true);}};
$('enable-cycle').onclick=async()=>{try{const result=await api('setups/preview',{device_id:$('device').value});preview=result;$('review-content').textContent='Enable this cycle on hardware layer '+result.layer+'?\n\n'+result.profiles.map((p,i)=>`${i+1}. ${p.name}\n`+controls.map(c=>`${names[c]} → ${describe(p.bindings[c])}`).join('\n')).join('\n\n')+'\n\nApply sends the first setup now. Each dial press (F18) sends the next setup, replacing all nine bindings. The app must stay running. F18 on any keyboard also triggers this cycle. Firmware persistence and write endurance are unknown; this is intended for occasional setup changes.';$('review').showModal();}catch(e){message(e.message,true);}};
$('disable-cycle').onclick=async()=>{try{showRuntime(await api('setups/disable',{}));message('Cycling stopped. The keypad keeps its last bindings. Apply a normal layout to restore the dial press.');}catch(e){message(e.message,true);}};
$('next-setup').onclick=async()=>{if(cyclePending)return;cyclePending=true;$('next-setup').disabled=true;try{showRuntime(await api('setups/cycle',{}));}catch(e){message(e.message,true);}finally{cyclePending=false;refreshRuntime();}};
$('platform').value=/Mac/.test(navigator.platform)?'mac':'windows';preset();refresh();refreshRuntime();setInterval(refreshRuntime,1000);
