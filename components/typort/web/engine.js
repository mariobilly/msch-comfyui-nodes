/* The editor and export worker deliberately use the same canvas renderer. */
(() => {
    const clamp = (v, a = 0, b = 1) => Math.max(a, Math.min(b, v));
    const rtl = text => /[\u0590-\u08ff]/u.test(text);
    const FONTS = ['Black', 'ExtraBold', 'Bold', 'Medium', 'Regular', 'Light', 'ExtraLight'];
    const PRESETS = ['Line reveal', 'Word cascade', 'Scale impact', 'Editorial drift', 'Side sweep', 'Tracking reveal', 'Rise', 'Fade', 'Static'];
    const makeAudio=()=>({file:'',trim_start:0,trim_end:0,start:0,gain:1,muted:false,bpm_override:0,beat_offset:0,analysis:null});
    function makeLayer(text = 'MAKE\nIT MATTER', font = 'Black', preset = 'Line reveal', duration = 5) {
        return {text, font, preset, start:0, end:duration, x:.5, y:.5, width:.9, height:.8, size:.4,
            fit:true, align:'center', direction:'auto', line_height:1, tracking:0, color:'#FFFFFF', opacity:1,
            stroke_color:'#111111', stroke:0, shadow_color:'#000000', shadow_opacity:.45,
            shadow_blur:.015, shadow_x:.005, shadow_y:.012, block_color:'#DEFF4A', block_opacity:0,
            padding:.015, rotation:0, scale:1, anchor_x:.5, anchor_y:.5, enter:.8, exit:.5, stagger:.12,
            distance:.1, easing:'Power out', curve:[.22,1,.36,1], enabled:true, keyframes:[],
            react_mode:'Off',react_source:'Mix',sensitivity:1,threshold:.1,attack:0,decay:.18,
            beat_every:1,beat_phase:0,react_outline:.006,react_scale:.04,react_x:0,react_y:0,react_opacity:0,react_shadow:0};
    }
    const makeProject = (text, font, preset, duration = 5) => ({version:1, duration, background:'#121416', video_offset:0, markers:[], text_cues:[], cues_visible:true, audio:makeAudio(), layers:[makeLayer(text,font,preset,duration)]});
    function audioBeats(track){
        const a=track?.analysis;if(!a)return [];
        if(!track.bpm_override)return a.beats.map(t=>t+track.beat_offset).filter(t=>t>=0&&t<a.duration);
        const step=60/track.bpm_override,origin=(a.beats[0]||0)+track.beat_offset,beats=[];
        for(let t=origin-Math.floor(origin/step)*step;t<a.duration;t+=step)if(t>=0)beats.push(t);
        return beats;
    }
    function timelineBeats(project){const a=project.audio;return audioBeats(a).filter(t=>t>=a.trim_start&&t<a.trim_end).map(t=>t-a.trim_start+a.start).filter(t=>t<=project.duration);}
    function lowerBound(values,t){let lo=0,hi=values.length;while(lo<hi){const mid=(lo+hi)>>1;if(values[mid]<t)lo=mid+1;else hi=mid;}return lo;}
    function reaction(project,l,time,cache){
        const track=project.audio,a=track?.analysis;
        if(!a||!l.react_mode||l.react_mode==='Off')return 0;
        const t=time-track.start+track.trim_start;
        if(time<track.start||t<track.trim_start||t>=track.trim_end)return 0;
        const channel=a.channels[l.react_source];if(!channel)return 0;
        const level=t=>channel.levels[clamp(Math.round(t*a.rate),0,channel.levels.length-1)]||0;
        let value=0;
        if(l.react_mode==='Energy'){
            const key=`${l.react_source}:${l.attack}:${l.decay}`;
            let bank=cache.get(a);if(!bank){bank=new Map();cache.set(a,bank);}
            if(!bank.has(key)){
                if(bank.size>=32)bank.clear();
                let previous=0;
                const smooth=channel.levels.map(v=>{const seconds=v>previous?l.attack:l.decay;const alpha=seconds?1-Math.exp(-1/(a.rate*seconds)):1;previous+=alpha*(v-previous);return previous;});
                bank.set(key,smooth);
            }
            const values=bank.get(key),index=t*a.rate,i=Math.floor(index),f=index-i;
            value=(values[i]||0)*(1-f)+(values[Math.min(i+1,values.length-1)]||0)*f;
        }else{
            const events=l.react_mode==='Beats'?audioBeats(track):channel.hits;
            const start=lowerBound(events,t-l.attack-l.decay*8),end=lowerBound(events,t+1e-7);
            for(let i=start;i<end;i++){
                if(i%l.beat_every!==l.beat_phase%l.beat_every)continue;
                const dt=t-events[i];
                const strength=l.react_mode==='Beats'&&l.react_source==='Mix'?1:Math.max(level(events[i]),level(events[i]+.04),level(events[i]+.08));
                const pulse=l.attack&&dt<l.attack?dt/l.attack:Math.exp(-Math.max(0,dt-l.attack)/l.decay);
                value=Math.max(value,strength*pulse);
            }
        }
        return clamp((value*l.sensitivity-l.threshold)/Math.max(.01,1-l.threshold));
    }
    async function loadFonts(base) {
        await Promise.all(FONTS.map(async name => {
            const font = new FontFace(`MT-${name}`, `url("${base}Tajawal-${name}.ttf")`);
            await font.load(); document.fonts.add(font);
        }));
        await document.fonts.ready;
    }
    function ease(t, layer) {
        t = clamp(t);
        if (layer.easing === 'Linear') return t;
        if (layer.easing === 'Smooth') return t*t*(3-2*t);
        if (layer.easing !== 'Custom') return 1 - (1-t)**4;
        const [x1,y1,x2,y2] = layer.curve;
        const cubic = (s,a,b) => 3*(1-s)**2*s*a+3*(1-s)*s*s*b+s**3;
        let a=0, b=1;
        for (let i=0;i<20;i++) { const m=(a+b)/2; if(cubic(m,x1,x2)<t) a=m; else b=m; }
        return cubic((a+b)/2,y1,y2);
    }
    function state(layer, t) {
        const keys=layer.keyframes;
        if (!keys?.length) return layer;
        if(t<=keys[0].time) return {...layer,...keys[0]};
        if(t>=keys.at(-1).time) return {...layer,...keys.at(-1)};
        const end=keys.findIndex(k=>k.time>=t), a=keys[end-1], b=keys[end];
        const q=ease((t-a.time)/(b.time-a.time),layer), out={...layer};
        for(const name of ['x','y','scale','rotation','opacity']) out[name]=a[name]+(b[name]-a[name])*q;
        return out;
    }
    function font(ctx, layer, size, spacing) {
        ctx.font = `${size}px "MT-${layer.font}"`;
        ctx.letterSpacing = `${spacing}px`;
        ctx.textBaseline='alphabetic'; ctx.textAlign='left';
        ctx.direction=layer.direction==='auto' ? (rtl(layer.text)?'rtl':'ltr') : layer.direction;
    }
    function layout(ctx, layer, w, h) {
        const unit=Math.min(w,h), maxW=w*layer.width, maxH=h*layer.height;
        let size=layer.size*unit, lines=[], metrics=[];
        const spacing=rtl(layer.text)?0:layer.tracking*unit;
        function measure() {
            font(ctx,layer,size,spacing); lines=[];
            for(const paragraph of layer.text.split('\n')) {
                const words=paragraph.split(/\s+/u); let line='';
                for(const word of words) {
                    const candidate=line ? `${line} ${word}` : word;
                    if(layer.fit && line && ctx.measureText(candidate).width>maxW) { lines.push(line); line=word; }
                    else line=candidate;
                }
                lines.push(line);
            }
            metrics=lines.map(line=>ctx.measureText(line));
        }
        measure();
        if(layer.fit) {
            for(let i=0;i<12;i++) {
                const factor=Math.min(1,maxW/Math.max(1,...metrics.map(m=>m.width)),maxH/(size*layer.line_height*lines.length));
                if(factor>=.999) break;
                size*=factor*.995; measure();
            }
        }
        const height=size*layer.line_height*lines.length;
        const width=Math.max(1,...metrics.map(m=>m.width));
        return {lines,metrics,size,spacing,width,height,lineHeight:size*layer.line_height};
    }
    function drawLayer(ctx, original, time, w, h, project, cache) {
        if(!original.enabled || time<original.start || time>=original.end) return null;
        const layer={...state(original,time)}, amount=reaction(project,original,time,cache);
        if(amount){layer.scale*=1+amount*original.react_scale;layer.x+=amount*original.react_x;layer.y+=amount*original.react_y;
            layer.stroke+=amount*original.react_outline;layer.opacity*=1-original.react_opacity*(1-amount);layer.shadow_blur+=amount*original.react_shadow;}
        else if(original.react_mode&&original.react_mode!=='Off')layer.opacity*=1-original.react_opacity;
        const l=layout(ctx,layer,w,h), unit=Math.min(w,h);
        const local=time-layer.start, duration=layer.end-layer.start;
        const enter=Math.min(layer.enter,duration*.45), exit=Math.min(layer.exit,duration*.45);
        const inQ=enter ? ease(local/enter,layer):1;
        const outQ=exit ? ease((duration-local)/exit,layer):1;
        let scale=layer.scale, dy=0, dx=0;
        if(layer.preset==='Scale impact') scale*=1+.75*(1-inQ);
        if(layer.preset==='Editorial drift') { scale*=1+.055*local/duration; dx=unit*.025*(local/duration-.5); }
        if(layer.preset==='Side sweep') dx=unit*layer.distance*(1-inQ);
        if(layer.preset==='Rise') dy=unit*layer.distance*(1-inQ);
        ctx.save();
        ctx.translate(w*layer.x+dx,h*layer.y+dy); ctx.rotate(layer.rotation*Math.PI/180); ctx.scale(scale,scale);
        ctx.translate(-l.width*layer.anchor_x,-l.height*layer.anchor_y);
        let opacity=layer.opacity*(layer.preset==='Static'?1:outQ);
        if(['Fade','Rise','Side sweep','Editorial drift','Tracking reveal'].includes(layer.preset)) opacity*=inQ;
        ctx.globalAlpha=opacity;
        const pad=layer.padding*unit;
        if(layer.block_opacity>0) {
            ctx.save(); ctx.globalAlpha*=layer.block_opacity; ctx.fillStyle=layer.block_color;
            ctx.fillRect(-pad,-pad,l.width+2*pad,l.height+2*pad); ctx.restore();
        }
        let animatedSpacing=l.spacing;
        if(layer.preset==='Tracking reveal' && !rtl(layer.text)) animatedSpacing+=unit*.02*(1-inQ);
        font(ctx,layer,l.size,animatedSpacing);
        ctx.fillStyle=layer.color; ctx.strokeStyle=layer.stroke_color; ctx.lineWidth=layer.stroke*unit*2;
        ctx.lineJoin='round';
        const rgb=layer.shadow_color.match(/\w\w/g).map(x=>parseInt(x,16));
        ctx.shadowColor=`rgba(${rgb.join(',')},${layer.shadow_opacity})`;
        ctx.shadowBlur=layer.shadow_blur*unit;
        ctx.shadowOffsetX=layer.shadow_x*unit; ctx.shadowOffsetY=layer.shadow_y*unit;
        let itemIndex=0;
        const wordCount=l.lines.reduce((n,line)=>n+line.split(/\s+/u).length,0);
        const count=layer.preset==='Word cascade'&&!rtl(layer.text)?wordCount:l.lines.length;
        const stagger=Math.min(layer.stagger,enter*.6/Math.max(1,count-1));
        const revealTime=Math.max(.001,enter-stagger*Math.max(0,count-1));
        l.lines.forEach((line,row)=> {
            const lineWidth=ctx.measureText(line).width;
            const x=layer.align==='left'?0:layer.align==='right'?l.width-lineWidth:(l.width-lineWidth)/2;
            const metric=l.metrics[row];
            const ascent=metric.actualBoundingBoxAscent || l.size*.75;
            const descent=metric.actualBoundingBoxDescent || l.size*.2;
            const baseline=row*l.lineHeight+(l.lineHeight-ascent-descent)/2+ascent;
            const paint=(text,tx,delay) => {
                const q=enter?ease((local-delay)/revealTime,layer):1;
                ctx.save();
                if(layer.preset==='Line reveal' || (layer.preset==='Word cascade' && rtl(layer.text))) {
                    ctx.beginPath(); ctx.rect(-pad,row*l.lineHeight-pad,l.width+2*pad,l.lineHeight+pad*2); ctx.clip();
                    ctx.translate(0,(1-q)*l.lineHeight*1.2);
                } else if(layer.preset==='Word cascade') {
                    ctx.globalAlpha*=q; ctx.translate(0,(1-q)*unit*layer.distance);
                }
                if(layer.stroke>0) ctx.strokeText(text,tx,baseline);
                ctx.fillText(text,tx,baseline); ctx.restore();
            };
            if(layer.preset==='Word cascade'&&!rtl(layer.text)) {
                const words=line.split(/\s+/u); let prefix='';
                for(const word of words) {
                    paint(word,x+ctx.measureText(prefix).width,itemIndex++*stagger); prefix+=word+' ';
                }
            } else paint(line,x,row*stagger);
        });
        ctx.restore();
        return {x:w*layer.x-l.width*layer.anchor_x,y:h*layer.y-l.height*layer.anchor_y,width:l.width,height:l.height};
    }
    function createRenderer(canvas) {
        const ctx=canvas.getContext('2d'), sample=document.createElement('canvas');
        const audioCache=new WeakMap();
        const sc=sample.getContext('2d');
        return {
            render(project,time,{samples=1,fps=30}={}) {
                const w=canvas.width,h=canvas.height;
                if(sample.width!==w||sample.height!==h) {sample.width=w;sample.height=h;}
                ctx.clearRect(0,0,w,h); const bounds=[];
                ctx.save(); ctx.globalCompositeOperation='lighter'; ctx.globalAlpha=1/samples;
                for(let i=0;i<samples;i++) {
                    sc.clearRect(0,0,w,h);
                    const t=time+(samples===1?0:(i/(samples-1)-.5)*.5/fps);
                    project.layers.forEach((l,index)=> {const box=drawLayer(sc,l,t,w,h,project,audioCache); if(i===0) bounds[index]=box;});
                    ctx.drawImage(sample,0,0);
                }
                ctx.restore(); return bounds;
            }
        };
    }
    window.MarioType={FONTS,PRESETS,makeLayer,makeProject,makeAudio,audioBeats,timelineBeats,reaction,loadFonts,createRenderer,layout,state,ease};
})();
