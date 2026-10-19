'use strict';

// Sincronización de catálogo, fotos y reportes pendientes.
window.campoSync={
  async refresh({state,api}){
    const user=state.user;
    const [catalog,config,reports]=await Promise.all([api('/api/catalog'),api('/api/config'),api('/api/reports')]);
    if(state.user!==user)throw new Error('La cuenta cambió durante la descarga.');
    const savedCatalog={...catalog,offlineSavedAt:new Date().toISOString()};
    const snapshot={catalog:savedCatalog,config,reports:reports.reports,topics:reports.topics,clarifications:reports.clarifications||[]};
    await window.campoStorage.write('meta',snapshot,`snapshot:${user}`);
    if(state.user!==user)return;
    Object.assign(state,snapshot);
    await window.campoStorage.purgeDeliveredPhotos(user,state.reports);
  },
  async sync({state,api,online,banner,updateChrome,reloadLocal,render}){
    if(state.syncing||!state.user)return;
    if(!online()){banner(state.simulation?'Prueba sin señal activa. Los reportes se guardarán en este dispositivo.':'Sin conexión. Puedes trabajar con los proyectos descargados.');updateChrome();return;}
    state.syncing=true;updateChrome();
    try{
      const identity=await api('/api/me');if(identity.user!==state.user)throw new Error('La sesión pertenece a otro usuario. Vuelve a iniciar sesión con tu cuenta.');
      state.canManageIncidents=Boolean(identity.canManageIncidents);state.isAdmin=Boolean(identity.isAdmin);
      // Download field data first; a slow outbox must not delay the offline catalog.
      await this.refresh({state,api});
      await reloadLocal();
      const now=Date.now();
      for(const item of state.local.filter(row=>row.state==='pending').slice().reverse()){
        if(item.nextRetryAt&&Date.parse(item.nextRetryAt)>now)continue;
        const attempt=(item.attempts||0)+1;
        const startedAt=new Date().toISOString();
        await window.campoStorage.write('queue',{...item,attempts:attempt,lastAttemptAt:startedAt,lastError:null});
        try{
          const receipt=await api('/api/reports',item.payload);
          if(['erp_review','erp_rejected','erp_sending'].includes(receipt.state)){
            await window.campoStorage.write('queue',{...item,state:'invalid',error:receipt.error||'El registro ERP requiere revisión.'});
            continue;
          }
          for(const photo of item.photos||[])await api('/api/photos',{id:photo.id,reportId:item.id,data:photo.data.split(',')[1]});
          state.reports=[receipt,...state.reports.filter(report=>report.id!==receipt.id)];
          await window.campoStorage.write('meta',{catalog:state.catalog,config:state.config,reports:state.reports,topics:state.topics,clarifications:state.clarifications||[]},`snapshot:${state.user}`);
          if(item.photos?.length)await window.campoStorage.write('meta',item.photos,`photos:${state.user}:${item.id}`);
          await window.campoStorage.delete(item.id);
        }catch(error){
          if(error.code==='conflict'){
            await window.campoStorage.write('queue',{...item,state:'conflict',attempts:attempt,lastAttemptAt:startedAt,lastError:error.message,error:error.message,currentProgressBps:error.currentProgressBps});
          }else if([400,404,409].includes(error.status)){
            await window.campoStorage.write('queue',{...item,state:'invalid',attempts:attempt,lastAttemptAt:startedAt,lastError:error.message,error:error.message});
          }else{
            const delay=Math.min(15*60*1000,30000*Math.pow(2,Math.min(attempt-1,4)));
            await window.campoStorage.write('queue',{...item,state:'pending',attempts:attempt,lastAttemptAt:startedAt,lastError:error.message,nextRetryAt:new Date(Date.now()+delay).toISOString(),error:error.message});
          }
        }
      }
      await reloadLocal();await this.refresh({state,api});
      const conflicts=state.local.filter(row=>row.state!=='pending').length;
      const pending=state.local.filter(row=>row.state==='pending').length;
      banner(conflicts?`${conflicts} reporte(s) requieren revisión. El original permanece intacto; consulta el registro en Proyectos.`:pending?`${pending} reporte(s) siguen pendientes; se reintentará automáticamente.`:'');
    }catch(error){banner(error.message,error.status===401);}
    finally{state.syncing=false;await reloadLocal();render();}
  },
};
