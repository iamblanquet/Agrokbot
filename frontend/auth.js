'use strict';

window.campoAuth={
  async login({body,state,api,storage,reloadLocal,showApp,sync}){
    const result=await api('/api/login',body);
    const previous=await storage.get('meta','user');
    if(previous&&previous!==result.user){
      if((await storage.all()).length){await api('/api/logout',{});throw new Error(`Hay reportes pendientes de ${previous}. Entra con esa cuenta para sincronizarlos antes de cambiar de usuario.`);}
      await storage.clear();
      state.catalog={projects:[],tasks:[]};state.reports=[];state.topics=[];state.local=[];state.selected=null;state.topic=null;
    }
    state.user=result.user;state.canManageIncidents=false;state.isAdmin=Boolean(result.isAdmin);await storage.write('meta',state.user,'user');await storage.write('meta',state.isAdmin,'isAdmin');
    const saved=await storage.get('meta',`snapshot:${state.user}`);if(saved)Object.assign(state,saved);
    await reloadLocal();showApp();await sync();
    if(window.campoRestorePush)await window.campoRestorePush();
  },
  async logout({state,api,storage,showLogin,toast}){
    if(state.local.length){toast('Sincroniza o corrige tus reportes pendientes antes de cerrar sesión.');return;}
    try{
      if('serviceWorker' in navigator){
        const registration=await navigator.serviceWorker.getRegistration();
        const subscription=registration?.pushManager&&await registration.pushManager.getSubscription();
        if(subscription)await api('/api/notifications/unsubscribe',{endpoint:subscription.endpoint});
      }
      await api('/api/logout',{});await storage.clear();state.user=null;state.canManageIncidents=false;state.view='projects';try{if(typeof sessionStorage!=='undefined')sessionStorage.removeItem('campo-active-view');}catch(_){}state.catalog={projects:[],tasks:[]};state.reports=[];state.topics=[];state.simulation=false;showLogin();
    }catch(error){toast(error.message);}
  },
  async setupTelegram({showLogin,login,$}){
    const initData=window.Telegram?.WebApp?.initData || new URLSearchParams(location.hash.slice(1)).get('tgWebAppData') || new URLSearchParams(location.search).get('tgWebAppData');
    if(!initData)return false;
    showLogin();
    $('#login-form .muted').textContent='Verificando tu cuenta vinculada de Telegram…';
    $('#telegram-login').hidden=true;
    try{await login({initData});}
    catch(error){$('#login-form .muted').textContent='Puedes entrar con tu PIN.';$('#login-error').textContent=error.message;}
    return true;
  },
  async boot({state,storage,showLogin,showApp,reloadLocal,sync,setupTelegram,banner,$}){
    try{
      await storage.open();await storage.removeDemoCatalog();state.user=await storage.get('meta','user');state.isAdmin=Boolean(await storage.get('meta','isAdmin'));state.canManageIncidents=Boolean(await storage.get('meta','canManageIncidents'));state.simulation=Boolean(await storage.get('meta','simulation'));
      if('serviceWorker' in navigator)navigator.serviceWorker.register('/sw.js').catch(()=>banner('No se pudo preparar el modo offline. Abre la app por HTTPS o localhost.'));
      if(await setupTelegram())return;
      if(state.user){const saved=await storage.get('meta',`snapshot:${state.user}`);if(saved)Object.assign(state,saved);await reloadLocal();showApp();await sync();}else showLogin();
    }catch(error){showLogin();$('#login-error').textContent='No se pudo abrir el almacenamiento local. Habilita los datos del sitio para usar Campo.';}
  },
};
