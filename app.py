import os, sqlite3, secrets, time, io, json
from pathlib import Path
from datetime import timedelta
from collections import defaultdict, deque
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, abort, send_file, flash, jsonify
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
  response.headers['Content-Security-Policy']="default-src 'self'; img-src 'self' blob:; style-src 'self'; script-src 'self'; form-action 'self'; frame-ancestors 'none'; base-uri 'self'"
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
  responses,photos=all_data();return render_template('home.html',completed=responses,photos=[p for p in photos if p['kind']=='recent'])
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
    flash('Your answers are saved. Next: choose photos and upload them.');return redirect(url_for('member',name=name,_anchor='photos'))
   row=c.execute('SELECT * FROM responses WHERE name=?',(name,)).fetchone()
   photos=c.execute('SELECT * FROM photos WHERE name=? ORDER BY rowid',(name,)).fetchall()
  groups=[];offset=0
  for heading,labels in SECTIONS.items():
   groups.append((heading,FIELDS[offset:offset+len(labels)]));offset+=len(labels)
  return render_template('member.html',name=name,groups=groups,answers=json.loads(row['answers']) if row else {},photos=photos,updated=row['updated'] if row else None)
 def upload_result(name,message,success=False,status=400):
  if request.accept_mimetypes.best=='application/json':
   with db() as c:photos=c.execute('SELECT * FROM photos WHERE name=? ORDER BY rowid',(name,)).fetchall()
   return jsonify(success=success,message=message,gallery=render_template('_photo_gallery.html',name=name,photos=photos)),200 if success else status
  flash(message);return redirect(url_for('member',name=name,_anchor='photos'))
 @app.errorhandler(413)
 def too_large(error):
  message='That upload is too large. Choose up to 5 photos, each 10 MB or smaller.'
  if request.accept_mimetypes.best=='application/json':return jsonify(success=False,message=message),413
  if request.view_args and request.view_args.get('name') in NAMES:
   flash(message);return redirect(url_for('member',name=request.view_args['name'],_anchor='photos'))
  return message,413
 @app.post('/crew/<name>/photos')
 @private
 def upload(name):
  if name not in NAMES:abort(404)
  kind=request.form.get('kind');files=[f for f in request.files.getlist('photos') if f.filename]
  replace_id=request.form.get('replace_id')
  if kind not in ('recent','childhood') or not files:return upload_result(name,'Choose a photo first.')
  if len(files)>(1 if replace_id or kind=='childhood' else 5):
   return upload_result(name,'Choose one replacement or childhood photo, or up to 5 recent photos.')
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
   return upload_result(name,str(e) if isinstance(e,ValueError) else 'This photo could not be read. Try another image.')
  written=[]
  try:
   with db() as c:
    c.execute('BEGIN IMMEDIATE')
    old=None
    if replace_id:
     old=c.execute('SELECT * FROM photos WHERE id=? AND name=? AND kind=?',(replace_id,name,kind)).fetchone()
     if not old:return upload_result(name,'That photo is no longer available to replace. Refresh and try again.',status=409)
    count=c.execute('SELECT count(*) FROM photos WHERE name=? AND kind=?',(name,kind)).fetchone()[0]
    if count+len(prepared)-(1 if old else 0)>(5 if kind=='recent' else 1):
     return upload_result(name,'Keep up to 5 recent photos and one childhood photo. Use Replace or Remove on an existing photo.')
    caption=request.form.get('caption',old['caption'] if old else '')[:300]
    for ident,content in prepared:
     path=data/'photos'/f'{ident}.jpg';written.append(path);path.write_bytes(content)
     if old:c.execute('UPDATE photos SET id=?,caption=? WHERE id=?',(ident,caption,replace_id))
     else:c.execute('INSERT INTO photos VALUES(?,?,?,?)',(ident,name,kind,caption))
  except (OSError,sqlite3.Error):
   for path in written:path.unlink(missing_ok=True)
   app.logger.exception('Photo storage failed')
   return upload_result(name,'The photo could not be saved. Your existing photos are unchanged. Please try again.',status=503)
  if replace_id:
   try:(data/'photos'/f'{replace_id}.jpg').unlink(missing_ok=True)
   except OSError:app.logger.warning('Old replacement file could not be removed')
  return upload_result(name,'Uploaded ✓ — your photos are saved.' if not replace_id else 'Uploaded ✓ — your replacement is saved.',success=True)
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
  (data/'photos'/f'{ident}.jpg').unlink(missing_ok=True);return upload_result(row['name'],'Photo removed.',success=True)
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
