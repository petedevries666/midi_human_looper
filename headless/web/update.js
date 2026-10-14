/* Executable updates use independent administrator authorization, never editor token. */
(() => {
  const el=id=>document.getElementById(id);let status=null,timer=null;
  async function call(data){
    const response=await fetch('/api/v1/update',{method:data?'POST':'GET',headers:{'Content-Type':'application/json','X-Engine-Token':sessionStorage.getItem('mbh-token')||el('token')?.value||''},body:data?JSON.stringify(data):undefined});
    const result=await response.json();if(!response.ok)throw Error(result.error||'Update unavailable');return result;
  }
  async function refresh(){
    try{
      status=await call();el('update-version').textContent=`INSTALLED V${status.version || "?"} · ${status.installed}`;
      el('update-changes').textContent=status.available?`${status.available.name} · ${status.available.revision}\n${status.available.changes}`:'';
      el('update-progress').textContent=`${status.progress.phase.toUpperCase()} · ${status.progress.message}\n${status.restart}`;
      el('update-install').disabled=status.busy||!status.available||status.available.revision===status.installed||status.recoveryRequired;
      el('update-rollback').disabled=status.busy||!status.rollbackAvailable;
      el('update-check').disabled=status.busy;el('update-recover').hidden=!status.recoveryRequired;
    }catch(error){el('update-progress').textContent=error.message;}
    if(el('runtime-update').open)timer=setTimeout(refresh,1500);
  }
  async function action(action){
    if(action!=='check'&&!confirm(`${action.toUpperCase()} MBMF? Stop every phrase, MOVEMENT and recording first. Save the Zynthian snapshot. UI-owned processors will restart; audio may be interrupted. JACK and LUMAZ services stay running.`))return;
    const password=prompt('UPDATE administrator password (separate from editor token):');if(!password)return;
    try{await call({action,password,confirm:action!=='check',revision:status?.available?.revision});clearTimeout(timer);await refresh();}
    catch(error){el('update-progress').textContent=error.message;}
  }
  for(const name of ['check','install','rollback','recover'])el('update-'+name).onclick=()=>action(name);
  el('runtime-update').ontoggle=()=>{clearTimeout(timer);if(el('runtime-update').open)refresh();};
})();
