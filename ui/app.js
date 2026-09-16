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
let starterLayouts={}, cycleOrder=[], libraryFingerprint='', devicePolling=false, deviceFingerprint='';
const keyNames = ['NONE',...'ABCDEFGHIJKLMNOPQRSTUVWXYZ',...'1234567890', 'ENTER','ESCAPE','TAB','SPACE','CAPSLOCK','BACKSPACE','DELETE','UP','DOWN','LEFT','RIGHT','HOME','END','PAGEUP','PAGEDOWN','MINUS','EQUAL','LEFTBRACKET','RIGHTBRACKET','BACKSLASH','SEMICOLON','QUOTE','GRAVE','COMMA','DOT','SLASH',...Array.from({length:24},(_,i)=>`F${i+1}`)];
const actions = {mouse:['wheel_up','wheel_down','middle_click','left_click','right_click'],media:['volume_up','volume_down','mute','play_pause','next','previous','stop','brightness_up','brightness_down']};
function option(value, text=value){return new Option(text,value);}
keyNames.forEach(k=>$('key').add(option(k,k==='NONE'?'No key · modifiers only':k)));
function message(text,error=false){$('message').textContent=text;$('message').className=error?'error':'';}
async function api(path,body){
 const response=await fetch('/api/'+path,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+token,...(body?{'Content-Type':'application/json'}:{})},...(body?{body:JSON.stringify(body)}:{})});
 const result=await response.json();if(!response.ok)throw new Error(result.error||'Request failed.');return result;
}
function describe(action){if(action.type==='multi_tap')return ['single','double','triple'].map((tap,i)=>(i+1)+'× '+describe(action[tap])).join(' · ');if(action.type==='clipboard')return action.action[0].toUpperCase()+action.action.slice(1)+(action.formatting==='formatted'?'':' · plain');if(action.type==='copy_paste')return 'Copy ⇄ Paste';if(action.type==='shortcut')return [...action.modifiers.map(m=>({cmd:'⌘ / Win',alt:'⌥ / Alt',ctrl:'Ctrl',shift:'Shift'}[m]||m)),...(action.key==='NONE'?[]:[action.key])].join(' + ');return (action.action||action.type).replaceAll('_',' ');}
function preset(){
 const mac=$('platform').value==='mac',kind=$('preset').value;
 if(['media','web','word','mail'].includes(kind)){
  const template=starterLayouts[$('platform').value]?.[kind];
  if(!template){message('Apple Mail is available on Mac. Choose Mac to load that layout.',true);return;}
  profile=structuredClone(template);
  if(kind==='word'||kind==='mail')configureFlow();
  render();message('Starting layout loaded. Changes save automatically; Apply updates the keypad.');return;
 }
 const labels={key1:'Wispr Flow',key2:'Enter',key3:'Escape',key4:'New line',key5:'Paste',key6:kind==='claude'?'Transcript':kind==='desktop'?'Review':'Tab',dial_ccw:'Arrow up',dial_press:'Tab',dial_cw:'Arrow down'};
 const bindings={key1:shortcut(mac?'NONE':'SPACE',mac?['ctrl','cmd','alt']:['ctrl','cmd']),key2:shortcut('ENTER'),key3:shortcut('ESCAPE'),key4:shortcut('J',['ctrl']),key5:shortcut('V',mac?['cmd']:['ctrl','shift']),key6:kind==='claude'?shortcut('O',['ctrl']):shortcut('TAB'),dial_ccw:shortcut('UP'),dial_press:shortcut('TAB'),dial_cw:shortcut('DOWN')};
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
function invalidate(){preview=null;revision++;scheduleSave();}
function render(){
 $('flow-setting').hidden=['media','web'].some(kind=>profile.starter_id?.startsWith(kind+'-'));
 if(profile.note)$('preset-note').textContent=profile.note;
 $('profile-name').value=profile.name;$('layer').value=profile.layer;
 $('keys').replaceChildren();
 controls.slice(0,6).forEach((c,i)=>{const b=document.createElement('button');b.className='key'+(selected===c?' selected':'');b.dataset.control=c;b.title=describe(profile.bindings[c]);
 for(const [cls,text] of [['number','0'+(i+1)],['key-label',profile.labels[c]||names[c]],['key-shortcut',describe(profile.bindings[c])]]){const s=document.createElement('span');s.className=cls;s.textContent=text;b.append(s);}b.onclick=()=>select(c);$('keys').append(b);});
 document.querySelectorAll('.rotations button').forEach(b=>{b.classList.toggle('selected',b.dataset.control===selected);b.querySelector('span').textContent=profile.labels[b.dataset.control]||describe(profile.bindings[b.dataset.control]);b.title=describe(profile.bindings[b.dataset.control]);});$('dial-face').classList.toggle('selected',selected==='dial_press');
 editor();invalidate();
}
function select(c){selected=c;recording=false;render();openEditor();}
function editor(){
 const a=profile.bindings[selected];$('multi-tap-options').hidden=a.type!=='multi_tap';if(a.type==='multi_tap')renderTapEditor(a);$('control-title').textContent=names[selected];$('label').value=profile.labels[selected]||'';$('type').value=a.type;
 $('shortcut-fields').hidden=a.type!=='shortcut';$('action-field').hidden=['shortcut','copy_paste','multi_tap'].includes(a.type);$('toggle-note').hidden=a.type!=='copy_paste';$('clipboard-options').hidden=a.type!=='copy_paste';
 if(a.type==='copy_paste'){$('copy-format').value=a.formatting||'plain';const reset=String(a.reset_seconds??10);if(![...$('copy-reset').options].some(o=>o.value===reset))$('copy-reset').add(option(reset,reset+' seconds'));$('copy-reset').value=reset;$('copy-double').value=String(a.double_tap_cut??true);}
 if(a.type==='shortcut'){$('key').value=a.key.toUpperCase();document.querySelectorAll('.modifiers input').forEach(i=>i.checked=a.modifiers.includes(i.value));}
 else{$('action').replaceChildren();(actions[a.type]||[]).forEach(v=>$('action').add(option(v,v.replaceAll('_',' '))));$('action').value=a.action;}
 $('record').textContent=recording?'Press your shortcut…':'Record shortcut';
}
function updateAction(){
 const type=$('type').value;
 profile.bindings[selected]=type==='shortcut'?shortcut($('key').value,[...document.querySelectorAll('.modifiers input:checked')].map(i=>i.value)):{type,action:$('action').value};render();
}
function clipboardLeaf(action, modifiers=[$('platform').value==='mac'?'cmd':'ctrl'], formatting='plain'){return {type:'clipboard',action,formatting,modifiers:[...modifiers]};}
function newMultiTap(previous){const existing=previous?.modifiers||[],modifiers=['cmd','ctrl','ctrl,shift'].includes([...existing].sort().join(','))?existing:[$('platform').value==='mac'?'cmd':'ctrl'];return {type:'multi_tap',window_ms:350,single:clipboardLeaf('copy',modifiers),double:clipboardLeaf('paste',modifiers),triple:clipboardLeaf('cut',modifiers)};}
$('type').onchange=()=>{const type=$('type').value;if(['copy_paste','multi_tap'].includes(type)&&!selected.startsWith('key')){message('Choose one of the six keys for multi-tap or Copy / Paste.',true);editor();return;}const previous=profile.bindings[selected];profile.bindings[selected]=type==='multi_tap'?newMultiTap(previous.type==='copy_paste'||(previous.type==='shortcut'&&previous.key==='V')?previous:null):type==='copy_paste'?{type,modifiers:$('platform').value==='mac'?['cmd']:['ctrl']}:type==='shortcut'?shortcut('ENTER'):{type,action:actions[type][0]};if(type==='multi_tap')profile.labels[selected]='Copy / Paste / Cut';if(type==='copy_paste')profile.labels[selected]='Copy / Paste';render();};
$('convert-multi').onclick=()=>{const previous=profile.bindings[selected];const multi=newMultiTap(previous);for(const tap of ['single','double','triple'])multi[tap].formatting=previous.formatting||'plain';profile.bindings[selected]=multi;profile.labels[selected]='Copy / Paste / Cut';render();message('Draft converted to single Copy, double Paste, triple Cut. Changes save automatically. Apply the cycle to use it.');};
$('tap-window').onchange=()=>{const ms=Number($('tap-window').value);if(!Number.isInteger(ms)||ms<100||ms>1000){message('Choose a whole number from 100 to 1000 milliseconds.',true);$('tap-window').value=profile.bindings[selected].window_ms??350;return;}profile.bindings[selected].window_ms=ms;invalidate();};
function renderTapEditor(binding){
 $('tap-window').value=binding.window_ms??350;$('tap-actions').replaceChildren();
 const addSelect=(box,id,label,values,value,change)=>{const field=document.createElement('label');field.textContent=label;const select=document.createElement('select');select.id=id;for(const item of values){const [v,text]=Array.isArray(item)?item:[item,item.replaceAll('_',' ')];select.add(option(v,text));}select.value=value;select.onchange=()=>{change(select.value);render();};field.append(select);box.append(field);return select;};
 for(const [index,tap] of ['single','double','triple'].entries()){
  const leaf=binding[tap],box=document.createElement('fieldset');box.className='tap-editor';const legend=document.createElement('legend');legend.textContent=['Single tap','Double tap','Triple tap'][index];box.append(legend);
  addSelect(box,`tap-${tap}-type`,'Action',[['clipboard','Clipboard'],['shortcut','Keyboard shortcut'],['mouse','Mouse'],['media','Media']],leaf.type,type=>{binding[tap]=type==='clipboard'?clipboardLeaf(['copy','paste','cut'][index]):type==='shortcut'?shortcut('ENTER'):{type,action:actions[type][0]};});
  if(leaf.type==='shortcut'){
   addSelect(box,`tap-${tap}-key`,'Key',keyNames.filter(k=>!/^F(1[3-9]|2[0-4])$/.test(k)).map(k=>[k,k==='NONE'?'No key · modifiers only':k]),leaf.key,key=>leaf.key=key);
   const mods=document.createElement('div');mods.className='tap-modifiers';for(const [value,text] of [['ctrl','Ctrl'],['shift','Shift'],['alt','Alt / ⌥'],['cmd','Win / ⌘']]){const label=document.createElement('label'),input=document.createElement('input');input.type='checkbox';input.value=value;input.id=`tap-${tap}-${value}`;input.checked=leaf.modifiers.includes(value);input.onchange=()=>{leaf.modifiers=[...mods.querySelectorAll('input:checked')].map(i=>i.value);render();};label.append(input,document.createTextNode(text));mods.append(label);}box.append(mods);
  }else{
   const choices=leaf.type==='clipboard'?['copy','paste','cut']:leaf.type==='media'?actions.media.slice(0,6):actions.mouse;
   addSelect(box,`tap-${tap}-action`,'Function',choices,leaf.action,value=>leaf.action=value);
   if(leaf.type==='clipboard'){
    addSelect(box,`tap-${tap}-format`,'Clipboard formatting',[['plain','Plain text'],['formatted','Keep formatting']],leaf.formatting||'plain',value=>leaf.formatting=value);
    addSelect(box,`tap-${tap}-modifiers`,'App shortcut',[['cmd','Command · Mac'],['ctrl','Control · Windows'],['ctrl,shift','Control + Shift · terminal']],(leaf.modifiers||['cmd']).join(','),value=>leaf.modifiers=value.split(','));
   }
  }
  $('tap-actions').append(box);
 }
}
for(const id of ['copy-format','copy-reset','copy-double'])$(id).onchange=()=>{Object.assign(profile.bindings[selected],{formatting:$('copy-format').value,reset_seconds:Number($('copy-reset').value),double_tap_cut:$('copy-double').value==='true'});render();};
$('key').onchange=updateAction;$('action').onchange=updateAction;document.querySelectorAll('.modifiers input').forEach(i=>i.onchange=updateAction);
$('label').oninput=()=>{profile.labels[selected]=$('label').value;const label=$('keys').querySelector(`[data-control="${selected}"] .key-label`);if(label)label.textContent=$('label').value;invalidate();};
$('profile-name').oninput=()=>{profile.name=$('profile-name').value;invalidate();};$('layer').onchange=()=>{profile.layer=Number($('layer').value);invalidate();};
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
 if(devicePolling||busy)return;devicePolling=true;
 try{const data=await api('devices');devices=data.devices;
 const fingerprint=JSON.stringify(devices);if(fingerprint===deviceFingerprint)return;deviceFingerprint=fingerprint;
 const previous=$('device').value;$('device').replaceChildren();
 if(!devices.length){$('device').add(option('','No keypad found'));$('connection').textContent='Keypad not found';$('connection').className='status';}
 else{const candidates=devices.filter(d=>d.programmable);const shown=candidates.length?candidates:devices;shown.forEach((d,i)=>$('device').add(option(d.device_id||d.id,(d.programmable?'Mini keypad':'Input interface')+(shown.length>1?' '+(i+1):'')+' · 1189:8890')));$('connection').textContent=candidates.length?'Keypad connected':'Keypad found · access limited';$('connection').className='status connected';if(!candidates.length)message(shown[0].limitation,true);}
 if([...$('device').options].some(o=>o.value===previous))$('device').value=previous;
 $('preview').disabled=!devices.some(d=>d.programmable);if($('device').value!==previous)invalidate();
 }catch(e){$('connection').textContent='Connection unavailable';$('connection').className='status';$('preview').disabled=true;message(e.message,true);deviceFingerprint='';}finally{devicePolling=false;}
}
$('refresh').onclick=refresh;$('device').onchange=invalidate;$('scope').onchange=invalidate;
$('export').onclick=async()=>{try{await api('validate',{profile});const url=URL.createObjectURL(new Blob([JSON.stringify(profile,null,2)],{type:'application/json'}));const link=document.createElement('a');link.href=url;link.download=profile.name.replace(/[^\w -]/g,'').trim()+'.dialpad.json';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);message('Profile exported. Keep it to restore these app settings later.');}catch(e){message(e.message,true);}};
$('import').onclick=()=>$('file').click();$('file').onchange=async()=>{try{const file=$('file').files[0];if(!file)return;if(file.size>65536)throw new Error('Profile is too large.');const imported=JSON.parse(await file.text());await api('validate',{profile:imported});imported.labels=Object.fromEntries(controls.map(c=>[c,typeof imported.labels?.[c]==='string'?imported.labels[c].slice(0,32):names[c]]));
function checkEditable(a){if(a.type==='multi_tap'){for(const tap of ['single','double','triple'])checkEditable(a[tap]);return;}if(a.type==='shortcut'){a.key=a.key.toUpperCase();a.modifiers=(a.modifiers||[]).map(m=>m.toLowerCase());if(a.modifiers.some(m=>!['ctrl','shift','alt','cmd'].includes(m))||!keyNames.includes(a.key))throw new Error('Profile uses a key or modifier this editor cannot display.');}else if(a.type==='mouse'&&a.modifiers?.length)throw new Error('Mouse modifiers are not supported by this editor. Remove them before importing.');else if(!['copy_paste','clipboard'].includes(a.type)&&!actions[a.type]?.includes(a.action))throw new Error('Profile uses an action this editor cannot display.');}for(const action of Object.values(imported.bindings))checkEditable(action);profile=imported;openEditor();render();$('preset-note').textContent='Imported profile. Check that its dictation and terminal shortcuts match this computer.';message('Profile imported. Nothing has been written to the keypad.');}catch(e){message(e.message,true);}finally{$('file').value='';}};
$('preview').onclick=async()=>{try{const selectedControls=$('scope').value==='all'?[...controls]:[selected];const snapshot=structuredClone(profile), currentRevision=revision;const result=await api('preview',{profile:snapshot,controls:selectedControls,device_id:$('device').value});if(revision!==currentRevision){message('Settings changed while preparing the preview. Review them again.');return;}preview=result;$('review-content').textContent=(runtime?.enabled?'This will stop dial cycling. Use Apply in Dial cycling to keep switching.\n\n':'')+'Layer '+snapshot.layer+'\n\n'+selectedControls.map(c=>`${names[c]}  →  ${describe(snapshot.bindings[c])}`).join('\n');$('review').showModal();}catch(e){message(e.message,true);}};
$('apply').onclick=async()=>{if(!preview||busy)return;busy=true;$('apply').disabled=true;$('apply').textContent='Applying…';try{const result=await api('apply',{nonce:preview.nonce});message(result.result.message||'Transfer completed. Test your physical controls below.');}catch(e){message('Apply failed: '+e.message,true);}finally{busy=false;preview=null;$('apply').disabled=false;$('apply').textContent='Apply to keypad';$('review').close();refreshRuntime();}};
$('review').addEventListener('cancel',e=>{if(busy)e.preventDefault();});
$('test-input').onkeydown=e=>{$('test-event').textContent='Received: '+[...(e.ctrlKey?['Ctrl']:[]),...(e.altKey?['Alt']:[]),...(e.metaKey?['Command / Windows']:[]),...(e.shiftKey?['Shift']:[]),e.key].join(' + ');};
$('test-input').onwheel=e=>{$('test-event').textContent=e.deltaY<0?'Received: scroll up':'Received: scroll down';};
$('quit').onclick=async()=>{try{await flushSave();await api('quit',{});document.querySelector('main').replaceChildren(Object.assign(document.createElement('p'),{textContent:'Dialpad has quit. You can close this tab.'}));$('connection').textContent='Disconnected';}catch(e){message(e.message,true);}};
let savedName=null, savedSnapshot=null, autosaveTimer=null, saving=null, initialized=false, keyEditorOpen=false, orderSaving=false, seenActive=null;
function saveStatus(text,error=false){$('autosave-status').textContent=text;$('autosave-status').classList.toggle('error',error);}
function dirty(){return JSON.stringify(profile)!==JSON.stringify(savedSnapshot);}
function scheduleSave(){
 if(!initialized||!dirty())return;
 saveStatus('Saving…');clearTimeout(autosaveTimer);
 autosaveTimer=setTimeout(()=>flushSave().catch(()=>{}),500);
}
async function flushSave(){
 clearTimeout(autosaveTimer);
 if(saving){await saving;if(dirty())return flushSave();return;}
 if(!initialized||!dirty())return;
 const snapshot=structuredClone(profile), previous=savedName, expected=savedSnapshot&&structuredClone(savedSnapshot);
 saving=(async()=>{
  try{
   const data=await api('setups/upsert',{profile:snapshot,previous_name:previous,...(expected?{expected_profile:expected}:{})});
   savedName=snapshot.name;savedSnapshot=snapshot;showRuntime(data);saveStatus(dirty()?'Saving…':'Saved in app');
  }catch(e){saveStatus('Not saved · '+e.message,true);throw e;}
 })();
 try{await saving;}finally{saving=null;}
 if(dirty())return flushSave();
}
function loadProfile(value){
 profile=structuredClone(value);profile.labels=profile.labels||{};savedName=value.name;savedSnapshot=structuredClone(profile);
 selected='key1';render();saveStatus('Saved in app');renderSetupSelect();
}
function renderSetupSelect(){
 const select=$('setup-select');const fingerprint=JSON.stringify([runtime?.profiles.map(p=>p.name),profile?.name]);if(select.dataset.fingerprint===fingerprint)return;select.dataset.fingerprint=fingerprint;select.replaceChildren();
 for(const p of runtime?.profiles||[])select.add(option(p.name,p.name));
 if(profile&&!Array.from(select.options).some(o=>o.value===profile.name))select.add(option(profile.name,profile.name||'Untitled setup'));
 select.value=profile?.name||'';
}
function showRuntime(data){
 runtime=data;
 const order=data.order??data.profiles.map(p=>p.name);
 cycleOrder=order.filter(n=>data.profiles.some(p=>p.name===n));
 if(!initialized){
  const initial=data.profiles.find(p=>p.name===data.current?.name)||data.profiles[0];
  if(initial)loadProfile(initial);
  initialized=true;seenActive=data.enabled?data.current?.name:null;
  if(!initial){savedSnapshot=null;savedName=null;scheduleSave();}
 }else if(data.enabled&&data.current?.name!==seenActive){
  seenActive=data.current?.name;
  if(!keyEditorOpen&&!dirty()&&!saving){const active=data.profiles.find(p=>p.name===seenActive);if(active)loadProfile(active);}
 }else if(!data.enabled)seenActive=null;
 renderSetupSelect();renderCycle(data);
 $('cycle-enabled').checked=data.enabled;
 $('cycle-enabled').disabled=!data.ready||busy;
 $('enable-cycle').disabled=!data.ready||!cycleOrder.length||busy||orderSaving;
 $('apply-key-changes').disabled=$('enable-cycle').disabled;
 $('live-title').textContent=data.enabled?'On keypad: '+data.current.name:'Cycling off';
 $('cycle-note').textContent=data.error||(data.enabled?'Press the dial to switch. Apply after editing to update the keypad.':data.ready?'Tick your setups, then Apply to keypad.':'Open the desktop app to use dial cycling.');
}
async function refreshRuntime(){
 if(runtimePolling||saving||orderSaving)return;runtimePolling=true;
 try{showRuntime(await api('setups'));}catch(e){$('cycle-note').textContent=e.message;$('live-title').textContent='App disconnected';$('enable-cycle').disabled=true;}finally{runtimePolling=false;}
}
function openEditor(){keyEditorOpen=true;$('key-editor').hidden=false;$('cycling-panel').hidden=true;}
function closeEditor(){keyEditorOpen=false;recording=false;$('key-editor').hidden=true;$('cycling-panel').hidden=false;}
$('close-key-editor').onclick=closeEditor;
$('apply-key-changes').onclick=()=>$('enable-cycle').click();
$('setup-select').onchange=async()=>{
 const name=$('setup-select').value;
 try{await flushSave();const next=runtime.profiles.find(p=>p.name===name);if(next){loadProfile(next);closeEditor();}}
 catch(e){renderSetupSelect();message('Finish or correct the current setup before switching.',true);}
};
$('create-setup').onclick=async()=>{
 try{
  await flushSave();
  if(runtime.profiles.length>=8)throw new Error('You can keep up to eight setups. Delete one before adding another.');
  let name='New setup',number=2;while(runtime.profiles.some(p=>p.name===name))name='New setup '+number++;
  profile={version:1,name,layer:runtime.profiles[0]?.layer||1,labels:{...names},bindings:Object.fromEntries(controls.map(c=>[c,shortcut(c==='dial_ccw'?'UP':c==='dial_cw'?'DOWN':'ENTER')]))};
  savedName=null;savedSnapshot=null;selected='key1';render();await flushSave();closeEditor();$('setup-settings').open=true;$('profile-name').focus();$('profile-name').select();
 }catch(e){message(e.message,true);}
};
$('delete-setup').onclick=async()=>{
 try{
  await flushSave();if(!confirm('Delete setup “'+profile.name+'”?'))return;
  const profiles=runtime.profiles.filter(p=>p.name!==savedName);
  if(!profiles.length)throw new Error('Keep at least one setup.');
  const data=await api('setups/save',{profiles});
  loadProfile(data.profiles[0]);showRuntime(data);closeEditor();message('Setup deleted. Apply to update the keypad cycle.');
 }catch(e){message(e.message,true);}
};
async function updateOrder(names){
 if(orderSaving)return;
 orderSaving=true;
 try{const before=savedName;await flushSave();names=names.map(n=>n===before?savedName:n);showRuntime(await api('setups/order',{names}));}
 catch(e){message(e.message,true);libraryFingerprint='';renderCycle(runtime);}
 finally{orderSaving=false;$('enable-cycle').disabled=!runtime?.ready||!cycleOrder.length;}
}
function smallButton(label,action){const b=document.createElement('button');b.textContent=label;b.onclick=action;return b;}
function renderCycle(data){
 const fingerprint=JSON.stringify([data.profiles.map(p=>p.name),cycleOrder]);if(fingerprint===libraryFingerprint)return;libraryFingerprint=fingerprint;
 $('cycle-list').replaceChildren();
 const ordered=[...cycleOrder,...data.profiles.map(p=>p.name).filter(n=>!cycleOrder.includes(n))];
 for(const name of ordered){
  const row=document.createElement('div');row.className='cycle-row';
  const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=cycleOrder.includes(name);check.setAttribute('aria-label','Include '+name+' in cycle');
  check.onchange=()=>updateOrder(check.checked?[...cycleOrder,name]:cycleOrder.filter(n=>n!==name));
  label.append(check,document.createTextNode(name));row.append(label);
  if(check.checked){const i=cycleOrder.indexOf(name);const move=delta=>{const order=[...cycleOrder];[order[i],order[i+delta]]=[order[i+delta],order[i]];updateOrder(order);};
   const up=smallButton('↑',()=>move(-1));up.disabled=i===0;up.setAttribute('aria-label','Move '+name+' up');
   const down=smallButton('↓',()=>move(1));down.disabled=i===cycleOrder.length-1;down.setAttribute('aria-label','Move '+name+' down');row.append(up,down);
  }
  $('cycle-list').append(row);
 }
}
$('enable-cycle').onclick=async()=>{
 try{
  await flushSave();if(orderSaving)throw new Error('Wait for the cycle selection to finish saving.');
  const currentRevision=revision;
  const result=await api('setups/preview',{device_id:$('device').value,names:cycleOrder});
  if(revision!==currentRevision)throw new Error('Settings changed. Review them again.');
  preview=result;
  $('review-content').textContent='Apply these setups on layer '+result.layer+'?\n\n'+result.profiles.map((p,i)=>`${i+1}. ${p.name}\n`+controls.map(c=>`${names[c]} → ${describe(p.bindings[c])}`).join('\n')).join('\n\n')+'\n\nThe first setup is sent now. Pressing the dial sends the next setup and replaces all nine bindings. Keep Dialpad running for cycling and multi-tap actions.';
  $('review').showModal();
 }catch(e){message(e.message,true);}
};
$('cycle-enabled').onchange=async()=>{
 if($('cycle-enabled').checked){$('cycle-enabled').checked=!!runtime?.enabled;$('enable-cycle').click();}
 else{try{showRuntime(await api('setups/disable',{}));message('Cycling stopped. The keypad retains its last bindings.');}catch(e){$('cycle-enabled').checked=!!runtime?.enabled;message(e.message,true);}}
};
$('background').onclick=async()=>{
 try{await flushSave();if(window.webkit?.messageHandlers?.desktop)window.webkit.messageHandlers.desktop.postMessage('hide');else message('You can close this tab. Keep the Dialpad companion running.');}catch(e){message('Changes could not be saved. Correct the setup before closing.',true);}
};
window.addEventListener('beforeunload',event=>{if(initialized&&dirty()){event.preventDefault();event.returnValue='';}});
$('platform').value=/Mac/.test(navigator.platform)?'mac':'windows';
async function start(){try{const response=await fetch('/starters.json');if(!response.ok)throw new Error('Could not load bundled layouts.');starterLayouts=await response.json();preset();await refreshRuntime();refresh();setInterval(refreshRuntime,1000);setInterval(refresh,4000);}catch(e){message(e.message,true);}}
start();
