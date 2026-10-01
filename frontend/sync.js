'use strict';

// Sincronización de catálogo, fotos y reportes pendientes.
window.campoSync={
  async refresh({state,api}){
    const [catalog,config,reports]=await Promise.all([api('/api/catalog'),api('/api/config'),api('/api/reports')]);
    state.catalog=catalog;state.config=config;state.reports=reports.reports;state.topics=reports.topics;state.clarifications=reports.clarifications||[];
    await window.campoStorage.write('meta',{catalog,config,reports:state.reports,topics:state.topics,clarifications:state.clarifications||[]},`snapshot:${state.user}`);
  },
  async sync({state,api,online,banner,updateChrome,reloadLocal,render}){
    if(state.syncing||!state.user)return;
    if(!online()){banner(state.simulation?'Prueba sin señal activa. Los reportes se guardarán en este dispositivo.':'Sin conexión. Puedes trabajar con los proyectos descargados.');updateChrome();return;}
    state.syncing=true;updateChrome();
    try{
      const identity=await api('/api/me');if(identity.user!==state.user)throw new Error('La sesión pertenece a otro usuario. Vuelve a iniciar sesión con tu cuenta.');
      await reloadLocal();
      for(const item of state.local.filter(row=>row.state==='pending').slice().reverse()){
        try{
          for(const photo of item.photos||[])await api('/api/photos',{id:photo.id,reportId:item.id,data:photo.data.split(',')[1]});
          const receipt=await api('/api/reports',item.payload);
          state.reports=[receipt,...state.reports.filter(report=>report.id!==receipt.id)];
          await window.campoStorage.write('meta',{catalog:state.catalog,config:state.config,reports:state.reports,topics:state.topics,clarifications:state.clarifications||[]},`snapshot:${state.user}`);
          if(item.photos?.length)await window.campoStorage.write('meta',item.photos,`photos:${state.user}:${item.id}`);
          await window.campoStorage.delete(item.id);
        }catch(error){
          if(error.code==='conflict')await window.campoStorage.write('queue',{...item,state:'conflict',error:error.message,currentProgressBps:error.currentProgressBps});
          else if([400,404,409].includes(error.status))await window.campoStorage.write('queue',{...item,state:'invalid',error:error.message});
          else throw error;
        }
      }
      await reloadLocal();await this.refresh({state,api});
      const conflicts=state.local.filter(row=>row.state!=='pending').length;
      banner(conflicts?`${conflicts} reporte(s) no se pudieron registrar. El original permanece intacto; consulta el registro en Proyectos.`:'');
    }catch(error){banner(error.message,error.status===401);}
    finally{state.syncing=false;await reloadLocal();render();}
  },
};
