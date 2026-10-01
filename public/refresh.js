(async()=>{
  try{
    if('serviceWorker' in navigator){
      const registration=await navigator.serviceWorker.register('/sw.js',{updateViaCache:'none'});
      await registration.update();
      const worker=registration.installing||registration.waiting;
      if(worker&&worker.state!=='activated')await new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>reject(new Error('La actualización está tardando. Vuelve a abrir este enlace con conexión.')),30000);
        worker.addEventListener('statechange',()=>{if(worker.state==='activated'){clearTimeout(timer);resolve();}else if(worker.state==='redundant'){clearTimeout(timer);reject(new Error('No se pudo actualizar. Vuelve a intentar con conexión.'));}});
        if(worker.state==='activated'){clearTimeout(timer);resolve();}
      });
    }
    location.replace('/');
  }catch(error){document.querySelector('#status').textContent=error.message;}
})();
