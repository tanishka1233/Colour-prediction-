import{ct as e,ft as t,vn as n}from"./runtime-core.esm-bundler-sjKfHKmo.js";function r(e){let t=null;return()=>(t===null&&(t=e().catch(e=>{throw t=null,e})),t)}function i(e){return new Promise(t=>setTimeout(t,e))}function a(){let e={set(e,t,n=-1){n!==-1&&(n=Date.now()+n*1e3),window.localStorage.setItem(e,JSON.stringify({value:t,expires:n}))},get(t){let n=window.localStorage.getItem(t);if(n)try{let r=JSON.parse(n);return r.expires!==-1&&r.expires<Date.now()?(e.remove(t),null):r.value}catch{return null}return null},remove(e){window.localStorage.removeItem(e)}};return{localStore:e,cookie:{setCookie:function(e,t,n,r={sameSite:`None`,secure:!0,domain:location.hostname}){let i=``;if(n){let e=new Date;e.setTime(e.getTime()+n*24*60*60*1e3),i=`; expires=`+e.toUTCString()}let a=r.path?`; path=${r.path}`:`; path=/`,o=r.domain?`; domain=${r.domain}`:``,s=r.secure?`; Secure`:``,c=r.sameSite?`; SameSite=${r.sameSite}`:``;try{document.cookie=`${e}=${encodeURIComponent(t)}${i}${a}${o}${s}${c}`}catch(e){console.error(`Failed to set cookie:`,e)}},getCookie:function(e){let t=e+`=`,n=document.cookie.split(`;`);for(let e=0;e<n.length;e++){let r=n[e].trim();if(r.indexOf(t)===0)return decodeURIComponent(r.substring(t.length,r.length))}return null},remove:function(e){this.setCookie(e,``,-1)}}}}function o(r,i,a={immediate:!1}){let o=n(!1),s=null,c=()=>{let e=new Blob([`
      let intervalId = null;
      self.onmessage = (e) => {
        const { command, interval } = e.data;

        switch (command) {
          case 'start':
            if (!intervalId) {
              intervalId = setInterval(() => postMessage('tick'), interval);
            }
            break;
          case 'pause':
            clearInterval(intervalId);
            intervalId = null;
            break;
        }
      };
    `],{type:`application/javascript`});return new Worker(URL.createObjectURL(e))},l=()=>{s&&(o.value=!0,s.postMessage({command:`start`,interval:i}))},u=()=>{s&&(o.value=!1,s.postMessage({command:`pause`}))};return e(()=>{s=c(),s.onmessage=e=>{e.data===`tick`&&r()},a.immediate&&l()}),t(()=>{u(),s==null||s.terminate(),s=null}),{start:l,pause:u,resume:()=>{o.value||l()},isActive:o}}var s=function(e){return e.TOKEN=`ar_g_token`,e.LANG=`ar_g_lang`,e.API_URL=`ar_g_api_url`,e.URL=`ar_url`,e.SKIN=`ar_skin`,e.SOUND_BG=`ar_sound_bg`,e.SOUND_EF=`ar_sound_ef`,e.REDIRECT_URL=`ar_g_rurl`,e.BECK=`ar_g_beck`,e}({});export{r as a,i,o as n,a as r,s as t};