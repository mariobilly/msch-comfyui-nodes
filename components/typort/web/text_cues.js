window.MarioTextCues = {
    generate(project, {mode='Beats', source='Mix', every=4, minimum=.4, fps=30}={}) {
        const a=project.audio;
        if(!a?.analysis)throw Error('Analyze the soundtrack first.');
        if(!Number.isInteger(every)||every<1||every>16||!Number.isFinite(minimum)||minimum<.1||minimum>10||!Number.isFinite(fps)||fps<1||fps>60)
            throw Error('Invalid text cue settings.');
        if(!['Beats','Hits'].includes(mode))throw Error('Unknown cue trigger.');
        if(mode==='Hits'&&!a.analysis.channels[source])throw Error('Analyze the selected source first.');
        const events=mode==='Beats'?MarioType.audioBeats(a):a.analysis.channels[source].hits;
        const end=Math.floor(Math.min(project.duration,a.start+a.trim_end-a.trim_start)*fps)/fps;
        const mapped=[...new Set(events.filter(t=>t>=a.trim_start&&t<a.trim_end)
            .map(t=>Math.round((t-a.trim_start+a.start)*fps)/fps).filter(t=>t>=0&&t<end))];
        const starts=[];
        for(let i=0;i<mapped.length;i+=every){
            const t=mapped[i];
            if(!starts.length||t-starts.at(-1)>=minimum-1e-8)starts.push(t);
        }
        const cues=starts.map((start,i)=>({start,end:starts[i+1]??end})).filter(c=>c.end-c.start>=minimum-1e-8);
        if(cues.length>500)throw Error('More than 500 cues. Increase the event interval or minimum duration.');
        return cues;
    }
};
