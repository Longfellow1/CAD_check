const S={data:null,filter:'ALL',selected:null};
const $=id=>document.getElementById(id);
const canvas=$('canvas'),ctx=canvas.getContext('2d');

const C={battery:'#355f9e',underbody_bracket:'#73839a',left_rail:'#8b95a7',right_rail:'#8b95a7',motor:'#6e5aa3',motor_bracket:'#7e8d9f',controller:'#2d7b74',controller_bracket:'#7e8d9f',exhaust:'#9a5e4c',front_crossmember:'#697386',ground_ref:'#c8ced8',rear_module:'#6e5aa3'};
const REGRESSION_LABEL={ALL:'全部',NEW_FAIL:'新增不满足',REGRESSED:'退化',FIXED:'已修复',IMPROVED:'改善',UNCHANGED:'无变化',NON_COMPARABLE:'不可比'};
const STATUS_LABEL={PASS:'满足',FAIL:'不满足',REVIEW_REQUIRED:'需人工复核',BLOCKED:'无法执行'};
const EXECUTOR_LABEL={minimum_clearance:'最小间隙',directional_distance:'方向距离',angle:'角度/姿态'};
const OBJECT_LABEL={battery:'动力电池包',underbody_bracket:'底部支架',left_rail:'左纵梁',right_rail:'右纵梁',motor:'动力系统',motor_bracket:'电机支架',controller:'电机控制器',controller_bracket:'控制器支架',exhaust:'排气高温区',front_crossmember:'前横梁',ground_ref:'地面基准',rear_module:'后电驱模块'};
const TRACE_STAGE_LABEL={resolve:'对象解析',geometry:'几何计算',rule:'规则判定',blocked:'执行阻塞'};
const objName=id=>OBJECT_LABEL[id]||id;
const statusName=s=>STATUS_LABEL[s]||s;
const regressionName=s=>REGRESSION_LABEL[s]||s;
const executorName=s=>EXECUTOR_LABEL[s]||s;

async function load(){
  S.data=await fetch('/api/demo').then(r=>r.json());
  render();
  selectCase(S.data.regression.find(x=>x.regression==='NEW_FAIL')?.case_id||S.data.regression[0].case_id);
}

function render(){renderSummary();renderFilters();renderList();draw()}

function renderSummary(){
  const c={TOTAL:S.data.regression.length,NEW_FAIL:0,REGRESSED:0,FIXED:0,IMPROVED:0,UNCHANGED:0};
  S.data.regression.forEach(r=>c[r.regression]!==undefined&&c[r.regression]++);
  $('summary').innerHTML=[['TOTAL','校核总数'],['NEW_FAIL','新增不满足'],['REGRESSED','退化'],['FIXED','已修复'],['IMPROVED','改善'],['UNCHANGED','无变化']]
    .map(([k,l])=>`<div class="metric"><div class="n">${c[k]}</div><div class="l">${l}</div></div>`).join('');
}

function renderFilters(){
  const items=['ALL','NEW_FAIL','REGRESSED','FIXED','IMPROVED','UNCHANGED'];
  $('filters').innerHTML=items.map(k=>`<button class="filter ${S.filter===k?'active':''}" data-f="${k}">${regressionName(k)}</button>`).join('');
  document.querySelectorAll('.filter').forEach(b=>b.onclick=()=>{S.filter=b.dataset.f;renderFilters();renderList()});
}

function renderList(){
  const rows=S.data.regression.filter(r=>S.filter==='ALL'||r.regression===S.filter);
  $('caseList').innerHTML=rows.map(r=>`<div class="case ${S.selected===r.case_id?'active':''}" data-id="${r.case_id}"><div class="case-title">${r.title}</div><div class="case-meta"><span>${r.candidate.value??'—'} ${r.candidate.unit}</span><span class="tag ${r.regression}">${regressionName(r.regression)}</span></div></div>`).join('');
  document.querySelectorAll('.case').forEach(el=>el.onclick=()=>selectCase(el.dataset.id));
}

function selectCase(id){S.selected=id;renderList();renderDetail();draw()}

function ruleText(id){
  const r=S.data.cases.find(x=>x.id===id).rule;
  return r.operator==='range'?`${r.lower}–${r.upper} ${r.unit}`:`${r.operator} ${r.threshold} ${r.unit}`;
}

function formatTrace(execution,label){
  const lines=[`【${label}】`, `结果：${statusName(execution.status)}`];
  if(execution.value!==null&&execution.value!==undefined) lines.push(`测量值：${execution.value} ${execution.unit}`);
  execution.trace.forEach((t,i)=>{
    const d=t.detail||{};
    const parts=[];
    if(d.target) parts.push(`目标=${objName(d.target)}`);
    if(d.counterpart) parts.push(`对比对象=${objName(d.counterpart)}`);
    if(d.executor) parts.push(`计算方法=${executorName(d.executor)}`);
    if(d.value!==undefined) parts.push(`值=${d.value} ${d.unit||''}`.trim());
    if(d.operator) parts.push(`规则=${d.operator} ${d.threshold??''}`.trim());
    if(d.status) parts.push(`判定=${statusName(d.status)}`);
    if(d.missing) parts.push(`缺失对象=${d.missing.map(objName).join('、')}`);
    lines.push(`${i+1}. ${TRACE_STAGE_LABEL[t.stage]||t.stage}${parts.length?'：'+parts.join('；'):''}`);
  });
  return lines.join('\n');
}

