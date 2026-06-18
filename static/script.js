
const $=id=>document.getElementById(id);
let token=null,currentFile=null,lastData=null,activeTab='candidate';
let docImg=new Image(),activeRow=null,activeLabel='';

// ── Screen switcher ──────────────────────────────────────
function show(id){
  ['uploadScreen','loadingScreen','resultsScreen'].forEach(s=>{
    $(s).style.display=s===id?'flex':'none';
  });
}

// ── Color helpers ────────────────────────────────────────
const confColor=c=>c>=.85?'#16a34a':c>=.5?'#d97706':'#dc2626';
const fmtKey=k=>k.replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());

// ── Login ────────────────────────────────────────────────
$('loginBtn').addEventListener('click',doLogin);
['loginUser','loginPass'].forEach(id=>$(id).addEventListener('keydown',e=>{if(e.key==='Enter')doLogin();}));

async function doLogin(){
  const u=$('loginUser').value.trim(),p=$('loginPass').value;
  if(!u||!p){$('loginErr').textContent='Fill in both fields.';return;}
  $('loginBtn').disabled=true;$('loginBtn').textContent='Signing in…';$('loginErr').textContent='';
  try{
    const r=await fetch('/token',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});
    const d=await r.json();
    if(!r.ok)throw new Error(d.detail||'Invalid credentials');
    token=d.access_token;
    $('tbUser').textContent=u;
    $('loginOverlay').classList.add('gone');
    $('app').style.display='flex';
    $('app').style.flexDirection='column';
    show('uploadScreen');
  }catch(e){$('loginErr').textContent=e.message;}
  finally{$('loginBtn').disabled=false;$('loginBtn').textContent='Sign in';}
}

// ── Logout ───────────────────────────────────────────────
$('logoutBtn').addEventListener('click',()=>{
  token=null;currentFile=null;
  $('loginUser').value='';$('loginPass').value='';$('loginErr').textContent='';
  $('loginOverlay').classList.remove('gone');
  $('app').style.display='none';
  resetUpload();show('uploadScreen');
});

// ── File select ──────────────────────────────────────────
const dropzone=$('dropzone'),fileInput=$('fileInput');
dropzone.addEventListener('click',()=>fileInput.click());
fileInput.addEventListener('change',()=>setFile(fileInput.files[0]));
dropzone.addEventListener('dragover',e=>{e.preventDefault();dropzone.classList.add('over');});
dropzone.addEventListener('dragleave',()=>dropzone.classList.remove('over'));
dropzone.addEventListener('drop',e=>{e.preventDefault();dropzone.classList.remove('over');if(e.dataTransfer.files[0])setFile(e.dataTransfer.files[0]);});

function setFile(f){
  if(!f)return;
  const ok=['image/jpeg','image/png','image/webp','application/pdf'];
  if(!ok.includes(f.type)){alert('Unsupported type. Use JPG, PNG, WEBP or PDF.');return;}
  if(f.size>10*1024*1024){alert('File exceeds 10 MB.');return;}
  currentFile=f;
  $('pillName').textContent=f.name;
  $('filePill').classList.add('show');
  $('extractBtn').disabled=false;
}

function resetUpload(){
  currentFile=null;fileInput.value='';
  $('filePill').classList.remove('show');
  $('extractBtn').disabled=true;
}

// ── Extract ──────────────────────────────────────────────
$('extractBtn').addEventListener('click',doExtract);
$('newBtn').addEventListener('click',()=>{show('uploadScreen');resetUpload();});

async function doExtract(){
  if(!currentFile||!token)return;
  show('loadingScreen');startProgress();
  const form=new FormData();form.append('file',currentFile);
  try{
    const r=await fetch('/extract',{method:'POST',headers:{'Authorization':'Bearer '+token},body:form});
    const d=await r.json();
    if(!r.ok)throw new Error(d.message||d.detail||'Extraction failed');
    finishProgress();
    await new Promise(res=>setTimeout(res,450));
    renderResults(d,currentFile);
    show('resultsScreen');
  }catch(e){
    stopProgress();show('uploadScreen');
    alert('Extraction failed: '+e.message);
  }
}

