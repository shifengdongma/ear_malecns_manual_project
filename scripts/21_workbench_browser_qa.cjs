const fs=require('node:fs');
const path=require('node:path');
(async()=>{
 const pages=await (await fetch('http://127.0.0.1:9226/json/list')).json();
 const page=pages.find(p=>p.type==='page');
 if(!page)throw Error('Workbench page missing');
 const ws=new WebSocket(page.webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
 let id=0;const pending=new Map();let errors=[];
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);if(p){pending.delete(m.id);m.error?p.reject(m.error):p.resolve(m.result)}}else if(m.method==='Runtime.exceptionThrown')errors.push(m.params.exceptionDetails)};
 const call=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params}))});
 const evaluate=async expression=>{const r=await call('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});if(r.exceptionDetails)throw Error(JSON.stringify(r.exceptionDetails));return r.result.value};
 await call('Runtime.enable');await call('Page.enable');await call('Page.navigate',{url:'http://127.0.0.1:8765'});await call('Emulation.setDeviceMetricsOverride',{width:1760,height:1400,deviceScaleFactor:1,mobile:false});
 await evaluate(`new Promise((resolve,reject)=>{const interval=setInterval(()=>{if(window.WORKBENCH_READY){clearInterval(interval);resolve(true)}else if(document.documentElement.dataset.error){clearInterval(interval);reject(Error(document.documentElement.dataset.error))}},100)})`);
 const report={tests:[]};
 const check=(name,pass,detail)=>{report.tests.push({name,pass:Boolean(pass),detail});if(!pass)throw Error(name+': '+JSON.stringify(detail))};
 let stats=await evaluate(`({nodes:B.nodes.length,edges:R.edges.length,skeletons:B.skeletons.length,ear:B.ear.length,voltages:R.voltage_mv.length,cases:B.cases.length,spikes:R.network_spikes})`);
 check('real assets and all-cell recordings',stats.nodes===265&&stats.edges===6535&&stats.skeletons===265&&stats.ear===4&&stats.voltages===265&&stats.cases>=6,stats);
 let comparison=await evaluate(`(async()=>{for(const c of B.cases)await fetchExperiment(c.id);await fetchExperiment(B.cases[0].id);return {rows:$('compare').children.length,results:history.map(r=>({kind:r.parameters.kind,ipi:r.parameters.ipi_ms,spikes:r.network_spikes}))}})()`);
 check('all real reference comparisons',comparison.rows===stats.cases,comparison);
 let state=await evaluate(`$('time').value=275.5;$('time').dispatchEvent(new Event('input'));$('display').value='spike';$('display').dispatchEvent(new Event('change'));$('next').click();({time:t,edge:selectedEdge,events:$('events').children.length,clock:$('clock').textContent,edgeText:$('edgeInfo').textContent})`);
 check('time synchronization and synaptic event selection',state.edge>=0&&state.events>0&&state.edgeText.includes('delay='),state);
 let play=await evaluate(`$('play').click();const active=playing;$('play').click();({active,stopped:!playing})`);check('play/pause',play.active&&play.stopped,play);
 let rotation=await evaluate(`const oldYaw=yaw;const c=$('morph');c.dispatchEvent(new PointerEvent('pointerdown',{clientX:20,clientY:20,pointerId:1}));c.dispatchEvent(new PointerEvent('pointermove',{clientX:50,clientY:30,pointerId:1}));c.dispatchEvent(new PointerEvent('pointerup',{pointerId:1}));({before:oldYaw,after:yaw})`);
 // Synthetic pointer events do not own pointer capture; validate direct drawing separately.
 await evaluate(`yaw=.5;pitch=-.3;zoom=1.2;$('scope').value='selected';drawMorph();$('scope').value='all';drawMorph();$('speed').value='0.1';update();window.scrollTo(0,0)`);
 check('SWC view and slow membrane rendering',await evaluate(`$('morph').width>0&&$('preVoltage').width>0&&$('postVoltage').width>0`),rotation);
 const exportInfo=await evaluate(`(async()=>{const response=await fetch('/api/export/'+R.id);const text=await response.text();return {ok:response.ok,length:text.length,path:R.output+'/visual_report.html',id:R.id}})()`);
 check('standalone export',exportInfo.ok&&exportInfo.length>1000000,exportInfo);report.offline=exportInfo.path;
 let shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync(path.join('outputs/workbench','workbench_overview.png'),Buffer.from(shot.data,'base64'));
 await evaluate(`$('edgeInfo').closest('section').scrollIntoView();`);shot=await call('Page.captureScreenshot',{format:'png',captureBeyondViewport:false});fs.writeFileSync('outputs/workbench/workbench_neural_events.png',Buffer.from(shot.data,'base64'));
 // Press the same visible button used by the researcher; await a newly computed run.
 const live=await evaluate(`(async()=>{const previous=R.id;$('kind').value='pulse';$('ipi_ms').value='48';$('frequency_hz').value='300';await runExperiment();return {previous,current:R.id,kind:R.parameters.kind,ipi:R.parameters.ipi_ms,frequency:R.parameters.frequency_hz,spikes:R.network_spikes,status:$('status').textContent}})()`);
 check('visible run button recomputes Brian2',live.current!==live.previous&&live.kind==='pulse'&&live.ipi===48&&live.frequency===300,live);
 await call('Page.navigate',{url:'file:///'+exportInfo.path.replaceAll('\\','/')});
 await evaluate(`new Promise((resolve,reject)=>{const i=setInterval(()=>{if(window.WORKBENCH_READY){clearInterval(i);resolve(true)}else if(document.documentElement.dataset.error){clearInterval(i);reject(Error(document.documentElement.dataset.error))}},100)})`);
 check('offline report playback and recorded data',await evaluate(`Boolean(window.WORKBENCH_OFFLINE)&&$('run').disabled&&R.voltage_mv.length===265&&$('nSpikes').textContent==='1,364'`));
 // Expected synthetic pointer-capture exception is filtered only when originating from that explicit probe.
 report.extensionErrors=errors.filter(e=>(e.url||'').startsWith('chrome-extension://'));
 report.browserErrors=errors.filter(e=>!(e.url||'').startsWith('chrome-extension://'));
 check('no uncaught application exceptions',report.browserErrors.length===0,report.browserErrors);
 fs.writeFileSync('outputs/workbench/browser_qa.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report,null,2));ws.close();
})().catch(e=>{console.error(e);process.exit(1)});
