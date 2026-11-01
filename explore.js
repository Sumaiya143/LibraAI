(()=>{'use strict';
const $=id=>document.getElementById(id);
const books=$('books'),count=$('count'),notice=$('notice'),genre=$('genre'),sort=$('sort'),search=$('search'),empty=$('empty');
const prev=$('prev'),next=$('next'),pageInfo=$('pageInfo');
const palette=[['#304c75','#13243d'],['#ac7355','#50342e'],['#547b70','#1c4c4a'],['#8a719d','#4b3769'],['#bb8d4d','#76502d']];
let latest=0,page=1,pages=0,abortController=null;
let favorites=new Set();
try{const saved=JSON.parse(localStorage.getItem('libraai-favorites')||'[]');if(Array.isArray(saved))favorites=new Set(saved.filter(Number.isInteger))}catch{}
function element(tag,cls,text){const el=document.createElement(tag);if(cls)el.className=cls;if(text!==undefined)el.textContent=String(text);return el}
function bookCard(b,i){
 const card=element('article','book'),cover=element('div','cover');
 const colors=palette[Math.abs(Number(b.id)||i)%palette.length];cover.style.setProperty('--c1',colors[0]);cover.style.setProperty('--c2',colors[1]);
 cover.append(element('strong','',b.title||'Untitled'),element('small','',b.author||'Unknown author'));card.append(cover);
 const meta=element('div','book-meta');meta.append(element('span','pill',b.genre||'Books'),element('h3','',b.title||'Untitled'),element('div','author',b.author||'Unknown author'));
 const stats=element('div','stats');stats.append(element('span','',`★ ${Number(b.rating||0).toFixed(1)} rating`),element('span','',b.year||''));meta.append(stats);
 const actions=element('div','actions'),link=element('a','','View details ↗');link.href='/books/'+encodeURIComponent(b.id);
 const fav=element('button','','♡');fav.type='button';fav.setAttribute('aria-label','Save '+(b.title||'book')+' to favorites');
 const update=()=>{const on=favorites.has(Number(b.id));fav.setAttribute('aria-pressed',String(on));fav.textContent=on?'♥':'♡';fav.title=on?'Remove favorite':'Save favorite'};
 update();fav.addEventListener('click',()=>{const id=Number(b.id);if(favorites.has(id))favorites.delete(id);else favorites.add(id);try{localStorage.setItem('libraai-favorites',JSON.stringify([...favorites]))}catch{}update()});
 actions.append(link,fav);meta.append(actions);card.append(meta);return card;
}
async function load(){
 const token=++latest;if(abortController)abortController.abort();abortController=new AbortController();
 notice.textContent='';count.textContent='Loading books…';books.replaceChildren();empty.hidden=true;prev.disabled=true;next.disabled=true;
 const qs=new URLSearchParams({sort:sort.value,page:String(page),page_size:'12'});
 if(genre.value)qs.set('genre',genre.value);if(search.value.trim())qs.set('q',search.value.trim());
 try{
  const res=await fetch('/api/books/page?'+qs.toString(),{headers:{Accept:'application/json'},credentials:'same-origin',signal:abortController.signal});
  if(!res.ok)throw Error('Catalog request failed');const data=await res.json();if(!Array.isArray(data.items))throw Error('Unexpected catalog response');if(token!==latest)return;
  pages=data.pages;const fragment=document.createDocumentFragment();data.items.forEach((b,i)=>fragment.append(bookCard(b,i)));books.replaceChildren(fragment);
  count.textContent=`${data.total} ${data.total===1?'book':'books'} found`;
  pageInfo.textContent=data.pages?`Page ${data.page} of ${data.pages}`:'No pages';prev.disabled=page<=1;next.disabled=!data.has_more;empty.hidden=data.total!==0;
 }catch(e){if(token!==latest||e.name==='AbortError')return;count.textContent='Catalog temporarily unavailable';pageInfo.textContent='';notice.textContent='We could not load the catalog. Please refresh or try again later.'}
}
async function genres(){try{const r=await fetch('/api/books',{credentials:'same-origin'});if(!r.ok)return;const all=await r.json();if(!Array.isArray(all))return;[...new Set(all.map(b=>b.genre).filter(v=>typeof v==='string'&&v))].sort().forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;genre.append(o)})}catch{}}
function reset(){page=1;load()}
$('searchForm').addEventListener('submit',e=>{e.preventDefault();reset()});genre.addEventListener('change',reset);sort.addEventListener('change',reset);
prev.addEventListener('click',()=>{if(page>1){page--;load();$('results').scrollIntoView({behavior:'smooth'})}});
next.addEventListener('click',()=>{if(page<pages){page++;load();$('results').scrollIntoView({behavior:'smooth'})}});
$('clear').addEventListener('click',()=>{search.value='';genre.value='';sort.value='trending';reset()});genres();load();
})();