// ── Progress ─────────────────────────────────────────────
const STEPS=[
  {p:12,m:'Uploading document…'},
  {p:28,m:'Analyzing document structure…'},
  {p:48,m:'Running primary extraction (Scout)…'},
  {p:68,m:'Cross-validating with MiniMax-M3…'},
  {p:84,m:'Merging and scoring confidence…'},
  {p:94,m:'Applying consistency checks…'},
  {p:98,m:'Finalizing results…'},
];
let ptimer=null,pidx=0;

function setProgress(p,m){
  $('progFill').style.width=p+'%';
  $('progPct').textContent=p+'%';
  $('loadMsg').textContent=m;
}

function startProgress(){
  pidx=0;setProgress(0,'Preparing document…');
  ptimer=setInterval(()=>{
    if(pidx>=STEPS.length)return;
    const s=STEPS[pidx++];setProgress(s.p,s.m);
  },950);
}

function finishProgress(){clearInterval(ptimer);setProgress(100,'Complete!');}
function stopProgress(){clearInterval(ptimer);setProgress(0,'');}

// ── Canvas ───────────────────────────────────────────────
function loadImage(file){
  const url=URL.createObjectURL(file);
  docImg.onload=()=>{drawCanvas();URL.revokeObjectURL(url);};
  docImg.src=url;
}

function drawCanvas(bbox, label) {
  const canvas = $('docCanvas');
  const wrap = canvas.parentElement;
  const maxW = wrap.clientWidth - 28;
  const scale = Math.min(maxW / docImg.naturalWidth, 1);
  canvas.width = Math.round(docImg.naturalWidth * scale);
  canvas.height = Math.round(docImg.naturalHeight * scale);
  const ctx = canvas.getContext('2d');
  ctx.drawImage(docImg, 0, 0, canvas.width, canvas.height);

  if (bbox && bbox.length === 4) {
    const [x1, y1, x2, y2] = bbox;
    const px = x1 * canvas.width, py = y1 * canvas.height;
    const pw = (x2 - x1) * canvas.width, ph = (y2 - y1) * canvas.height;

    // soft highlight — no dimming, just a colored overlay rectangle
    ctx.save();
    ctx.fillStyle = 'rgba(37,99,235,0.15)';
    ctx.fillRect(px, py, pw, ph);
    ctx.strokeStyle = '#2563eb';
    ctx.lineWidth = 2;
    ctx.setLineDash([5, 3]);
    ctx.strokeRect(px, py, pw, ph);
    ctx.setLineDash([]);

    // label
    const lbl = label || '';
    ctx.font = 'bold 11px system-ui,sans-serif';
    const tw = ctx.measureText(lbl).width;
    const lx = Math.max(px, 2), ly = Math.max(py - 22, 2);
    ctx.fillStyle = '#2563eb';
    ctx.beginPath();
    ctx.roundRect ? ctx.roundRect(lx, ly, tw + 14, 20, 4) : ctx.rect(lx, ly, tw + 14, 20);
    ctx.fill();
    ctx.fillStyle = '#fff';
    ctx.fillText(lbl, lx + 7, ly + 14);
    ctx.restore();
  }
}
function highlight(bbox,label,row){
  if(activeRow===row){
    activeRow.classList.remove('active');
    activeRow=null;drawCanvas();return;
  }
  if(activeRow)activeRow.classList.remove('active');
  activeRow=row;row.classList.add('active');
  drawCanvas(bbox,label);
}

window.addEventListener('resize',()=>{if(lastData)drawCanvas(activeRow?null:null);});

// ── Render results ────────────────────────────────────────
const TABS_DEF=[
  {key:'candidate',label:'Candidate'},
  {key:'subjects',label:'Subjects'},
  {key:'result',label:'Result'},
  {key:'issue_info',label:'Issue Info'},
];

function renderResults(data,file){
  lastData=data;activeRow=null;activeTab='candidate';
  $('imgFileName').textContent=file.name;
  loadImage(file);

  const c=data.document_confidence||0;
  const badge=$('overallBadge');
  badge.textContent=`Overall ${(c*100).toFixed(1)}%`;
  badge.style.cssText=`background:${confColor(c)}18;color:${confColor(c)};border:1px solid ${confColor(c)}33;`;

  renderTabs(data);
  renderWarnings(data.warnings||[]);
}
setView('fields');
function renderTabs(data){
  const bar=$('tabBar');bar.innerHTML='';
  TABS_DEF.forEach(({key,label})=>{
    const t=document.createElement('button');
    t.className='tab'+(key===activeTab?' active':'');
    t.textContent=label;
    t.addEventListener('click',()=>{
      activeTab=key;
      bar.querySelectorAll('.tab').forEach(b=>b.classList.toggle('active',b===t));
      renderTabContent(data,key);
    });
    bar.appendChild(t);
  });
  renderTabContent(data,activeTab);
}

