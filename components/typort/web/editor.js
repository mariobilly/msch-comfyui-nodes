/* Studio state stays private until Apply; closing never changes the ComfyUI node. */
(() => {
if (!document.getElementById('canvas') || !document.getElementById('layerList')) return;
const $ = id => document.getElementById(id), MT=window.MarioType;
let project=MT.makeProject(), selected=0, options={width:1920,height:1080,fps:30,format:'Transparent MOV',motion_blur:'3 samples',video_file:''};
let current=0, playing=false, lastTick=0, bounds=[], ready=false, history=[], future=[], activeKey=-1;
const canvas=$('canvas'), renderer=MT.createRenderer(canvas), video=$('footage');
const clone=x=>JSON.parse(JSON.stringify(x));
function icon(id,name){$(id).innerHTML=`<i data-lucide="${name}"></i>`;window.lucide?.createIcons({attrs:{'stroke-width':1.8}});}
for(const [id,name]of [['undo','undo-2'],['redo','redo-2'],['add','plus'],['play','play'],['home','skip-back']])icon(id,name);
const layer=()=>project.layers[selected];
const status=message=>$('status').textContent=message;
const audioStudio=window.createMarioAudioStudio({project:()=>project,options:()=>options,time:()=>current,
    playing:()=>playing,saveUndo,changed:(structural=false)=>{if(structural)properties();drawTracks();draw();updateState();},seek,status});
function snapshot(){const {audio,...rest}=project;return {project:{...clone(rest),audio:{...audio}},options:clone(options),selected};}
function saveUndo(){history.push(snapshot());if(history.length>80)history.shift();future=[];}
function restore(from,to){if(!from.length)return;to.push(snapshot());({project,options,selected}=from.pop());activeKey=-1;current=Math.min(current,project.duration);refresh();}
function updateState(){ $('projectState').textContent=`${project.layers.length} layers / ${project.duration.toFixed(1)} seconds`; $('undo').disabled=!history.length; $('redo').disabled=!future.length; }
function formatTime(v){return v.toFixed(2);}
function seek(t){current=Math.max(0,Math.min(project.duration,t));$('scrub').value=current;syncVideo();draw();}
function syncVideo(){
    audioStudio.sync();video.muted=Boolean(project.audio?.file)||!$('audio').checked;
    const target=current+project.video_offset;
    if(video.src && Number.isFinite(video.duration) && Math.abs(video.currentTime-target)>.08)
        video.currentTime=Math.min(Math.max(0,video.duration-.001),target);
}
function draw(){
    if(!ready)return;
    bounds=renderer.render(project,current,{samples:options.motion_blur==='Off'?1:parseInt(options.motion_blur),fps:options.fps});
    const b=bounds[selected], box=$('selection'), s=MT.state(layer(),current);
    if(b&& !playing){
        box.style.display='block';box.style.left=`${b.x/canvas.width*100}%`;box.style.top=`${b.y/canvas.height*100}%`;
        box.style.width=`${b.width/canvas.width*100}%`;box.style.height=`${b.height/canvas.height*100}%`;
        box.style.transformOrigin=`${s.anchor_x*100}% ${s.anchor_y*100}%`;box.style.transform=`rotate(${s.rotation}deg) scale(${s.scale})`;
    }else box.style.display='none';
    $('time').textContent=`${formatTime(current)} / ${formatTime(project.duration)}`;
    $('playhead').style.left=`${current/project.duration*100}%`;
    $('selectedTime').textContent=`${formatTime(layer().start)} - ${formatTime(layer().end)} s`;
}
function drawTracks(){
    audioStudio.drawWave();
    $('showCues').checked=project.cues_visible!==false;
    const source=$('cueSource'),previousSource=source.value;
    source.replaceChildren(...Object.keys(project.audio?.analysis?.channels||{Mix:null}).map(name=>new Option(name,name)));
    if([...source.options].some(o=>o.value===previousSource))source.value=previousSource;
    source.disabled=$('cueMode').value!=='Hits';
    $('generateCues').disabled=!project.audio?.analysis;
    $('ruler').replaceChildren();$('tracks').replaceChildren();
    const steps=Math.min(12,Math.ceil(project.duration));
    for(let i=0;i<=steps;i++){
        const tick=document.createElement('span');tick.textContent=formatTime(project.duration*i/steps);tick.style.left=`${i/steps*100}%`;
        if(i===steps)tick.style.transform='translateX(-100%)';$('ruler').append(tick);
    }
    if(project.cues_visible!==false&&project.text_cues?.length){
        const row=document.createElement('div');row.className='track cue-track';row.setAttribute('aria-label','Text cues');
        project.text_cues.forEach((cue,index)=>{
            const box=document.createElement('button');box.className='text-cue';
            box.style.left=`${cue.start/project.duration*100}%`;box.style.width=`${(cue.end-cue.start)/project.duration*100}%`;
            box.textContent=`+ ${index+1}`;box.title=`Add text: ${formatTime(cue.start)} - ${formatTime(cue.end)} s`;
            box.setAttribute('aria-label',box.title);box.onclick=()=>useCue(index);row.append(box);
        });
        $('tracks').append(row);
    }
    project.layers.forEach((l,index)=>{
        const track=document.createElement('div');track.className='track';
        const clip=document.createElement('div');clip.className='clip'+(index===selected?' active':'');clip.dataset.index=index;
        clip.style.left=`${l.start/project.duration*100}%`;clip.style.width=`${(l.end-l.start)/project.duration*100}%`;
        const a=document.createElement('b'),b=document.createElement('b');a.className=b.className='handle';a.dataset.edge='start';b.dataset.edge='end';
        clip.append(a,document.createTextNode(l.text.replaceAll('\n',' ')),b);track.append(clip);$('tracks').append(track);
        clip.onpointerdown=e=>dragClip(e,index,e.target.dataset.edge);
        l.keyframes.forEach((key,k)=>{
            const dot=document.createElement('button');dot.className='key-dot';dot.style.left=`${(key.time-l.start)/(l.end-l.start)*100}%`;dot.title=`Keyframe ${formatTime(key.time)} s`;
            dot.onpointerdown=e=>e.stopPropagation();dot.onclick=e=>{e.stopPropagation();selectLayer(index);activeKey=k;seek(key.time);keyProperties();};clip.append(dot);
        });
    });
    for(const time of project.markers){const mark=document.createElement('div');mark.className='mark';mark.style.left=`${time/project.duration*100}%`;$('tracks').append(mark);}
}
function listLayers(){
    $('layerList').replaceChildren();
    project.layers.forEach((l,i)=>{
        const row=document.createElement('div');row.className='layer-row'+(i===selected?' active':'');
        const visible=document.createElement('input');visible.type='checkbox';visible.checked=l.enabled;visible.title='Layer visibility';
        visible.onclick=e=>e.stopPropagation();visible.onchange=()=>{saveUndo();l.enabled=visible.checked;draw();updateState();};
        const text=document.createElement('span');text.textContent=l.text.replaceAll('\n',' ');const n=document.createElement('small');n.textContent=String(i+1).padStart(2,'0');
        row.append(n,visible,text);row.onclick=()=>selectLayer(i);$('layerList').append(row);
    });
}
function selectLayer(index){selected=index;activeKey=-1;if(current<layer().start||current>=layer().end)seek(Math.min(layer().end-.01,layer().start+layer().enter+.05));listLayers();properties();drawTracks();draw();}
function control(parent,label,key,type='number',spec={},object=layer(),callback=null){
    const wrapper=document.createElement('label');wrapper.append(document.createTextNode(label));
    const input=document.createElement(type==='select'?'select':'input');input.dataset.field=key;input.setAttribute('aria-label',label);
    if(type==='select')for(const value of spec.values){const option=document.createElement('option');option.value=option.textContent=value;input.append(option);}
    else input.type=type;
    const factor=spec.factor||1;
    for(const name of ['min','max','step'])if(spec[name]!==undefined)input[name]=spec[name];
    if(type==='checkbox')input.checked=object[key];else input.value=typeof object[key]==='number'?Number((object[key]*factor).toFixed(4)):object[key];
    wrapper.append(input);parent.append(wrapper);
    input.onchange=()=>{
        saveUndo();let value=type==='checkbox'?input.checked:type==='number'?Number(input.value)/factor:input.value;
        if(type==='number'&&(!Number.isFinite(value)||(spec.min!==undefined&&value*factor<spec.min)||(spec.max!==undefined&&value*factor>spec.max))){status('Value is outside the allowed range.');properties();return;}
        object[key]=value;
        if(key==='start'||key==='end'){
            object.start=Math.min(object.start,project.duration-.01);object.end=Math.max(object.start+.01,Math.min(project.duration,object.end));
            object.keyframes=object.keyframes.filter(k=>k.time>=object.start&&k.time<=object.end);drawTracks();
        }
        callback?.();draw();updateState();
    };
    return input;
}
function group(name){const details=document.createElement('details');details.open=true;const summary=document.createElement('summary');summary.textContent=name;
    const grid=document.createElement('div');grid.className='property-grid';details.append(summary,grid);$('properties').append(details);return grid;}
function properties(){
    $('text').value=layer().text;$('properties').replaceChildren();
    let g=group('Typography');
    control(g,'Font weight','font','select',{values:MT.FONTS});control(g,'Alignment','align','select',{values:['left','center','right']});
    control(g,'Direction','direction','select',{values:['auto','ltr','rtl']});control(g,'Auto fit','fit','checkbox');
    control(g,'Size (% height)','size','number',{factor:100,min:.5,max:150,step:.5});
    control(g,'Line height','line_height','number',{min:.5,max:3,step:.05});control(g,'Tracking (%)','tracking','number',{factor:100,min:-2,max:10,step:.05});
    g=group('Composition');
    for(const [label,key,min,max]of [['X (%)','x',-100,200],['Y (%)','y',-100,200],['Box width (%)','width',2,200],['Box height (%)','height',2,200],['Anchor X (%)','anchor_x',0,100],['Anchor Y (%)','anchor_y',0,100]])control(g,label,key,'number',{factor:100,min,max,step:.5});
    control(g,'Scale','scale','number',{min:.05,max:5,step:.05});control(g,'Rotation','rotation','number',{min:-360,max:360,step:1});
    const fit=document.createElement('button');fit.textContent='Fit canvas';fit.onclick=()=>{saveUndo();Object.assign(layer(),{x:.5,y:.5,width:.94,height:.88,fit:true,size:.8,scale:1,rotation:0});properties();draw();};g.append(fit);
    g=group('Fill & outline');control(g,'Fill','color','color');control(g,'Opacity (%)','opacity','number',{factor:100,min:0,max:100,step:1});
    control(g,'Outline','stroke_color','color');control(g,'Outline (%)','stroke','number',{factor:100,min:0,max:5,step:.05});
    control(g,'Block','block_color','color');control(g,'Block opacity (%)','block_opacity','number',{factor:100,min:0,max:100,step:1});
    control(g,'Block padding (%)','padding','number',{factor:100,min:0,max:15,step:.1});
    g=group('Drop shadow');control(g,'Shadow','shadow_color','color');control(g,'Opacity (%)','shadow_opacity','number',{factor:100,min:0,max:100,step:1});
    control(g,'Softness (%)','shadow_blur','number',{factor:100,min:0,max:10,step:.1});
    control(g,'Offset X (%)','shadow_x','number',{factor:100,min:-50,max:50,step:.1});control(g,'Offset Y (%)','shadow_y','number',{factor:100,min:-50,max:50,step:.1});
    g=group('Audio reaction');
    control(g,'Trigger','react_mode','select',{values:['Off','Beats','Hits','Energy']},layer(),()=>{
        if(layer().react_mode!=='Off'&&!project.audio.analysis){layer().react_mode='Off';status('Upload and analyze audio before enabling a reaction.');properties();}
    });
    control(g,'Source','react_source','select',{values:project.audio.analysis?Object.keys(project.audio.analysis.channels):['Mix']});
    control(g,'Sensitivity','sensitivity','number',{min:0,max:5,step:.1});control(g,'Threshold','threshold','number',{min:0,max:.99,step:.01});
    control(g,'Attack (s)','attack','number',{min:0,max:1,step:.01});control(g,'Decay (s)','decay','number',{min:.01,max:2,step:.01});
    control(g,'Every N events','beat_every','number',{min:1,max:16,step:1});control(g,'Event phase','beat_phase','number',{min:0,max:15,step:1});
    for(const [label,key,min,max]of [['Outline pulse (%)','react_outline',0,5],['Scale pulse (%)','react_scale',0,100],['X travel (%)','react_x',-50,50],['Y travel (%)','react_y',-50,50],['Opacity dip (%)','react_opacity',0,100],['Shadow pulse (%)','react_shadow',0,10]])control(g,label,key,'number',{factor:100,min,max,step:.1});
    g=group('Animation');control(g,'Treatment','preset','select',{values:MT.PRESETS});control(g,'Easing','easing','select',{values:['Smooth','Power out','Linear','Custom']},layer(),properties);
    for(const [label,key,max]of [['Start (s)','start',project.duration],['End (s)','end',project.duration],['Entrance (s)','enter',30],['Exit (s)','exit',30],['Stagger (s)','stagger',2]])control(g,label,key,'number',{min:0,max,step:.05});
    control(g,'Travel (%)','distance','number',{factor:100,min:0,max:100,step:1});
    if(layer().easing==='Custom'){
        for(let i=0;i<4;i++)control(g,['Bezier X1','Bezier Y1','Bezier X2','Bezier Y2'][i],String(i),'number',{min:0,max:1,step:.01},layer().curve,properties);
        const graph=document.createElement('canvas');graph.className='curve';graph.width=260;graph.height=110;graph.title='Drag the easing control points';g.append(graph);
        const paint=()=>{const ctx=graph.getContext('2d'),c=layer().curve;ctx.clearRect(0,0,260,110);ctx.strokeStyle='#55606b';ctx.lineWidth=1;
            ctx.beginPath();ctx.moveTo(10,100);ctx.lineTo(10+c[0]*240,100-c[1]*90);ctx.moveTo(250,10);ctx.lineTo(10+c[2]*240,100-c[3]*90);ctx.stroke();
            ctx.strokeStyle='#deff4a';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(10,100);ctx.bezierCurveTo(10+c[0]*240,100-c[1]*90,10+c[2]*240,100-c[3]*90,250,10);ctx.stroke();
            for(let i=0;i<4;i+=2){ctx.beginPath();ctx.arc(10+c[i]*240,100-c[i+1]*90,5,0,Math.PI*2);ctx.fillStyle='#82d6e7';ctx.fill();}};paint();
        graph.onpointerdown=e=>{saveUndo();const rect=graph.getBoundingClientRect(),x=(e.clientX-rect.left)/rect.width*260,y=(e.clientY-rect.top)/rect.height*110,c=layer().curve;
            const distance=i=>Math.hypot(x-(10+c[i]*240),y-(100-c[i+1]*90));const point=distance(0)<distance(2)?0:2;graph.setPointerCapture(e.pointerId);
            const move=ev=>{c[point]=Math.max(0,Math.min(1,((ev.clientX-rect.left)/rect.width*260-10)/240));c[point+1]=Math.max(0,Math.min(1,(100-(ev.clientY-rect.top)/rect.height*110)/90));paint();draw();};
            graph.onpointermove=move;graph.onpointerup=()=>{graph.onpointermove=null;properties();};};
    }
    keyProperties();
}
function keyProperties(){
    $('keys').replaceChildren();$('keyProperties').replaceChildren();
    layer().keyframes.forEach((k,i)=>{const o=document.createElement('option');o.value=i;o.textContent=`${formatTime(k.time)} s / ${Math.round(k.x*100)}, ${Math.round(k.y*100)} / ${k.scale.toFixed(2)}x`;$('keys').append(o);});
    $('keys').value=activeKey;
    if(activeKey<0||!layer().keyframes[activeKey])return;
    const key=layer().keyframes[activeKey],g=$('keyProperties');g.className='property-grid';
    for(const [label,name,min,max,factor,step]of [['X (%)','x',-100,200,100,.5],['Y (%)','y',-100,200,100,.5],['Scale','scale',.05,5,1,.05],['Rotation','rotation',-360,360,1,1],['Opacity (%)','opacity',0,100,100,1]])control(g,label,name,'number',{min,max,factor,step},key);
}
function setKey(){
    const l=layer(),t=Math.max(l.start,Math.min(l.end,current)),s=MT.state(l,t);
    let key=l.keyframes.find(k=>Math.abs(k.time-t)<.5/options.fps);
    if(!key){key={time:t,x:s.x,y:s.y,scale:s.scale,rotation:s.rotation,opacity:s.opacity};l.keyframes.push(key);l.keyframes.sort((a,b)=>a.time-b.time);}
    activeKey=l.keyframes.indexOf(key);keyProperties();drawTracks();return key;
}
function refresh(){
    selected=Math.min(selected,project.layers.length-1);$('scrub').max=project.duration;$('scrub').value=current;$('duration').value=project.duration;
    $('background').value=project.background;$('videoOffset').value=project.video_offset;
    $('format').value=options.format;$('fps').value=options.fps;$('blur').value=options.motion_blur;
    const res=`${options.width},${options.height}`;$('resolution').value=['1920,1080','3840,2160','1280,720'].includes(res)?res:'custom';
    $('dimensions').textContent=`${options.width} x ${options.height} / ${options.fps} FPS`;
    canvas.width=Math.min(1280,options.width);canvas.height=Math.round(canvas.width*options.height/options.width);
    $('stage').style.aspectRatio=`${options.width}/${options.height}`;
    $('stage').style.backgroundColor=project.background;
    $('stage').style.backgroundImage=options.format==='MP4 composite'?'none':'';
    listLayers();properties();drawTracks();loadVideo();audioStudio.refresh();updateState();draw();fitStage();
}
function fitStage(){const parent=$('stage').parentElement,r=options.width/options.height;$('stage').style.width=`${Math.min(parent.clientWidth-16,(parent.clientHeight-16)*r)}px`;}
new ResizeObserver(fitStage).observe($('stage').parentElement);
function videoURL(path){
    if(!path||/^[a-zA-Z]:|^[/\\]/.test(path))return '';
    path=path.replaceAll('\\','/');const index=path.lastIndexOf('/');
    return (options.viewURL||'/view')+'?'+new URLSearchParams({filename:path.slice(index+1),subfolder:path.slice(0,index<0?0:index),type:'input'});
}
function loadVideo(){
    const url=videoURL(options.video_file);$('videoName').textContent=options.video_file?options.video_file.split(/[\\/]/).at(-1):'No footage';
    if(url&&video.getAttribute('src')!==url){video.src=url;video.load();}
    if(!url){video.pause();video.removeAttribute('src');video.load();}
    video.style.display=url&&$('reference').checked?'block':'none';
    if(options.video_file&&!url)status('Upload this local-path video in the studio to preview it. Export can still use the path.');
}
video.addEventListener('error',()=>status('This footage cannot play in the browser. Use an H.264 MP4 for preview.'));
video.addEventListener('loadedmetadata',syncVideo);
$('reference').onchange=()=>loadVideo();$('guides').onchange=()=>{$('safeArea').hidden=!$('guides').checked;};
$('audio').onchange=()=>{audioStudio.play();syncVideo();};
$('text').onchange=()=>{saveUndo();layer().text=$('text').value||' ';listLayers();drawTracks();draw();updateState();};
function useCue(index){
    const reuse=$('cueAction').value==='selected';
    if(!reuse&&project.layers.length>=60)return status('Maximum 60 layers. Delete a layer or choose Time selected layer.');
    saveUndo();const cue=project.text_cues.splice(index,1)[0],next=clone(layer()),length=cue.end-cue.start;
    const keys=reuse?next.keyframes.map(k=>({...k,time:cue.start+(k.time-next.start)/(next.end-next.start)*length})):[];
    Object.assign(next,{text:reuse?next.text:'YOUR TEXT',start:cue.start,end:cue.end,keyframes:keys,enabled:true,
        enter:Math.min(next.enter,length*.25),exit:Math.min(next.exit,length*.2),stagger:Math.min(next.stagger,length*.05)});
    if(reuse)project.layers[selected]=next;else{project.layers.push(next);selected=project.layers.length-1;}
    selectLayer(selected);seek(cue.start+length*.5);updateState();
    $('text').focus();$('text').select();status(reuse?'Selected text aligned to the cue.':'Text layer added at the cue timing.');
}
$('cueMode').onchange=()=>{$('cueSource').disabled=$('cueMode').value!=='Hits';};
$('generateCues').onclick=()=>{
    try{
        const cues=MarioTextCues.generate(project,{mode:$('cueMode').value,source:$('cueSource').value,
            every:Number($('cueEvery').value),minimum:Number($('cueMinimum').value),fps:options.fps});
        saveUndo();project.text_cues=cues;project.cues_visible=true;drawTracks();updateState();
        status(cues.length?`${cues.length} text cues generated. Existing text layers are unchanged.`:'No cues found. Try a smaller event interval or minimum duration.');
    }catch(error){status(error.message);}
};
$('showCues').onchange=()=>{saveUndo();project.cues_visible=$('showCues').checked;drawTracks();updateState();};
$('clearCues').onclick=()=>{saveUndo();project.text_cues=[];drawTracks();updateState();};
$('add').onclick=()=>{if(project.layers.length>=60)return status('Maximum 60 layers.');saveUndo();project.layers.push(MT.makeLayer('YOUR NEXT LINE','Bold','Word cascade',project.duration));selectLayer(project.layers.length-1);updateState();};
$('duplicate').onclick=()=>{if(project.layers.length>=60)return;saveUndo();project.layers.push(clone(layer()));selectLayer(project.layers.length-1);updateState();};
$('delete').onclick=()=>{if(project.layers.length===1)return status('Keep at least one text layer.');saveUndo();project.layers.splice(selected,1);selected=Math.max(0,selected-1);refresh();};
for(const [id,delta]of [['up',1],['down',-1]])$(id).onclick=()=>{const next=selected+delta;if(next<0||next>=project.layers.length)return;saveUndo();[project.layers[selected],project.layers[next]]=[project.layers[next],project.layers[selected]];selectLayer(next);};
$('undo').onclick=()=>restore(history,future);$('redo').onclick=()=>restore(future,history);
$('addKey').onclick=()=>{saveUndo();setKey();updateState();};$('deleteKey').onclick=()=>{if(activeKey<0)return;saveUndo();layer().keyframes.splice(activeKey,1);activeKey=-1;keyProperties();draw();};
$('keys').onchange=()=>{activeKey=Number($('keys').value);seek(layer().keyframes[activeKey].time);keyProperties();};
for(const id of ['format','fps','blur','resolution'])$(id).onchange=()=>{
    saveUndo();if(id==='resolution'){if($('resolution').value==='custom')return;[options.width,options.height]=$('resolution').value.split(',').map(Number);}
    else if(id==='fps')options.fps=Math.max(1,Math.min(60,Math.round(Number($('fps').value)||30)));
    else options[id==='blur'?'motion_blur':id]=$(id).value;refresh();
};
$('background').onchange=()=>{saveUndo();project.background=$('background').value;refresh();};
$('videoOffset').onchange=()=>{saveUndo();project.video_offset=Math.max(0,Math.min(36000,Number($('videoOffset').value)||0));syncVideo();};
$('duration').onchange=()=>{
    const value=Number($('duration').value);if(!Number.isFinite(value)||value<.1||value>600)return;
    const last=Math.max(...project.layers.map(l=>l.end));if(value<last){status(`Duration must reach the last layer at ${last.toFixed(2)} s. Trim layers first.`);$('duration').value=project.duration;return;}
    saveUndo();project.duration=value;project.text_cues=(project.text_cues||[]).filter(c=>c.start<value).map(c=>({...c,end:Math.min(c.end,value)}));refresh();
};
$('marker').onclick=()=>{saveUndo();project.markers=[...new Set([...project.markers,Math.round(current*options.fps)/options.fps])].sort((a,b)=>a-b);drawTracks();};
$('clearMarkers').onclick=()=>{saveUndo();project.markers=[];drawTracks();};
$('beatGrid').onclick=()=>{const bpm=Number($('bpm').value);if(!Number.isFinite(bpm)||bpm<20||bpm>300)return;saveUndo();project.markers=[];
    if(project.audio.analysis){project.audio.bpm_override=bpm;project.text_cues=[];project.markers=MT.timelineBeats(project);audioStudio.refresh();}
    else for(let t=0;t<=project.duration;t+=60/bpm)project.markers.push(t);drawTracks();};
$('zoom').oninput=()=>{$('timelineContent').style.width=`${Number($('zoom').value)*100}%`;};
function snap(t){
    t=Math.round(t*options.fps)/options.fps;
    if($('snap').checked){const near=project.markers.reduce((a,b)=>Math.abs(b-t)<Math.abs(a-t)?b:a,t+.09);if(Math.abs(near-t)<.08)t=near;}
    return Math.max(0,Math.min(project.duration,t));
}
function dragClip(e,index,edge){
    e.preventDefault();selectLayer(index);saveUndo();const l=layer(),start=l.start,end=l.end,x=e.clientX;
    const keys=clone(l.keyframes),width=$('tracks').getBoundingClientRect().width;
    const move=ev=>{
        const delta=(ev.clientX-x)/width*project.duration;
        if(edge==='start')l.start=Math.min(l.end-.05,snap(start+delta));
        else if(edge==='end')l.end=Math.max(l.start+.05,snap(end+delta));
        else{const duration=end-start;l.start=Math.max(0,Math.min(project.duration-duration,snap(start+delta)));l.end=l.start+duration;}
        l.keyframes=keys.map(k=>({...k,time:edge?k.time:k.time+l.start-start})).filter(k=>k.time>=l.start&&k.time<=l.end);
        drawTracks();draw();
    };
    const endDrag=()=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',endDrag);properties();updateState();};
    window.addEventListener('pointermove',move);window.addEventListener('pointerup',endDrag);
}
$('ruler').onpointerdown=e=>{const rect=$('ruler').getBoundingClientRect();seek((e.clientX-rect.left)/rect.width*project.duration);};
canvas.onpointerdown=e=>{
    if(playing)return;e.preventDefault();const rect=canvas.getBoundingClientRect(),x=(e.clientX-rect.left)/rect.width*canvas.width,y=(e.clientY-rect.top)/rect.height*canvas.height;
    let hit=-1;for(let i=bounds.length-1;i>=0;i--){const b=bounds[i];if(b&&x>=b.x&&x<=b.x+b.width&&y>=b.y&&y<=b.y+b.height){hit=i;break;}}
    if(hit>=0&&hit!==selected)selectLayer(hit);
    const b=bounds[selected];if(!b)return;saveUndo();
    const resize=Math.abs(x-b.x-b.width)<24&&Math.abs(y-b.y-b.height)<24;
    const target=layer().keyframes.length?setKey():layer();const initial={x:target.x,y:target.y,width:layer().width,height:layer().height,size:layer().size};
    const sx=e.clientX,sy=e.clientY;canvas.setPointerCapture(e.pointerId);
    const move=ev=>{const dx=(ev.clientX-sx)/rect.width,dy=(ev.clientY-sy)/rect.height;
        if(resize){layer().width=Math.max(.02,Math.min(2,initial.width+dx*2));layer().height=Math.max(.02,Math.min(2,initial.height+dy*2));if(!layer().fit)layer().size=Math.max(.005,Math.min(1.5,initial.size+dy));}
        else{target.x=Math.max(-1,Math.min(2,initial.x+dx));target.y=Math.max(-1,Math.min(2,initial.y+dy));}draw();};
    const end=()=>{canvas.removeEventListener('pointermove',move);canvas.removeEventListener('pointerup',end);properties();updateState();};
    canvas.addEventListener('pointermove',move);canvas.addEventListener('pointerup',end);
};
function stop(){playing=false;video.pause();audioStudio.stop();icon('play','play');draw();}
$('play').onclick=()=>{if(playing)return stop();if(current>=project.duration)seek(0);playing=true;lastTick=performance.now();icon('play','pause');audioStudio.play();syncVideo();if(video.src)video.play().catch(()=>{});};
$('home').onclick=()=>seek(0);$('scrub').oninput=()=>seek(Number($('scrub').value));
function tick(now){if(playing){current=Math.min(project.duration,current+(now-lastTick)/1000);lastTick=now;$('scrub').value=current;syncVideo();draw();if(current>=project.duration)stop();}requestAnimationFrame(tick);}requestAnimationFrame(tick);
$('upload').onclick=()=>$('file').click();
$('file').onchange=async()=>{
    const file=$('file').files[0];if(!file)return;
    $('upload').disabled=true;status('Uploading footage...');
    try{const body=new FormData();body.append('image',file,file.name.replace(/[^a-zA-Z0-9._-]/g,'_'));body.append('type','input');body.append('subfolder','mariotyport/'+crypto.randomUUID());
        const response=await fetch(options.uploadURL||'/upload/image',{method:'POST',body});if(!response.ok)throw Error(`Upload failed (${response.status}).`);
        const result=await response.json();saveUndo();options.video_file=result.subfolder+'/'+result.name;loadVideo();status('');
    }catch(error){status(error.message);}finally{$('upload').disabled=false;$('file').value='';}
};
$('removeVideo').onclick=()=>{saveUndo();options.video_file='';loadVideo();status('');};
function send(type){parent.postMessage({type,project:clone(project),options:clone(options)},location.origin);}
$('close').onclick=()=>{stop();audioStudio.dispose();send('mariotyport-cancel');};$('apply').onclick=()=>{document.activeElement.blur();stop();audioStudio.dispose();send('mariotyport-apply');};
document.addEventListener('keydown',e=>{if(e.key==='Escape')$('close').click();if(!['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)){if(e.code==='Space'){e.preventDefault();$('play').click();}if((e.ctrlKey||e.metaKey)&&e.key==='z'){e.preventDefault();e.shiftKey?restore(future,history):restore(history,future);}}});
window.addEventListener('message',async e=>{
    if(e.source!==parent||e.origin!==location.origin||e.data.type!=='mariotyport-init')return;
    try{options={...options,...e.data.options};project=clone(e.data.project);project.audio={...MT.makeAudio(),...project.audio};project.layers=project.layers.map(l=>({...MT.makeLayer(),...l}));current=Math.min(1,project.duration/2);await MT.loadFonts(new URL('./fonts/',location.href).href);ready=true;refresh();parent.postMessage({type:'mariotyport-ready'},location.origin);}
    catch(error){status(error.message);}
});
// The host sends state only after this document's message listener is installed.
parent.postMessage({type:'mariotyport-loaded'},location.origin);
})();
