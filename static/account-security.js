'use strict';
const notice=document.getElementById('security-message');
async function secureAction(path,body){
 const response=await fetch(path,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
 const result=await response.json().catch(()=>({error:'Invalid server response'}));
 if(!response.ok)throw new Error(result.error||`Request failed (${response.status})`);
 return result;
}
function wire(formId,path,payload){
 const form=document.getElementById(formId);
 form.addEventListener('submit',async(event)=>{
  event.preventDefault();
  if(!form.reportValidity())return;
  const button=form.querySelector('button[type="submit"]');
  button.disabled=true;notice.textContent='Processing…';
  try{
   const result=await secureAction(path,payload());
   form.reset();notice.textContent=result.message||'Success. Please sign in again.';
   window.location.assign('/account.html');
  }catch(error){notice.textContent=error.message;}
  finally{button.disabled=false;}
 });
}
wire('password-form','/api/security/change-password',()=>({current_password:document.getElementById('current-password').value,new_password:document.getElementById('new-password').value}));
wire('logout-form','/api/security/logout-all',()=>({password:document.getElementById('verify-password').value}));
