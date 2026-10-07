import os, sqlite3, secrets, time, io, json
from pathlib import Path
from datetime import timedelta
from collections import defaultdict, deque
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, abort, send_file, flash
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image, ImageOps, UnidentifiedImageError

NAMES = ['Abby','Angel','Christine','Debbie','Gabby','Gloria','Hannah','Heidi','Rhea','Stephanie','Sue']
SECTIONS = {
 'Life lately': ['Current season in 3 words','Biggest life update since summer','Something really good right now',"Something that’s been hard",'How are you really doing?'],
 'Family + life': ['Quick family / kid update','A recent win or fail that made you laugh','Work / life update'],
 'Fall check-in': ['What are you thankful for right now?','What was your favorite Halloween costume as a kid?','What are you looking forward to this holiday season?'],
 'Current favorites': ['Watching','Listening to','Eating / drinking','Loving / recommending','Text me about']}
FIELDS = [(f'q{i}',label) for i,label in enumerate(sum(SECTIONS.values(),[]))]
GROUP_FIELDS = [('updates','Group updates'),('dates','Upcoming dates'),('prayers','Prayer requests / Celebrations'),('notes','Notes')]

def create_app(config=None):
 app = Flask(__name__)
 data = Path(os.environ.get('TRF_DATA_DIR', str(Path(__file__).parent/'instance')))
 app.config.update(DATA_DIR=data, MAX_CONTENT_LENGTH=55*1024*1024, SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE='Lax', SESSION_COOKIE_SECURE=os.environ.get('TRF_SECURE_COOKIES')=='1', PERMANENT_SESSION_LIFETIME=timedelta(hours=12))
 if config: app.config.update(config)
 data=Path(app.config['DATA_DIR']);data.mkdir(parents=True,exist_ok=True);(data/'photos').mkdir(exist_ok=True)
 key=data/'session.key'
 if not key.exists():
  with key.open('x') as f: f.write(secrets.token_hex(32))
  key.chmod(0o600)
 app.secret_key=key.read_text()
 password_hash=app.config.get('PASSWORD_HASH') or os.environ.get('TRF_PASSWORD_HASH')
 if not password_hash and os.environ.get('TRF_PASSWORD'):
  password_hash=generate_password_hash(os.environ['TRF_PASSWORD'])
 if not password_hash:
  pw=data/'password.txt'
  if not pw.exists():
   with pw.open('x') as f:f.write(secrets.token_urlsafe(18))
   pw.chmod(0o600)
  password_hash=generate_password_hash(pw.read_text().strip())
 app.config['PASSWORD_HASH']=password_hash
 def db():
  conn=sqlite3.connect(data/'trf.sqlite3');conn.row_factory=sqlite3.Row;return conn
 with db() as c:
  c.executescript('CREATE TABLE IF NOT EXISTS responses (name TEXT PRIMARY KEY, answers TEXT NOT NULL, updated TEXT NOT NULL); CREATE TABLE IF NOT EXISTS group_updates (id INTEGER PRIMARY KEY, answers TEXT NOT NULL); CREATE TABLE IF NOT EXISTS photos (id TEXT PRIMARY KEY, name TEXT NOT NULL, kind TEXT NOT NULL, caption TEXT NOT NULL);')
 attempts=defaultdict(deque)
 @app.before_request
 def security():
  if request.method=='POST' and (not session.get('csrf') or not secrets.compare_digest(session['csrf'], request.form.get('csrf',''))): abort(400)
 @app.after_request
 def headers(response):
  response.headers['Cache-Control']='no-store'
  response.headers['X-Content-Type-Options']='nosniff'
  response.headers['X-Frame-Options']='DENY'
  response.headers['Referrer-Policy']='same-origin'
  response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self'; style-src 'self'; script-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
  return response
 @app.context_processor
 def context():
  if 'csrf' not in session:session['csrf']=secrets.token_hex(32)
  return dict(names=NAMES,csrf=session['csrf'])
 def private(fn):
  @wraps(fn)
  def wrapped(*a,**kw):
   if not session.get('authenticated'):return redirect(url_for('login'))
   return fn(*a,**kw)
  return wrapped
 @app.route('/login',methods=['GET','POST'])
 def login():
  if request.method=='POST':
   bucket=attempts[request.remote_addr]; now=time.monotonic()
   while bucket and bucket[0]<now-900:bucket.popleft()
   if len(bucket)>=10: return render_template('login.html',error='Too many attempts. Please try again in 15 minutes.'),429
   bucket.append(now)
   if check_password_hash(app.config['PASSWORD_HASH'],request.form.get('password','')):
    session.clear();session['authenticated']=True;session['csrf']=secrets.token_hex(32);session.permanent=True
    return redirect(url_for('home'))
   return render_template('login.html',error='That password doesn’t match. Try again.'),401
  return render_template('login.html')
 @app.post('/logout')
 @private
 def logout():session.clear();return redirect(url_for('login'))
 def all_data():
  with db() as c:
   responses={r['name']:json.loads(r['answers']) for r in c.execute('SELECT * FROM responses')}
   photos=c.execute('SELECT * FROM photos ORDER BY rowid').fetchall()
  return responses,photos
 @app.get('/')
 @private
 def home():
  responses,_=all_data();return render_template('home.html',completed=responses)
 @app.route('/updates',methods=['GET','POST'])
 @private
 def updates():
  with db() as c:
   if request.method=='POST':
    answers={k:request.form.get(k,'')[:5000] for k,_ in GROUP_FIELDS};c.execute('INSERT OR REPLACE INTO group_updates VALUES(1,?)',(json.dumps(answers),));flash('Group updates saved.');return redirect(url_for('updates'))
   row=c.execute('SELECT answers FROM group_updates WHERE id=1').fetchone()
  return render_template('updates.html',fields=GROUP_FIELDS,answers=json.loads(row[0]) if row else {})
 @app.route('/crew/<name>',methods=['GET','POST'])
 @private
 def member(name):
  if name not in NAMES:abort(404)
  with db() as c:
   if request.method=='POST':
    answers={k:request.form.get(k,'')[:3000] for k,_ in FIELDS}
    c.execute('INSERT OR REPLACE INTO responses VALUES(?,?,datetime("now"))',(name,json.dumps(answers)))
    flash('Your answers are saved.');return redirect(url_for('member',name=name))
   row=c.execute('SELECT * FROM responses WHERE name=?',(name,)).fetchone()
   photos=c.execute('SELECT * FROM photos WHERE name=? ORDER BY rowid',(name,)).fetchall()
  groups=[];offset=0
  for heading,labels in SECTIONS.items():
   groups.append((heading,FIELDS[offset:offset+len(labels)]));offset+=len(labels)
  return render_template('member.html',name=name,groups=groups,answers=json.loads(row['answers']) if row else {},photos=photos,updated=row['updated'] if row else None)
 @app.post('/crew/<name>/photos')
 @private
 def upload(name):
  if name not in NAMES:abort(404)
  kind=request.form.get('kind');files=[f for f in request.files.getlist('photos') if f.filename]
  if kind not in ('recent','childhood') or not files:flash('Choose a photo first.');return redirect(url_for('member',name=name))
  if len(files)>(5 if kind=='recent' else 1):
   flash('Upload up to 5 recent photos or one childhood photo at a time.');return redirect(url_for('member',name=name))
  prepared=[]
  try:
   for f in files:
    raw=f.read(10*1024*1024+1)
    if len(raw)>10*1024*1024:raise ValueError('Each photo must be 10 MB or smaller.')
    with Image.open(io.BytesIO(raw)) as im:
     if im.format not in ('JPEG','PNG','WEBP'):raise ValueError('Please use JPG, PNG, or WebP photos.')
     im.load();clean=ImageOps.exif_transpose(im).convert('RGB');clean.thumbnail((2400,2400))
     out=io.BytesIO();clean.save(out,format='JPEG',quality=88);prepared.append((secrets.token_hex(16),out.getvalue()))
  except (UnidentifiedImageError,OSError,ValueError,Image.DecompressionBombError) as e:
   flash(str(e) if isinstance(e,ValueError) else 'This photo could not be read. Try another image.');return redirect(url_for('member',name=name))
  with db() as c:
   c.execute('BEGIN IMMEDIATE')
   count=c.execute('SELECT count(*) FROM photos WHERE name=? AND kind=?',(name,kind)).fetchone()[0]
   if count+len(prepared)>(5 if kind=='recent' else 1):flash('Keep up to 5 recent photos and one childhood photo. Remove a photo to replace it.');return redirect(url_for('member',name=name))
   for ident,content in prepared:
    (data/'photos'/f'{ident}.jpg').write_bytes(content)
    c.execute('INSERT INTO photos VALUES(?,?,?,?)',(ident,name,kind,request.form.get('caption','')[:300]))
  flash('Photos uploaded.');return redirect(url_for('member',name=name))
 @app.get('/photos/<ident>')
 @private
 def photo(ident):
  with db() as c:row=c.execute('SELECT id FROM photos WHERE id=?',(ident,)).fetchone()
  if not row:abort(404)
  return send_file(data/'photos'/f'{ident}.jpg',mimetype='image/jpeg')
 @app.post('/photos/<ident>/delete')
 @private
 def delete_photo(ident):
  with db() as c:
   row=c.execute('SELECT name FROM photos WHERE id=?',(ident,)).fetchone()
   if not row:abort(404)
   c.execute('DELETE FROM photos WHERE id=?',(ident,))
  (data/'photos'/f'{ident}.jpg').unlink(missing_ok=True);flash('Photo removed.');return redirect(url_for('member',name=row['name']))
 @app.get('/gratitude')
 @private
 def gratitude():
  responses,_=all_data();return render_template('collection.html',title='Room for gratitude.',eyebrow='What we’re thankful for',responses=responses,photos=[],field='q8')
 @app.get('/halloween')
 @private
 def halloween():
  responses,photos=all_data();return render_template('collection.html',title='Halloween, way back.',eyebrow='Our childhood costume archive',responses=responses,photos=[p for p in photos if p['kind']=='childhood'],field='q9')
 @app.get('/summer')
 @private
 def summer():return render_template('summer.html')
 @app.get('/summer/newsletter.pdf')
 @private
 def summer_pdf():
  return send_file(Path(__file__).parent/'content'/'summer-2026.pdf',mimetype='application/pdf',as_attachment=request.args.get('download')=='1',download_name='TRF-Summer-2026.pdf')
 @app.get('/camp')
 @private
 def camp():return render_template('camp.html')
 @app.get('/editions')
 @private
 def editions():return render_template('editions.html')
 return app

if __name__=='__main__':create_app().run(host='0.0.0.0',port=int(os.environ.get('PORT','3000')))
