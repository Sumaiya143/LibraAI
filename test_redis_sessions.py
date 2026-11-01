import sys, types, unittest
from unittest.mock import patch
from http.cookies import SimpleCookie
from flask import Flask, request
from redis_sessions import RedisSessionInterface

class FakeRedis:
    def __init__(self): self.data={}
    def ping(self): return True
    def get(self,key): return self.data.get(key)
    def set(self,key,value,ex=None): self.data[key]=value; return True
    def delete(self,key): return int(self.data.pop(key,None) is not None)

class RedisSessionTests(unittest.TestCase):
    def setUp(self):
        self.client=FakeRedis()
        module=types.ModuleType('redis')
        class RedisFactory:
            @staticmethod
            def from_url(*args,**kwargs): return self.client
        module.Redis=RedisFactory
        self.patch=patch.dict(sys.modules,{'redis':module}); self.patch.start()
        self.addCleanup(self.patch.stop)
        self.app=Flask(__name__); self.app.secret_key='unit-test-secret-key-with-more-than-32-chars'; self.app.config['SESSION_COOKIE_NAME']='session'
        self.interface=RedisSessionInterface('redis://fake'); self.app.session_interface=self.interface
    def test_session_roundtrip_uses_opaque_cookie_and_server_store(self):
        with self.app.test_request_context('/'):
            sess=self.interface.open_session(self.app,request); sess['uid']=23; sess.permanent=True
            response=self.app.make_response('ok'); self.interface.save_session(self.app,sess,response)
            cookie=SimpleCookie(); cookie.load(response.headers.get('Set-Cookie'))
            sid_cookie=cookie['session'].value
        self.assertNotIn('uid',sid_cookie)
        with self.app.test_request_context('/',headers={'Cookie':f'session={sid_cookie}'}):
            restored=self.interface.open_session(self.app,request)
            self.assertEqual(restored['uid'],23)
    def test_login_rotation_replaces_old_server_session_id(self):
        with self.app.test_request_context('/'):
            sess=self.interface.open_session(self.app,request); sess['uid']=1
            response=self.app.make_response('ok'); self.interface.save_session(self.app,sess,response)
            cookie=SimpleCookie(); cookie.load(response.headers.get('Set-Cookie')); old_cookie=cookie['session'].value
        with self.app.test_request_context('/',headers={'Cookie':f'session={old_cookie}'}):
            sess=self.interface.open_session(self.app,request); old_sid=sess.sid
            sess.clear(); sess['uid']=2
            response=self.app.make_response('ok'); self.interface.save_session(self.app,sess,response)
            cookie=SimpleCookie(); cookie.load(response.headers.get('Set-Cookie')); new_cookie=cookie['session'].value
        self.assertNotEqual(old_cookie,new_cookie)
        self.assertNotIn('libraai:sess:'+old_sid,self.client.data)
        with self.app.test_request_context('/',headers={'Cookie':f'session={new_cookie}'}):
            restored=self.interface.open_session(self.app,request); self.assertEqual(restored['uid'],2)

if __name__=='__main__': unittest.main()
