window.createMarioAudioStudio = function({project,options,time,playing,saveUndo,changed,seek,status}) {
    const $=id=>document.getElementById(id),audio=new Audio(),wave=$('audioWave');
    audio.preload='metadata';let busy=false,generation=0,context=null,gainNode=null;
    const track=()=>project().audio;
    const fields={audioIn:'trim_start',audioOut:'trim_end',audioStart:'start',audioGain:'gain',audioMute:'muted',audioBpm:'bpm_override',beatOffset:'beat_offset'};
    function url(file){file=file.replaceAll('\\','/');const i=file.lastIndexOf('/');return options().viewURL+'?'+new URLSearchParams({filename:file.slice(i+1),subfolder:i<0?'':file.slice(0,i),type:'input'});}
    function markers(){project().markers=MarioType.timelineBeats(project());}
    function refresh(){
        const a=track();$('audioName').textContent=a.file?a.file.split('/').at(-1):'No soundtrack';
        const next=a.file?url(a.file):'';
        if(next&&audio.getAttribute('src')!==next){audio.src=next;audio.load();}
        if(!next&&audio.getAttribute('src')){audio.pause();audio.removeAttribute('src');audio.load();}
        for(const [id,key]of Object.entries(fields)){
            if(key==='muted')$(id).checked=a[key];else $(id).value=key==='gain'?Math.round(a[key]*100):a[key];
        }
        $('analyzeAudio').disabled=!a.file||busy;$('uploadAudio').disabled=busy;
        $('analysisDevice').disabled=busy||$('analysisMode').value!=='stems';$('analysisMode').disabled=busy;
        $('analysisBusy').hidden=!busy;
        $('analysisStatus').textContent=busy?'Analyzing audio...':a.analysis?`${a.analysis.bpm.toFixed(1)} BPM / ${a.analysis.beats.length} beats / ${Object.keys(a.analysis.channels).length} sources${a.analysis.separation_device?' / '+(a.analysis.separation_device==='cuda'?'GPU':'CPU'):''}`:a.file?'Not analyzed':'';
        drawWave();sync();
    }
    function drawWave(){
        const a=track(),data=a.analysis,rect=wave.getBoundingClientRect();wave.width=Math.max(1,Math.min(16000,Math.round(rect.width*devicePixelRatio)));wave.height=54*devicePixelRatio;
        const clip=$('audioClip');clip.hidden=!a.file;clip.style.left=`${a.start/project().duration*100}%`;clip.style.width=`${(a.trim_end-a.trim_start)/project().duration*100}%`;
        const ctx=wave.getContext('2d'),w=wave.width,h=wave.height;ctx.fillStyle='#152522';ctx.fillRect(0,0,w,h);
        ctx.strokeStyle='#609f91';ctx.beginPath();ctx.moveTo(0,h/2);ctx.lineTo(w,h/2);ctx.stroke();
        if(data){ctx.fillStyle='#79cbbb';
            for(let x=0;x<w;x++){
                const t=x/w*project().duration,source=t-a.start+a.trim_start;
                if(t<a.start||source<a.trim_start||source>=a.trim_end)continue;
                const index=Math.min(data.waveform.length-1,Math.floor(source/data.duration*data.waveform.length));
                const height=Math.max(1,data.waveform[index]*h*.8);ctx.fillRect(x,(h-height)/2,1,height);
            }
            ctx.fillStyle='#edcd73';for(const t of MarioType.timelineBeats(project()))ctx.fillRect(t/project().duration*w,0,Math.max(1,devicePixelRatio),h);
        }
        ctx.font=`${10*devicePixelRatio}px Arial`;ctx.fillStyle='#dcf0e9';ctx.fillText(a.file?'AUDIO'+(a.muted?' / MUTED':''):'AUDIO',6*devicePixelRatio,12*devicePixelRatio);
    }
    function sync(){
        const a=track(),source=time()-a.start+a.trim_start,active=a.file&&time()>=a.start&&source>=a.trim_start&&source<a.trim_end;
        const monitor=$('audio').checked;
        audio.muted=!monitor||a.muted;
        if(gainNode)gainNode.gain.value=a.gain;
        if(active&&Number.isFinite(audio.duration)){
            const target=Math.min(source,Math.max(0,audio.duration-.001));
            if(Math.abs(audio.currentTime-target)>.045)audio.currentTime=target;
            if(playing()&&audio.paused)audio.play().catch(()=>{});
        }
        if(!active||!playing())audio.pause();
    }
    function play(){
        if(track().file&&!context){context=new AudioContext();gainNode=context.createGain();context.createMediaElementSource(audio).connect(gainNode).connect(context.destination);}
        context?.resume();sync();
    }
    audio.addEventListener('loadedmetadata',()=>{sync();});
    audio.addEventListener('error',()=>status('Audio preview could not decode this file. Try WAV or MP3.'));
    for(const [id,key]of Object.entries(fields))$(id).onchange=()=>{
        const a=track(),old=a[key];let value=key==='muted'?$(id).checked:Number($(id).value);
        if(key==='gain')value/=100;
        const maximum=key==='gain'?2:key==='bpm_override'?300:key==='beat_offset'?5:600;
        if(key!=='muted'&&(!Number.isFinite(value)||value<(key==='beat_offset'?-5:0)||value>maximum||(key==='bpm_override'&&value>0&&value<20))){refresh();return;}
        saveUndo();a[key]=value;
        if(a.trim_end<=a.trim_start||(a.analysis&&a.trim_end>a.analysis.duration)){a[key]=old;status('Audio out must be after in and within the analyzed audio.');}
        if(a[key]!==old&&['trim_start','trim_end','start','bpm_override','beat_offset'].includes(key))project().text_cues=[];
        if(a.analysis)markers();refresh();changed();
    };
    $('useAudioBeats').onclick=()=>{if(!track().analysis)return status('Analyze the soundtrack first.');saveUndo();markers();changed();};
    $('uploadAudio').onclick=()=>$('audioFile').click();
    $('audioFile').onchange=async()=>{
        const file=$('audioFile').files[0];if(!file)return;const id=++generation;busy=true;refresh();status('Uploading audio...');
        try{
            const form=new FormData();form.append('image',file,file.name.replace(/[^a-zA-Z0-9._-]/g,'_'));form.append('type','input');form.append('subfolder','mariotyport/audio/'+crypto.randomUUID());
            const response=await fetch(options().uploadURL,{method:'POST',body:form});if(!response.ok)throw Error(`Audio upload failed (${response.status}).`);
            const data=await response.json();if(id!==generation)return;
            saveUndo();project().audio={...MarioType.makeAudio(),file:data.subfolder+'/'+data.name,trim_end:project().duration};
            $('audio').checked=true;
            project().layers.forEach(l=>l.react_mode='Off');project().markers=[];project().text_cues=[];refresh();changed(true);
            status('Audio uploaded. Analyze it to draw the waveform and detect beats.');
        }catch(error){status(error.message);}finally{busy=false;$('audioFile').value='';refresh();}
    };
    $('analysisMode').onchange=()=>{$('analysisDevice').disabled=busy||$('analysisMode').value!=='stems';};
    $('analyzeAudio').onclick=async()=>{
        if(busy||!track().file)return;const id=++generation,file=track().file;busy=true;refresh();
        status($('analysisMode').value==='stems'?`Separating instruments (${$('analysisDevice').selectedOptions[0].text}); please wait.`:'Detecting beats and frequency-band energy...');
        try{
            const response=await fetch(options().analyzeURL,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({file,instruments:$('analysisMode').value==='stems',device:$('analysisDevice').value})});
            const data=await response.json();if(!response.ok)throw Error(data.error||'Audio analysis failed.');
            if(id!==generation||track().file!==file)return;
            saveUndo();if(track().analysis?.fingerprint===data.fingerprint){
                data.channels={...track().analysis.channels,...data.channels};
                if(!data.separation_device&&track().analysis.separation_device)data.separation_device=track().analysis.separation_device;
            }
            project().text_cues=[];track().analysis=data;track().trim_end=Math.min(track().trim_end||data.duration,data.duration);
            track().trim_start=Math.min(track().trim_start,Math.max(0,track().trim_end-.01));markers();changed(true);
            status(data.beats.length?'Audio analysis ready.':'No stable beats detected. Energy mode is still available.');
        }catch(error){status(error.message);}finally{busy=false;refresh();}
    };
    $('removeAudio').onclick=()=>{saveUndo();generation++;project().audio=MarioType.makeAudio();project().layers.forEach(l=>l.react_mode='Off');project().markers=[];project().text_cues=[];refresh();changed(true);};
    wave.onpointerdown=e=>{const rect=wave.getBoundingClientRect();seek((e.clientX-rect.left)/rect.width*project().duration);};
    $('audioClip').onpointerdown=e=>{
        if(busy)return;e.preventDefault();$('audioClip').setPointerCapture(e.pointerId);saveUndo();const a=track(),initial={...a},x=e.clientX,rect=wave.getBoundingClientRect(),edge=e.target.dataset.edge;
        let moved=false;
        const move=ev=>{
            moved=moved||Math.abs(ev.clientX-x)>3;
            const delta=Math.round((ev.clientX-x)/rect.width*project().duration*options().fps)/options().fps;
            if(edge==='in'){
                const d=Math.max(-initial.start,-initial.trim_start,Math.min(initial.trim_end-initial.trim_start-.05,delta));
                a.start=initial.start+d;a.trim_start=initial.trim_start+d;
            }else if(edge==='out')a.trim_end=Math.max(a.trim_start+.05,Math.min(a.analysis?.duration||600,initial.trim_end+delta));
            else a.start=Math.max(0,Math.min(project().duration-.05,initial.start+delta));
            if(a.start!==initial.start||a.trim_start!==initial.trim_start||a.trim_end!==initial.trim_end)project().text_cues=[];
            if(a.analysis)markers();refresh();changed();
        };
        const end=ev=>{window.removeEventListener('pointermove',move);window.removeEventListener('pointerup',end);window.removeEventListener('pointercancel',end);
            if(!moved&&ev.type==='pointerup')seek((ev.clientX-rect.left)/rect.width*project().duration);};
        window.addEventListener('pointermove',move);window.addEventListener('pointerup',end);window.addEventListener('pointercancel',end);
    };
    new ResizeObserver(drawWave).observe(wave);
    return {refresh,sync,play,drawWave,stop:()=>audio.pause(),dispose:()=>{generation++;audio.pause();audio.removeAttribute('src');audio.load();context?.close();}};
};
