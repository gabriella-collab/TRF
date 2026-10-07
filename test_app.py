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
  self.assertEqual(self.client.get('/photos/'+ident).status_code,200)
  self.assertIn(b'Halloween 1990',self.client.get('/halloween').data)
  self.post('/crew/Abby/photos',{'kind':'childhood','photos':(self.image(),'other.png')})
  with sqlite3.connect(self.path/'trf.sqlite3') as c:self.assertEqual(c.execute('SELECT count(*) FROM photos').fetchone()[0],1)
  self.post('/crew/Abby/photos',{'kind':'recent','photos':(io.BytesIO(b'fake'),'fake.png')})
  self.post('/logout');self.assertEqual(self.client.get('/photos/'+ident).status_code,302)
  self.login();self.post('/photos/'+ident+'/delete');self.assertEqual(self.client.get('/photos/'+ident).status_code,404)
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
