#!/usr/bin/env python
#coding=utf8

import StringIO
import base64
import binascii
import cookielib
import gzip
import hashlib
import json
import os
import re
from urllib import unquote
import urllib
import urllib2

import poster
import rsa

import log
from poster.streaminghttp import register_openers
import random

class sina_login:
    parameters = {
        'entry': 'weibo',
        'callback': 'sinaSSOController.preloginCallBack',
        'su': 'TGVuZGZhdGluZyU0MHNpbmEuY29t',
        'rsakt': 'mod',
        'checkpin': '1',
        'client': 'ssologin.js(v1.4.5)',
        '_': '1362560902427'
    }
    
    postdata = {
        'entry': 'weibo',
        'gateway': '1',
        'from': '',
        'savestate': '7',
        'useticket': '1',
        'pagerefer': '',
        'vsnf': '1',
        'su': '',
        'service': 'miniblog',
        'servertime': '',
        'nonce': '',
        'pwencode': 'rsa2',
        'rsakv': '',
        'sp': '',
        'encoding': 'UTF-8',
        'prelt': '27',
        'url': 'http://www.weibo.com/ajaxlogin.php?framelogin=1&callback=parent.sinaSSOController.feedBackUrlCallBack',
        'returntype': 'META'
    }
    #random = 1000000
    verify_server_url = 'http://localhost:8080/verify'
    
    def __init__(self):
        '''
        Constructor
        '''
        #login code from:  http://www.douban.com/note/201767245/
        #加了下注释
        # cookie -&gt; opener -&gt; urllib2.
        # 然后，urllib2的操作相关cookie会存在
        # 所以登陆成功之后，urllib2的操作会带有cookie信息，抓网页不会跳转到登陆页
        cookiejar = cookielib.LWPCookieJar()
        cookie_support = urllib2.HTTPCookieProcessor(cookiejar)
        opener = urllib2.build_opener(cookie_support, urllib2.HTTPHandler)
        urllib2.install_opener(opener)
        
    def get_servertime(self):
        url = 'http://login.sina.com.cn/sso/prelogin.php?' + urllib.urlencode(self.parameters)
        data = urllib2.urlopen(url).read()
        p = re.compile('\((.*)\)')
        try:
            json_data = p.search(data).group(1)
            data = json.loads(json_data)
            servertime = str(data['servertime'])
            nonce = data['nonce']
            pubkey = data['pubkey']
            rsakv = data['rsakv']
            pcid = data['pcid']
            return servertime, nonce, pubkey, rsakv, pcid
        except Exception as e:
            print 'Get severtime error!'
            log.logging.error("Get severtime error! message :%s"%(e))
            return None
    
    def get_pwd(self,pwd, servertime, nonce, pubkey):
        #先创建一个rsa公钥，公钥的两个参数新浪微博都给了是固定值，不过给的都是16进制的字符串，
        #第一个是登录第一步中的pubkey，第二个是js加密文件中的‘10001’。
        #这两个值需要先从16进制转换成10进制，不过也可以写死在代码里。我就把‘10001’直接写死为65537
        rsaPublickey = int(pubkey, 16)
        key = rsa.PublicKey(rsaPublickey, 65537) #创建公钥
        message = str(servertime) + '\t' + str(nonce) + '\n' + str(pwd) #拼接明文 js加密文件中得到
        passwd = rsa.encrypt(message, key) #加密
        passwd = binascii.b2a_hex(passwd)  #将加密信息转换为16进制
        return passwd
    
    def get_user(self,username):
        username_ = urllib.quote(username)
        username = base64.encodestring(username_)[:-1]
        return username
    
    def get_door(self,pcid):
        #下载验证码
        verify_pic_url = "http://login.sina.com.cn/cgi/pin.php?r=%s&s=0&p=%s"%(str(random.random()),str(pcid))
        log.logging.info("login_weibo - verify_pic_url: %s"%verify_pic_url)
        urllib.urlretrieve(verify_pic_url,"pin.jpg")
        '''
        #调用验证码识别服务，识别验证码
        register_openers() 
        params = {'vfile': open("pin.jpg", "rb"), 'name': 'vfile'}
        datagen, headers = poster.encode.multipart_encode(params)
        request = urllib2.Request(self.verify_server_url, datagen, headers)
        result = urllib2.urlopen(request)
        door = result.read()
        '''
        door = raw_input('请输入验证码:')
        return door
        
    def login_weibo(self,username, pwd, doorOpen = False):
        
        url = 'http://login.sina.com.cn/sso/login.php?client=ssologin.js(v1.4.5)'
        try:
            servertime, nonce, pubkey, rsakv, pcid = self.get_servertime()
        except Exception as e:
            log.logging.error("login - error msg : %s" % (e))
            return
        
        if doorOpen :
            self.postdata['door'] = self.get_door(pcid)
        self.postdata['servertime'] = servertime
        self.postdata['nonce'] = nonce
        self.postdata['rsakv'] = rsakv
        self.postdata['su'] = self.get_user(username)
        self.postdata['sp'] = self.get_pwd(pwd, servertime, nonce, pubkey)
        postdata = urllib.urlencode(self.postdata)
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Linux i686; rv:8.0) Gecko/20100101 Firefox/8.0'}
    
        req = urllib2.Request(
            url=url,
            data=postdata,
            headers=headers
        )
        text=False
        try:
            result = urllib2.urlopen(req)
            #text = result.read()
            if result.info().get('Content-Encoding') == 'gzip':
                buf = StringIO( result.read())
                f = gzip.GzipFile(fileobj=buf)
                text = f.read().encode('utf-8')
            else:
                text = result.read()
            print str(text).decode("gb2312")
            
            url_arr = re.findall(".*?replace\((\"|')(.*)(\"|')\).*?",text)
            login_url = url_arr[0][1]
            log.logging.info("login - login_url %s" % (login_url))
            
            if "retcode=0" in login_url :
                result = urllib2.urlopen(login_url)
                text = result.read()
                #print str(text).decode("gb2312")
                
                #test crawl current user
                uid = re.findall('"uniqueid":"(\d+)",',text)[0]
                url = "http://weibo.com/u/"+uid
                result = urllib2.urlopen(url)
                text = result.read()
                print text
                
                print "登录成功!"
                log.logging.info("登录成功!")
                return True
            elif "retcode=4049" in login_url :
                log.logging.info('login_weibo-->异地登陆失败,需要验证码!')
                # retry login weibo
                self.login_weibo(username, pwd, True)
            elif "retcode=5" in login_url :
                log.logging.info("login_weibo-->异地登陆失败,用户名不存在!")
                return False
            elif "retcode=2070" in login_url :
                log.logging.info("login_weibo-->异地登陆失败,验证码输入错误!")
                # retry login weibo
                self.login_weibo(username, pwd, True)
            else :
                log.logging.info("login_weibo-->登陆失败,用户名或密码错误!")
                return False
            
        except Exception as e:
            print 'Login error! message: %s \r\n html: %s'%(e,text)
            log.logging.error('Login error! message: %s \r\n html: %s'%(e,text))
            return False