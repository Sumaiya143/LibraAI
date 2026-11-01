import Link from "next/link";
import { ArrowRight, BookOpen, Brain, Headphones, UsersRound, ShieldCheck, Sparkles, LibraryBig } from "lucide-react";
const items=[
 {icon:BookOpen,title:"A library for every curiosity",text:"Explore eBooks, physical books, notes, and reading lists in one convenient place."},
 {icon:Brain,title:"AI-powered learning",text:"Get help with summaries, study planning, explanations, and discovering related titles. AI features may require an authorized account."},
 {icon:Headphones,title:"Read your way",text:"Choose a reading format that suits your routine, from digital books to audio."},
 {icon:UsersRound,title:"Learn together",text:"Find reading communities, exchange recommendations, and discuss what you are reading."},
 {icon:ShieldCheck,title:"Security first",text:"Protected actions require sign-in and server-side permission checks. Unauthorized requests should be rejected rather than bypassed."},
 {icon:LibraryBig,title:"Your personal collection",text:"Keep track of your saved books and continue building your own learning journey."}
];
export default function FeaturesPage(){return <><main className="feature-info-page"><span className="home-pill"><Sparkles size={12}/> THE LIBRAAI EXPERIENCE</span><h1>More ways to <span>read, learn & grow.</span></h1><p className="feature-info-intro">A connected reading and learning experience designed to help you discover your next great idea.</p><div className="feature-info-grid">{items.map(({icon:Icon,title,text})=><article key={title}><span><Icon size={23}/></span><h2>{title}</h2><p>{text}</p></article>)}</div><section className="feature-info-cta"><div><h2>Your next chapter starts here.</h2><p>Create your free account or explore the catalogue.</p></div><Link href="/signup" className="btn btn-primary">Get Started <ArrowRight size={14}/></Link><Link href="/library" className="btn btn-ghost">Explore Library</Link></section></main></>}
