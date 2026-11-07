// Exercises the actual browser executor against a fake serial device, not hardware.
const fs=require('fs'), vm=require('vm'), assert=require('node:assert/strict');
const html=fs.readFileSync('firmware/feedback_controller/dashboard/scanner_dashboard.html','utf8');
const code=html.slice(html.indexOf('const agentClient='),html.indexOf("$('agentEnable').onchange="));
function fixture({enabled=true,interlock=true,abort=false,probe=true,staticCapture=false,observation=false}={}) {
  const commands=[], S={connected:true,booting:false,running:false,armed:false,laser:false,cmd:1500,interlock};
  const context={crypto:require('node:crypto').webcrypto,setTimeout,clearTimeout,Date,console,performance,
    S,agentObserver:null,agentCancelled:false,inflight:null,queue:[],pendingGoto:null,
    $:()=>({checked:enabled}),render:()=>{},log:()=>{},inWin:u=>u>=1100&&u<=1900};
  context.rawWrite=async command=>{
    commands.push(command);
    let lines;
    if(command==='stop'){S.armed=false;S.laser=false;lines=['OK stopped, disarmed, servo released'];}
    else if(command==='status')lines=[`OK status armed=${+S.armed} interlock=closed laser=${+S.laser} cmd=${S.cmd}${probe?' probe=1 attached=0':''}${staticCapture?' static=1':''}${observation?' observe=1':''}`];
    else if(command.startsWith('read '))lines=['OK read n=100 mean=310 std=0.3'];
    else if(command.startsWith('move ')){S.cmd=+command.split(' ')[1];lines=['OK move '+S.cmd];}
    else if(command==='arm'){S.armed=true;lines=['OK armed'];}
    else if(command==='laser on'){S.laser=true;lines=['OK laser on'];}
    else if(command.startsWith('sweep '))lines=['OK sweep','S,123,1500,310,1',`E,456,${abort?'ABORTED':'DONE'},0,0,0`];
    else if(command.startsWith('probe '))lines=['OK probe','F,100,200,1500,310,4960,16,4,1,0',`E,456,PROBE_${abort?'ABORTED':'DONE'},1500,0,0`];
    else if(command.startsWith('observe '))lines=['OK static','E,200,STATIC_OBSERVE,1500,0,0','E,300,STATIC_SCREEN_WARN,1500,0,0',`E,456,STATIC_${abort?'ABORTED':'DONE'},1500,0,0`];
    else if(command.startsWith('static '))lines=['OK static',`E,456,STATIC_${abort?'ABORTED':'DONE'},1500,0,0`];
    else throw Error('Unexpected command '+command);
    for(const line of lines)if(context.agentObserver)context.agentObserver(line);
  };
  vm.createContext(context);vm.runInContext(code,context);
  return {commands,S,run:async request=>{
    await context.executeAgent({id:'test',request});
    return vm.runInContext('agentResult',context);
  }};
}
(async()=>{
  for(const request of [{action:'read',n:100},{action:'move',us:1510},
    {action:'pulse',seconds:1,arm:true,contained:true},
    {action:'sweep',start_us:1480,end_us:1520,duration_ms:100,arm:true,contained:true}]){
    const f=fixture(),r=await f.run(request);
    assert.equal(r.error,null);assert.equal(r.stop_confirmed,true);
    assert.deepEqual(f.commands.slice(-2),['stop','status']);assert.equal(f.S.laser,false);
    if(request.action==='sweep')assert(r.lines.some(l=>l.includes(',DONE,')));
  }
  for(const settings of [{enabled:false},{interlock:false}]){
    const f=fixture(settings),r=await f.run({action:'pulse',seconds:1,arm:true,contained:true});
    assert(r.error);assert(!f.commands.includes('laser on'));assert(r.stop_confirmed);
  }
  const f=fixture({abort:true}),r=await f.run({action:'sweep',start_us:1480,end_us:1520,duration_ms:100,arm:true,contained:true});
  assert.match(r.error,/aborted/);assert(r.stop_confirmed);
  for(const settings of [{},{probe:false},{abort:true}]) {
    const p=fixture(settings),r=await p.run({action:'probe',source_us:1500,target_us:1510,hold_ms:1000,contained:true});
    assert(r.stop_confirmed);assert(!p.commands.includes('arm'));assert(!p.commands.includes('laser on'));
    if(settings.probe===false){assert.match(r.error,/lacks bounded probe/);assert(!p.commands.some(c=>c.startsWith('probe ')));}
    else if(settings.abort)assert.match(r.error,/aborted/);
    else {assert.equal(r.error,null);assert(r.received.some(x=>x.line.startsWith('F,')&&Number.isFinite(x.host_rx_monotonic_ms)));}
  }
  const bad=fixture(),badResult=await bad.run({action:'probe',source_us:1500,target_us:1510,hold_ms:3001,contained:true});
  assert.match(badResult.error,/Invalid bounded/);assert(!bad.commands.some(c=>c.startsWith('probe ')));
  for(const settings of [{},{staticCapture:true},{staticCapture:true,abort:true}]) {
    const f=fixture(settings),r=await f.run({action:'static',us:1500,arm:true,contained:true});
    assert(r.stop_confirmed);
    if(!settings.staticCapture){assert.match(r.error,/lacks bounded static/);assert(!f.commands.includes('arm'));}
    else if(settings.abort)assert.match(r.error,/aborted/);
    else {assert.equal(r.error,null);assert(f.commands.includes('static 1500'));}
  }
  const wrong=fixture({staticCapture:true}),wr=await wrong.run({action:'static',us:1510,arm:true,contained:true});
  assert(wr.error);assert(!wrong.commands.includes('arm'));
  for(const settings of [{staticCapture:true},{staticCapture:true,observation:true},{staticCapture:true,observation:true,abort:true}]) {
    const f=fixture(settings),r=await f.run({action:'observe',us:1500,arm:true,contained:true});
    assert(r.stop_confirmed);
    if(!settings.observation){assert.match(r.error,/lacks bounded optical/);assert(!f.commands.includes('arm'));}
    else if(settings.abort)assert.match(r.error,/aborted/);
    else {assert.equal(r.error,null);assert(r.observation_mode);assert(r.feedback_screen_warning);assert(f.commands.includes('observe 1500'));}
  }
  console.log('PASS: browser executor read/move/pulse/sweep, disabled/interlock refusal, abort, final off/status (fake serial)');
})().catch(e=>{console.error(e);process.exitCode=1;});
