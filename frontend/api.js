'use strict';

// Cliente HTTP del frontend. La aplicación conserva aquí la política visual
// de conectividad; este módulo únicamente transporta JSON y normaliza errores.
window.campoApi = async function campoApi(path, body){
  let response;
  try{
    response=await fetch(path,{
      method:body===undefined?'GET':'POST',
      credentials:'same-origin',
      headers:body===undefined?{}:{'Content-Type':'application/json'},
      body:body===undefined?undefined:JSON.stringify(body),
      signal:AbortSignal.timeout(45000)
    });
  }catch(error){
    throw new Error('No se pudo conectar al servidor. Tus reportes se conservan.');
  }

  const data=await response.json();
  if(!response.ok){
    const error=new Error(data.error || 'No se pudo completar la operación.');
    Object.assign(error,{status:response.status,code:data.code,currentProgressBps:data.currentProgressBps});
    throw error;
  }
  return data;
};
