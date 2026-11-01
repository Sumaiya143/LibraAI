"""Licensed EPUB/CBZ rendering extension; intentionally does not run embedded scripts."""
import io,zipfile,re,html,os,urllib.parse
from html.parser import HTMLParser
from advanced import UPLOAD,ALLOWED
from advanced_server import db
from release_server import Release

ALLOWED['cbz']='application/vnd.comicbook+zip'
MAX_ENTRIES=2000
MAX_UNCOMPRESSED=60*1024*1024
class TextExtractor(HTMLParser):
 def __init__(self):super().__init__(convert_charrefs=True);self.parts=[];self.skip=0
 def handle_starttag(self,tag,attrs):
  if tag in ('script','style','svg'):self.skip+=1
  if tag in ('p','h1','h2','h3','h4','li','br','blockquote'):self.parts.append('\n')
 def handle_endtag(self,tag):
  if tag in ('script','style','svg'):self.skip=max(0,self.skip-1)
  if tag in ('p','h1','h2','h3','li'):self.parts.append('\n')
 def handle_data(self,data):
  if not self.skip:self.parts.append(data)
 def text(self):return re.sub(r'\n{3,}','\n\n',''.join(self.parts)).strip()

def archive_entries(path,kind):
 with zipfile.ZipFile(path) as z:
  entries=z.infolist()
  if len(entries)>MAX_ENTRIES or sum(i.file_size for i in entries)>MAX_UNCOMPRESSED:raise ValueError('Archive too large')
  ext=('.xhtml','.html','.htm') if kind=='epub' else ('.png','.jpg','.jpeg','.webp')
  names=[i.filename for i in entries if not i.is_dir() and i.filename.lower().endswith(ext) and not i.filename.startswith('/') and '..' not in i.filename.split('/')]
  return sorted(names, key=lambda s:[int(v) if v.isdigit() else v.lower() for v in re.split(r'(\d+)',s)])
class ReaderRelease(Release):
 def do_GET(self):
  p=urllib.parse.urlparse(self.path)
  if p.path.startswith('/api/ebook/'):
   u=self._auth()
   if not u:return
   try:fid=int(p.path.rsplit('/',1)[-1]);page=int(urllib.parse.parse_qs(p.query).get('page',['0'])[0])
   except:return self.send(400,{'error':'Invalid file or page'})
   with db() as c:
    f=c.execute('SELECT * FROM book_files WHERE id=?',(fid,)).fetchone()
    if not f:return self.send(404,{'error':'File not found'})
    access=c.execute('SELECT 1 FROM library WHERE user_id=? AND book_id=?',(u['id'],f['book_id'])).fetchone()
    owner=c.execute('SELECT merchant_id FROM books WHERE id=?',(f['book_id'],)).fetchone()
    if not access and u['role']!='admin' and (not owner or owner['merchant_id']!=u['id']):return self.send(403,{'error':'Access denied'})
   if f['kind'] not in ('epub','cbz'):return self.send(415,{'error':'Not an EPUB/CBZ file'})
   path=os.path.join(UPLOAD,os.path.basename(f['filename']))
   if not os.path.isfile(path):return self.send(404,{'error':'Missing file'})
   try:
    names=archive_entries(path,f['kind'])
    if not names:return self.send(422,{'error':'No readable pages found'})
    if not 0<=page<len(names):return self.send(400,{'error':'Page out of range'})
    with zipfile.ZipFile(path) as z:
     entry=z.getinfo(names[page]);raw=z.read(entry)
    if f['kind']=='epub':
     parser=TextExtractor();parser.feed(raw.decode('utf-8','replace'));return self.send(200,{'format':'epub','page':page,'total':len(names),'chapter':names[page].rsplit('/',1)[-1],'text':parser.text()[:150000]})
    import base64
    mime='image/webp' if names[page].lower().endswith('.webp') else ('image/png' if names[page].lower().endswith('.png') else 'image/jpeg')
    if len(raw)>8*1024*1024:return self.send(413,{'error':'Image too large'})
    return self.send(200,{'format':'cbz','page':page,'total':len(names),'image':'data:'+mime+';base64,'+base64.b64encode(raw).decode('ascii')})
   except (zipfile.BadZipFile,ValueError,RuntimeError,KeyError):return self.send(422,{'error':'Invalid or unsupported archive'})
  return super().do_GET()
if __name__=='__main__':
 from release_server import install
 from scheduler import start_maintenance
 from http.server import ThreadingHTTPServer
 install();start_maintenance();port=int(os.getenv('PORT','8000'))
 print('LibraAI with EPUB/CBZ reader: http://127.0.0.1:'+str(port))
 ThreadingHTTPServer(('127.0.0.1',port),ReaderRelease).serve_forever()