function renderTabContent(data,tab){
  const scroll=$('fieldsScroll');scroll.innerHTML='';
  activeRow=null;drawCanvas();
  const section=data[tab];
  if(!section){scroll.innerHTML='<div class="empty-tab">No data for this section</div>';updateCount(0,0);return;}

  let rows=[];
  if(tab==='subjects'&&Array.isArray(section)){
    section.forEach((subj,i)=>{
      const sname=subj.subject_name?.value||`Subject ${i+1}`;
      const lbl=document.createElement('div');
      lbl.className='sec-label';lbl.textContent=sname;
      scroll.appendChild(lbl);
      const sr=makeRows(subj,`subjects[${i}]`);
      sr.forEach(r=>scroll.appendChild(r));
      rows=rows.concat(sr);
    });
  }else{
    rows=makeRows(section,tab);
    rows.forEach(r=>scroll.appendChild(r));
  }

  const filled=rows.filter(r=>!r.querySelector('.empty')).length;
  $('fieldsSub').textContent=`${filled} of ${rows.length} fields extracted`;
}

function makeRows(obj,prefix){
  if(!obj||typeof obj!=='object')return[];
  const out=[];
  for(const[k,v]of Object.entries(obj)){
    if(v===null||v===undefined)continue;
    if(typeof v==='object'&&('confidence'in v||'value'in v)){
      out.push(makeRow(k,v,`${prefix}.${k}`));
    }else if(typeof v==='object'&&!Array.isArray(v)){
      makeRows(v,`${prefix}.${k}`).forEach(r=>out.push(r));
    }
  }
  return out;
}

function makeRow(key,field,path){
  const row=document.createElement('div');
  const hasBbox=Array.isArray(field.bbox)&&field.bbox.length===4;
  const hasVal=field.value!==null&&field.value!==undefined;
  const conf=typeof field.confidence==='number'?field.confidence:0;
  const color=confColor(conf);

  row.className='f-row'+(hasBbox?' clickable':'');
  row.title=hasBbox?'Click to highlight on document':'No location data available';

  row.innerHTML=`
    <div class="f-dot" style="background:${hasBbox?color:'#e2e8f0'};opacity:${hasBbox?1:.4};"></div>
    <div class="f-name">${fmtKey(key)}</div>
    <div class="f-val ${hasVal?'':'empty'}">${hasVal?field.value:'— not found'}</div>
    <div class="conf-wrap">
      <div class="conf-track"><div class="conf-bar" style="width:${(conf*100).toFixed(0)}%;background:${color};"></div></div>
      <div class="conf-num">${(conf*100).toFixed(0)}%</div>
    </div>
  `;

  if(hasBbox){
    row.addEventListener('click',()=>highlight(field.bbox,fmtKey(key),row));
  }
  return row;
}


// ── View toggle ───────────────────────────────────────────
function setView(mode) {
  const isFields = mode === 'fields';
  $('fieldsScroll').style.display = isFields ? 'block' : 'none';
  $('jsonView').style.display = isFields ? 'none' : 'block';
  $('viewFields').style.background = isFields ? 'var(--primary)' : 'none';
  $('viewFields').style.color = isFields ? '#fff' : 'var(--muted)';
  $('viewJson').style.background = isFields ? 'none' : 'var(--primary)';
  $('viewJson').style.color = isFields ? 'var(--muted)' : '#fff';
  if (!isFields && lastData) {
    $('jsonPre').textContent = JSON.stringify(lastData, null, 2);
  }
}

function copyJson() {
  if (!lastData) return;
  navigator.clipboard.writeText(JSON.stringify(lastData, null, 2))
    .then(() => { $('copyBtn').textContent = 'Copied!'; setTimeout(() => $('copyBtn').textContent = 'Copy', 1800); });
}


function renderWarnings(warnings){
  const sec=$('warnSection');
  if(!warnings.length){sec.style.display='none';return;}
  sec.style.display='block';
  $('warnCount').textContent=warnings.length;
  $('warnList').innerHTML=warnings.map(w=>`<div class="warn-item">· ${w}</div>`).join('');
}
