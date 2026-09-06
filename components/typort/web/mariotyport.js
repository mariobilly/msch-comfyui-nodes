import { app } from '../../../scripts/app.js';
import { api } from '../../../scripts/api.js';
import './engine.js';

function notify(detail,severity='error') { app.extensionManager.toast.add({severity,summary:'mariotyport',detail,life:9000}); }
function studio(node) {
    const get=name=>node.widgets.find(w=>w.name===name).value;
    let project;
    try { project=get('project_json').trim()?JSON.parse(get('project_json')):MarioType.makeProject(get('text'),get('font'),get('animation'),get('duration')); }
    catch(error){return notify('Invalid project JSON: '+error.message);}
    if(project.version!==1||!Array.isArray(project.layers)||!project.layers.length)return notify('Expected a version 1 mariotyport project with layers.');
    const dialog=document.createElement('dialog');
    Object.assign(dialog.style,{width:'100vw',height:'100dvh',maxWidth:'100vw',maxHeight:'100dvh',padding:'0',border:'0',margin:'0',background:'#17191c',pointerEvents:'auto'});
    const frame=document.createElement('iframe');frame.src=new URL('./editor.html',import.meta.url).href;frame.title='mariotyport studio';
    Object.assign(frame.style,{width:'100%',height:'100%',border:'0',display:'block',pointerEvents:'auto'});dialog.append(frame);document.body.append(dialog);dialog.showModal();
    const options={};for(const name of ['width','height','fps','format','motion_blur','video_file'])options[name]=get(name);
    options.uploadURL=api.apiURL('/upload/image');options.viewURL=api.apiURL('/view');
    options.analyzeURL=api.apiURL('/mariotyport/analyze-audio');
    const close=()=>{window.removeEventListener('message',listener);dialog.close();dialog.remove();};
    const listener=e=>{
        if(e.source!==frame.contentWindow||e.origin!==location.origin)return;
        if(e.data.type==='mariotyport-loaded')frame.contentWindow.postMessage({type:'mariotyport-init',project,options},location.origin);
        if(e.data.type==='mariotyport-cancel')close();
        if(e.data.type==='mariotyport-apply'){
            node.widgets.find(w=>w.name==='project_json').value=JSON.stringify(e.data.project);
            for(const name of ['width','height','fps','format','motion_blur','video_file'])node.widgets.find(w=>w.name===name).value=e.data.options[name];
            node.widgets.find(w=>w.name==='duration').value=e.data.project.duration;
            node.setDirtyCanvas(true,true);close();
        }
    };
    window.addEventListener('message',listener);dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
}
app.registerExtension({name:'mariotyport.studio',async beforeRegisterNodeDef(type,data){
    if(data.name!=='MarioTyport')return;
    const original=type.prototype.onNodeCreated;
    type.prototype.onNodeCreated=function(){
        const result=original?.apply(this,arguments);this.color='#3b4431';this.bgcolor='#202326';
        this.addWidget('button','Open typography studio',null,()=>studio(this),{serialize:false});
        this.addWidget('button','Reset to node text',null,()=>{if(confirm('Discard the studio timeline and use the node text and animation?'))this.widgets.find(w=>w.name==='project_json').value='';},{serialize:false});
        for(const name of ['text','font','animation','duration']){
            const w=this.widgets.find(w=>w.name===name),callback=w.callback;
            w.callback=function(...args){callback?.apply(this,args);if(this.node?.widgets?.find(w=>w.name==='project_json')?.value?.trim())notify('Studio timeline is active. Edit it in the studio or reset to node text.','warn');};
        }
        const box=document.createElement('div'),video=document.createElement('video'),download=document.createElement('a'),path=document.createElement('div');
        video.controls=true;video.loop=true;video.playsInline=true;video.preload='metadata';
        Object.assign(video.style,{width:'100%',maxHeight:'320px',display:'block',background:'#17191b'});
        Object.assign(download.style,{display:'block',color:'#deff4a',padding:'8px',font:'12px Arial'});
        Object.assign(path.style,{font:'11px Arial',color:'#adb5bd',padding:'6px',overflowWrap:'anywhere'});
        box.append(video,download,path);box.style.display='none';
        for(const event of ['pointerdown','pointermove','pointerup','wheel'])box.addEventListener(event,e=>e.stopPropagation());
        const widget=this.addDOMWidget('mariotyport_preview','mariotyport_video',box,{serialize:false});
        widget.serializeValue=()=>undefined;let visible=false;
        widget.computeSize=width=>[Math.max(400,width),visible?Math.min(320,(this.size[0]-20)*9/16)+90:0];
        const executed=this.onExecuted;
        this.onExecuted=function(output){executed?.apply(this,arguments);const item=output.mariotyport_video?.[0];if(!item)return;
            video.src=api.apiURL('/view?'+new URLSearchParams(item));
            const file=output.mariotyport_export?.[0];download.hidden=!file;
            if(file){download.href=api.apiURL('/view?'+new URLSearchParams(file));download.download=file.filename;download.textContent='Download '+file.filename;}
            path.textContent=output.mariotyport_path?.[0]||'';visible=true;box.style.display='block';this.setSize([Math.max(400,this.size[0]),this.computeSize()[1]]);
        };
        const removed=this.onRemoved;this.onRemoved=function(){video.pause();video.removeAttribute('src');video.load();box.remove();return removed?.apply(this,arguments);};
        this.setSize([430,this.computeSize()[1]]);return result;
    };
}});
