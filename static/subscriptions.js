'use strict';
const list=document.getElementById('invoices');
const message=document.getElementById('message');
async function request(url,data){
 const response=await fetch(url,{method:data===undefined?'GET':'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:data===undefined?undefined:JSON.stringify(data)});
 const result=await response.json().catch(()=>({error:'Invalid server response'}));
 if(!response.ok)throw new Error(result.error||`Request failed (${response.status})`);
 return result;
}
function node(tag,text,cls){const element=document.createElement(tag);element.textContent=String(text);if(cls)element.className=cls;return element;}
async function refresh(){
 message.textContent='Loading invoices…';list.replaceChildren();
 try{
  const invoices=await request('/api/commerce/invoices');
  message.textContent=invoices.length?'':'No invoices yet. Choose a plan above to request one.';
  for(const invoice of invoices){
   const row=node('article','','invoice');
   const info=node('div','');
   info.append(node('strong',`${invoice.plan} · ${invoice.amount} ${invoice.currency}`));
   info.append(node('p',`Invoice #${invoice.id} · Created ${invoice.created||'unknown'}`));
   if(invoice.expires_at)info.append(node('p',`Expires ${invoice.expires_at} UTC`));
   const actions=node('div','');actions.append(node('span',invoice.status,'status '+invoice.status));
   if(invoice.status==='unpaid'){
    const cancel=node('button','Cancel invoice','secondary');
    cancel.addEventListener('click',async()=>{
     if(!confirm('Cancel this unpaid invoice?'))return;
     cancel.disabled=true;
     try{await request('/api/commerce/subscription/cancel-invoice',{invoice_id:invoice.id});await refresh();message.textContent='Invoice cancelled.';}
     catch(error){message.textContent=error.message;cancel.disabled=false;}
    });
    actions.append(document.createTextNode(' '),cancel);
   }
   row.append(info,actions);list.append(row);
  }
 }catch(error){message.textContent=error.message==='Sign in required'?'Please sign in from the dashboard to manage invoices.':error.message;}
}
for(const button of document.querySelectorAll('[data-plan]'))button.addEventListener('click',async()=>{
 button.disabled=true;
 try{const result=await request('/api/commerce/subscription/invoice',{plan:button.dataset.plan});await refresh();message.textContent=result.reused?'Existing unpaid invoice shown.':'New unpaid invoice created. No payment was taken.';}
 catch(error){message.textContent=error.message;}finally{button.disabled=false;}
});
document.getElementById('refresh').addEventListener('click',refresh);
refresh();
