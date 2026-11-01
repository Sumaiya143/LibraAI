"use client";
import {useEffect,useMemo,useState} from "react";
import Link from "next/link";
import {ArrowLeft,BookOpen,Search,SlidersHorizontal,Bookmark,RefreshCw,Sparkles} from "lucide-react";
import styles from "./manga.module.css";
type Manga={id:number;title:string;author:string;genre:string;description:string;cover:string;rating:number;chapters:number;status:string};
export default function MangaPage(){
 const [items,setItems]=useState<Manga[]>([]),[query,setQuery]=useState(""),[loading,setLoading]=useState(true),[error,setError]=useState(""),[saved,setSaved]=useState<number[]>([]),[visibleCount,setVisibleCount]=useState(15);
 const load=async()=>{setLoading(true);setError("");try{
  const r=await fetch("/backend/api/books?sort=trending&limit=100",{cache:"no-store"});
  if(!r.ok)throw new Error("The live manga catalog is unavailable.");
  const d=await r.json();const rows=Array.isArray(d)?d:(d.items||d.books||[]);
  const mangaRows=rows.filter((b:any)=>/manga|comic|manhwa|webtoon/i.test(`${b.product_type||""} ${b.genre||""} ${b.format||""}`));
  setItems(mangaRows.map((b:any)=>({id:Number(b.id),title:String(b.title||"Untitled"),author:String(b.author||"Creator not listed"),genre:String(b.genre||"Manga"),description:String(b.description||""),cover:String(b.cover_image||b.cover_url||""),rating:Number(b.rating||0),chapters:Number(b.chapters||b.chapter_count||0),status:String(b.publication_status||"Available")})));
 }catch(e){setError(e instanceof Error?e.message:"Could not load manga.");}finally{setLoading(false)}};

 useEffect(()=>{void load()},[]);
 const filtered=useMemo(()=>items.filter(x=>`${x.title} ${x.author} ${x.genre}`.toLowerCase().includes(query.toLowerCase())),[items,query]);
 return <main className={styles.page}><Link href="/library" className={styles.back}><ArrowLeft size={16}/> Back to Resources</Link><section className={styles.hero}><span><Sparkles size={14}/> LIBRAAI MANGA LIBRARY</span><h1>Discover your next <em>favorite series.</em></h1><p>Explore manga, manhwa and comics from the live LibraAI catalog.</p></section><section className={styles.toolbar}><div><h2>Browse Series <small>{filtered.length}</small></h2><p>Latest additions from the catalog</p></div><label><Search size={17}/><input value={query} onChange={e=>{setQuery(e.target.value);setVisibleCount(15)}} placeholder="Search series..."/></label></section>{loading?<p className={styles.state}>Loading the latest series…</p>:error?<div className={styles.state}>{error} <button onClick={()=>void load()}><RefreshCw size={14}/> Retry</button></div>:filtered.length===0?<div className={styles.state}><BookOpen size={28}/><h3>No manga published yet</h3><p>New manga uploaded by the LibraAI catalog team will appear here automatically.</p><Link href="/library">Browse all resources</Link></div>:<div className={styles.grid}>{filtered.slice(0,visibleCount).map(m=><article className={styles.card} key={m.id}><div className={styles.cover}>{m.cover?<img src={m.cover} alt=""/>:<BookOpen size={38}/>}<small>{m.rating?`★ ${m.rating.toFixed(1)}`:"NEW"}</small></div><div className={styles.body}><h3>{m.title}</h3><p>{m.author}</p><div className={styles.tags}><span>{m.genre}</span><span>{m.chapters?`${m.chapters} Chapters`:m.status}</span></div><button onClick={()=>setSaved(v=>v.includes(m.id)?v.filter(x=>x!==m.id):[...v,m.id])}><Bookmark size={14} fill={saved.includes(m.id)?"currentColor":"none"}/>{saved.includes(m.id)?"Bookmarked":"Bookmark"}</button></div></article>)}</div>}{filtered.length>visibleCount&&<button className={styles.more} onClick={()=>setVisibleCount(v=>v+15)}>Load more series</button>}<p className={styles.note}>Catalog updates automatically when authorized manga titles are added by an administrator.</p></main>
}
