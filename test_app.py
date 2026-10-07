import unittest, tempfile, io, re, sqlite3
from pathlib import Path
from PIL import Image
from werkzeug.security import generate_password_hash
from app import create_app, NAMES

class SiteTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)
  self.app=create_app({'TESTING':True,'DATA_DIR':self.path,'PASSWORD_HASH':generate_password_hash('test-password')})
  self.client=self.app.test_client()
 def tearDown(self):self.temp.cleanup()
 def token(self):
  with self.client.session_transaction() as s:return s['csrf']
 def login(self):
  self.client.get('/login');return self.client.post('/login',data={'csrf':self.token(),'password':'test-password'})
 def post(self,url,data=None):return self.client.post(url,data={'csrf':self.token(),**(data or {})},follow_redirects=True)
 def image(self):
  b=io.BytesIO();Image.new('RGB',(20,20),'red').save(b,'PNG');b.seek(0);return b
 def test_private_routes_and_csrf(self):
  for route in ['/','/updates','/crew/Abby','/gratitude','/halloween','/editions','/photos/unknown','/summer','/summer/newsletter.pdf','/summer/newsletter.pdf?download=1','/camp']:
   self.assertEqual(self.client.get(route).status_code,302)
  self.assertEqual(self.client.post('/login',data={'password':'test-password'}).status_code,400)
  self.client.get('/login')
  self.assertEqual(self.client.post('/login',data={'csrf':self.token(),'password':'wrong'}).status_code,401)
  self.login();self.assertEqual(self.client.post('/crew/Abby',data={'q0':'bad'}).status_code,400)
 def test_pages_save_and_persistence(self):
  self.login()
  for route in ['/','/updates','/gratitude','/halloween','/editions']+['/crew/'+n for n in NAMES]:self.assertEqual(self.client.get(route).status_code,200)
  self.post('/crew/Abby',{'q0':'Busy, happy, hopeful','q8':'My friends','q9':'A tiny witch','q4':'<script>alert(1)</script>'})
  self.assertIn(b'My friends',self.client.get('/gratitude').data)
  self.assertIn(b'A tiny witch',self.client.get('/halloween').data)
  self.assertNotIn(b'<script>alert(1)</script>',self.client.get('/crew/Abby').data)
  self.post('/updates',{'updates':'Dinner together next week'})
  self.assertIn(b'Dinner together next week',self.client.get('/updates').data)
  second=create_app({'TESTING':True,'DATA_DIR':self.path,'PASSWORD_HASH':generate_password_hash('test-password')}).test_client()
  second.get('/login')
  with second.session_transaction() as s:token=s['csrf']
  second.post('/login',data={'csrf':token,'password':'test-password'})
  self.assertIn(b'Busy, happy, hopeful',second.get('/crew/Abby').data)
 def test_photos_protection_limits_and_removal(self):
  self.login()
  self.post('/crew/Abby/photos',{'kind':'childhood','photos':(self.image(),'photo.png'),'caption':'Halloween 1990'})
  with sqlite3.connect(self.path/'trf.sqlite3') as c:ident=c.execute('SELECT id FROM photos').fetchone()[0]
  photo_response=self.client.get('/photos/'+ident)
  self.assertEqual(photo_response.status_code,200)
  photo_response.close()
  self.assertIn(b'Halloween 1990',self.client.get('/halloween').data)
  self.post('/crew/Abby/photos',{'kind':'childhood','photos':(self.image(),'other.png')})
  with sqlite3.connect(self.path/'trf.sqlite3') as c:self.assertEqual(c.execute('SELECT count(*) FROM photos').fetchone()[0],1)
  self.post('/crew/Abby/photos',{'kind':'recent','photos':(io.BytesIO(b'fake'),'fake.png')})
  self.post('/logout');self.assertEqual(self.client.get('/photos/'+ident).status_code,302)
  self.login();self.post('/photos/'+ident+'/delete');self.assertEqual(self.client.get('/photos/'+ident).status_code,404)
 def test_existing_uploads_survive_restart_and_display(self):
  self.login()
  self.post('/crew/Abby',{'q1':'A weekend with friends'})
  self.post('/crew/Abby/photos',{'kind':'recent','photos':(self.image(),'recent.png'),'caption':'At the lake'})
  self.post('/crew/Abby/photos',{'kind':'childhood','photos':(self.image(),'child.png'),'caption':'Little pumpkin'})
  with sqlite3.connect(self.path/'trf.sqlite3') as c:rows=c.execute('SELECT id FROM photos').fetchall()
  originals={ident:(self.path/'photos'/f'{ident}.jpg').read_bytes() for (ident,) in rows}
  self.app=create_app({'TESTING':True,'DATA_DIR':self.path,'PASSWORD_HASH':generate_password_hash('test-password')})
  self.client=self.app.test_client();self.login()
  home=self.client.get('/').data
  self.assertIn(b'At the lake',home);self.assertIn(b'A weekend with friends',home)
  self.assertNotIn(b'Little pumpkin',home)
  halloween=self.client.get('/halloween').data
  self.assertIn(b'Little pumpkin',halloween);self.assertNotIn(b'At the lake',halloween)
  member=self.client.get('/crew/Abby').data.decode()
  self.assertIn('Uploaded ✓',member);self.assertIn('At the lake',member);self.assertIn('Little pumpkin',member)
  for ident,content in originals.items():
   self.assertEqual((self.path/'photos'/f'{ident}.jpg').read_bytes(),content)
   response=self.client.get('/photos/'+ident);self.assertEqual(response.status_code,200);response.close()
  self.assertNotIn(b'At the lake',self.client.get('/crew/Sue').data)
 def test_async_upload_and_safe_replacement(self):
  self.login()
  def upload(data,name='Abby'):
   return self.client.post('/crew/'+name+'/photos',data={'csrf':self.token(),**data},headers={'Accept':'application/json'})
  response=upload({'kind':'childhood','photos':(self.image(),'old.png'),'caption':'Original caption'})
  self.assertEqual(response.status_code,200);self.assertTrue(response.json['success'])
  self.assertIn('Uploaded ✓',response.json['gallery'])
  with sqlite3.connect(self.path/'trf.sqlite3') as c:ident=c.execute('SELECT id FROM photos').fetchone()[0]
  original=(self.path/'photos'/f'{ident}.jpg').read_bytes()
  response=upload({'kind':'childhood','replace_id':ident,'photos':(io.BytesIO(b'invalid'),'bad.png')})
  self.assertEqual(response.status_code,400);self.assertFalse(response.json['success'])
  self.assertEqual((self.path/'photos'/f'{ident}.jpg').read_bytes(),original)
  response=upload({'kind':'childhood','replace_id':ident,'photos':(self.image(),'wrong.png')},name='Sue')
  self.assertEqual(response.status_code,409)
  self.assertTrue((self.path/'photos'/f'{ident}.jpg').exists())
  response=upload({'kind':'childhood','replace_id':ident,'photos':(self.image(),'new.png'),'caption':'New caption'})
  self.assertTrue(response.json['success']);self.assertIn('New caption',response.json['gallery'])
  with sqlite3.connect(self.path/'trf.sqlite3') as c:
   self.assertEqual(c.execute('SELECT count(*) FROM photos').fetchone()[0],1)
   new_id=c.execute('SELECT id FROM photos').fetchone()[0]
  self.assertNotEqual(ident,new_id);self.assertFalse((self.path/'photos'/f'{ident}.jpg').exists())
  self.assertTrue((self.path/'photos'/f'{new_id}.jpg').exists())
  response=self.client.post('/photos/'+new_id+'/delete',data={'csrf':self.token()},headers={'Accept':'application/json'})
  self.assertTrue(response.json['success']);self.assertNotIn(new_id,response.json['gallery'])
 def test_homepage_portraits_are_separate_and_persistent(self):
  self.login()
  self.post('/crew/Gabby/photos',{'kind':'recent','photos':(self.image(),'recent.png'),'caption':'Keep this memory'})
  self.post('/crew/Gabby/photos',{'kind':'profile','photos':(self.image(),'portrait.png'),'caption':'Gabby portrait'})
  with sqlite3.connect(self.path/'trf.sqlite3') as c:
   ident=c.execute("SELECT id FROM photos WHERE kind='profile'").fetchone()[0]
  html=self.client.get('/').data.decode()
  self.assertIn('Gabby’s portrait',html);self.assertIn('/photos/'+ident,html)
  self.assertNotIn('Gabby portrait',self.client.get('/halloween').data.decode())
  self.assertIn('Homepage Portrait',self.client.get('/crew/Gabby').data.decode())
  self.post('/crew/Gabby/photos',{'kind':'profile','photos':(self.image(),'extra.png')})
  with sqlite3.connect(self.path/'trf.sqlite3') as c:self.assertEqual(c.execute("SELECT count(*) FROM photos WHERE kind='profile'").fetchone()[0],1)
  self.post('/crew/Gabby/photos',{'kind':'profile','replace_id':ident,'photos':(self.image(),'replacement.png')})
  self.assertIn(b'Keep this memory',self.client.get('/').data)
  self.app=create_app({'TESTING':True,'DATA_DIR':self.path,'PASSWORD_HASH':generate_password_hash('test-password')})
  self.client=self.app.test_client();self.login()
  self.assertIn('Gabby’s portrait',self.client.get('/').data.decode())
 def test_summer_and_camp(self):
  self.login()
  self.assertIn(b'Summer 2026',self.client.get('/editions').data)
  self.assertIn(b'Read the newsletter',self.client.get('/summer').data)
  response=self.client.get('/summer/newsletter.pdf')
  self.assertEqual(response.status_code,200)
  self.assertTrue(response.data.startswith(b'%PDF-'))
  self.assertEqual(response.headers['Cache-Control'],'no-store')
  response.close()
  response=self.client.get('/summer/newsletter.pdf?download=1')
  self.assertIn('attachment',response.headers['Content-Disposition'])
  response.close()
  camp=self.client.get('/camp').data.decode()
  self.assertIn('July 9–11, 2027',camp)
  self.assertIn('Details coming soon',camp)
  self.post('/logout')
  self.assertEqual(self.client.get('/summer/newsletter.pdf').status_code,302)
 def test_login_rate_limit(self):
  self.client.get('/login')
  for _ in range(10):self.assertEqual(self.client.post('/login',data={'csrf':self.token(),'password':'wrong'}).status_code,401)
  self.assertEqual(self.client.post('/login',data={'csrf':self.token(),'password':'wrong'}).status_code,429)

if __name__=='__main__':unittest.main()