function renderDetail(){
  const r=S.data.regression.find(x=>x.case_id===S.selected),c=S.data.cases.find(x=>x.id===S.selected);
  if(!r)return;
  $('detail').classList.remove('empty');
  const focus=r.candidate.evidence.focus_ids.map(objName).join(' ↔ ');
  $('detail').innerHTML=`<div class="kicker">${executorName(c.executor)}</div><h2>${r.title}</h2><span class="tag ${r.regression}">${regressionName(r.regression)}</span><div class="compare"><div class="value-card"><div class="kicker">基线版本 V1</div><div class="v">${r.baseline.value??'—'} ${r.baseline.unit}</div><div>${statusName(r.baseline.status)}</div></div><div class="value-card"><div class="kicker">候选版本 V2</div><div class="v">${r.candidate.value??'—'} ${r.candidate.unit}</div><div>${statusName(r.candidate.status)}</div></div></div><div class="rule"><b>校核要求</b><br>${ruleText(r.case_id)}<br><br><b>变化量</b><br>${r.delta??'—'} ${r.candidate.unit}<br><br><b>规则来源</b><br>脱敏演示规则 · ${c.source_ref}</div><div class="actions"><button id="traceBtn" class="secondary">查看执行追溯</button><button id="acceptBtn">确认结果</button></div><div class="trace"><b>校核证据</b><br>关注对象：${focus}<br>${r.candidate.evidence.annotation}</div>`;
  $('traceBtn').onclick=()=>{
    $('traceText').textContent=`${formatTrace(r.baseline,'基线版本 V1')}\n\n${formatTrace(r.candidate,'候选版本 V2')}`;
    $('traceDialog').showModal();
  };
  $('acceptBtn').onclick=e=>{e.target.textContent='已确认';e.target.disabled=true};
}

function resize(){
  const r=canvas.getBoundingClientRect();
  canvas.width=Math.max(1,r.width*devicePixelRatio);
  canvas.height=Math.max(1,r.height*devicePixelRatio);
  ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
}
function project([x,y,z],w,h){return [w/2+(x-y)*.28,h*.66-z*.42+(x+y)*.08]}
function box(b,hi,w,h){
  const [x,y]=project(b.center,w,h),sx=Math.max(8,b.size[0]*.16),sy=Math.max(8,b.size[1]*.10),sz=Math.max(5,b.size[2]*.22);
  ctx.save();ctx.translate(x,y);ctx.fillStyle=hi?'#ffcc80':(C[b.id]||'#8a94a6');ctx.strokeStyle=hi?'#d97706':'#596579';ctx.lineWidth=hi?2.5:1;ctx.globalAlpha=b.id==='ground_ref'?.22:.72;ctx.fillRect(-sx/2,-sz/2,sx,sz);ctx.strokeRect(-sx/2,-sz/2,sx,sz);ctx.globalAlpha=.25;ctx.beginPath();ctx.moveTo(-sx/2,-sz/2);ctx.lineTo(-sx/2+sy*.35,-sz/2-sy*.22);ctx.lineTo(sx/2+sy*.35,-sz/2-sy*.22);ctx.lineTo(sx/2,-sz/2);ctx.closePath();ctx.fill();ctx.restore();
}
function draw(){
  if(!S.data)return;
  resize();
  const r=canvas.getBoundingClientRect(),w=r.width,h=r.height;
  ctx.clearRect(0,0,w,h);
  const sel=S.data.regression.find(x=>x.case_id===S.selected),focus=new Set(sel?.candidate.evidence.focus_ids||[]);
  Object.values(S.data.models.V2.objects).forEach(b=>box(b,focus.has(b.id),w,h));
  $('measureLabel').classList.add('hidden');
  if(sel?.candidate.evidence.line_start&&sel?.candidate.evidence.line_end){
    const a=project(sel.candidate.evidence.line_start,w,h),b=project(sel.candidate.evidence.line_end,w,h);
    ctx.strokeStyle='#dc2626';ctx.lineWidth=2;ctx.setLineDash([6,4]);ctx.beginPath();ctx.moveTo(...a);ctx.lineTo(...b);ctx.stroke();ctx.setLineDash([]);
    $('measureLabel').textContent=sel.candidate.evidence.annotation;
    $('measureLabel').classList.remove('hidden');
  }
  $('viewerHint').textContent=sel?sel.title:'请选择一个校核项';
}

window.addEventListener('resize',draw);
$('runBtn').onclick=()=>{
  $('runBtn').textContent='校核运行中…';
  setTimeout(()=>{$('runBtn').textContent='运行校核';render()},450);
};
load();
