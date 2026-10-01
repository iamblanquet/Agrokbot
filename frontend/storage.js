'use strict';

// Persistencia local de la PWA. Mantiene la cola y los snapshots aunque el
// servidor no esté disponible o la aplicación se cierre.
const campoStorageDatabase = { current: null };

function campoStorageOpen(){
  return new Promise((resolve,reject)=>{
    const request=indexedDB.open('campo-offline',1);
    request.onupgradeneeded=()=>{request.result.createObjectStore('meta');request.result.createObjectStore('queue',{keyPath:'id'});};
    request.onsuccess=()=>{campoStorageDatabase.current=request.result;resolve(request.result);};
    request.onerror=()=>reject(request.error);
  });
}

function campoStorageGet(store,key){
  return new Promise((resolve,reject)=>{const request=campoStorageDatabase.current.transaction(store).objectStore(store).get(key);request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});
}

function campoStorageAll(){
  return new Promise((resolve,reject)=>{const request=campoStorageDatabase.current.transaction('queue').objectStore('queue').getAll();request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);});
}

function campoStorageWrite(store,value,key){
  return new Promise((resolve,reject)=>{const transaction=campoStorageDatabase.current.transaction(store,'readwrite');const target=transaction.objectStore(store);key===undefined?target.put(value):target.put(value,key);transaction.oncomplete=resolve;transaction.onerror=()=>reject(transaction.error);transaction.onabort=()=>reject(transaction.error);});
}

function campoStorageDelete(id){
  return new Promise((resolve,reject)=>{const transaction=campoStorageDatabase.current.transaction('queue','readwrite');transaction.objectStore('queue').delete(id);transaction.oncomplete=resolve;transaction.onerror=()=>reject(transaction.error);});
}

function campoStorageClear(){
  return new Promise((resolve,reject)=>{const transaction=campoStorageDatabase.current.transaction(['queue','meta'],'readwrite');transaction.objectStore('queue').clear();transaction.objectStore('meta').clear();transaction.oncomplete=resolve;transaction.onerror=()=>reject(transaction.error);});
}

function campoStorageRemoveDemoCatalog(){
  return new Promise((resolve,reject)=>{
    const transaction=campoStorageDatabase.current.transaction('meta','readwrite');
    const request=transaction.objectStore('meta').openCursor();
    request.onsuccess=()=>{const cursor=request.result;if(!cursor)return;if(String(cursor.key).startsWith('snapshot:')&&cursor.value?.catalog){const value=cursor.value;for(const kind of ['projects','tasks'])value.catalog[kind]=(value.catalog[kind]||[]).filter(item=>!String(item.id).startsWith('demo-'));cursor.update(value);}cursor.continue();};
    transaction.oncomplete=resolve;transaction.onerror=()=>reject(transaction.error);transaction.onabort=()=>reject(transaction.error);
  });
}

window.campoStorage={
  open:campoStorageOpen,
  get:campoStorageGet,
  all:campoStorageAll,
  write:campoStorageWrite,
  delete:campoStorageDelete,
  clear:campoStorageClear,
  removeDemoCatalog:campoStorageRemoveDemoCatalog,
  reloadLocal:async user=>(await campoStorageAll()).filter(row=>row.user===user).sort((a,b)=>b.created.localeCompare(a.created)),
};
