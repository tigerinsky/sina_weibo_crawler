#!/user/bin/env python
#coding: utf-8

'''
Created on 2015年8月18日
'''

import ConfigParser
import Queue
from StringIO import StringIO
import cookielib
from datetime import datetime
import errno
import gzip
import hashlib
import json
import os
import random
import re
import re
import sys
import thread
from time import sleep
import time
import traceback
from urllib import urlretrieve
import urllib
import urllib2

from bs4 import BeautifulSoup
import threadpool
import threading
import MySQLdb

import log
import login
from loginsinacom import LoginSinaCom
import sinaio
from weiborequest import getHtmlSource


reload(sys)
sys.setdefaultencoding('utf8')

class Spider(threading.Thread):
    '''
    classdocs
    '''

    def __init__(self, cf, crawled_avatar_conf, crawled_img_conf, account_index):
        '''
        Constructor
        '''
        super(Spider, self).__init__()

        # Create DB connect
        self.conn=MySQLdb.connect(
                          host="rdsjn2362jctbdvwi63h9.mysql.rds.aliyuncs.com",
                          user="nvshen",
                          passwd="MhxzKhl2014",
                          db="crawl",
                          charset="utf8")
        self.cursor = self.conn.cursor()

        self._cf = cf
        self._reader = sinaio.Reader()
        self._writer = sinaio.Writer()
        self._crawled_keys = {}
        self._timestamp_before_30_day = time.time() - 24*3600*30
        # 每页抓取微博数量 
        self._weibo_number = 5
        self.prepare(crawled_avatar_conf, crawled_img_conf, account_index)

    def __del__(self):
        self.conn.close()

    def prepare(self, crawled_avatar_conf, crawled_img_conf, account_index):
        log.logging.info("prepare - come in ")
        self._spider_work_count=self._cf.get("weibo","SPIDER_WORK_COUNT")
        self._parse_work_count=self._cf.get("weibo","PARSE_WORK_COUNT")
        #读取种子用户和已爬取用户
        self._user_file = self._cf.get("weibo", "BASE") + self._cf.get("weibo", "USERS_FILE")
        log.logging.info("user file %s" % self._user_file)
        self._user_array = self._reader.read_array(self._user_file)
        self._agent_file = self._cf.get("weibo", "BASE") + self._cf.get("weibo", "AGENTS_FILE")
        self._agent_dict = self._reader.read_dict_col1(self._agent_file)
        self._proxy_file = self._cf.get("weibo", "BASE") + self._cf.get("weibo", "PROXY_FILE")
        self._proxy_dict = self._reader.read_dict_col1(self._proxy_file)
        self._account_file = self._cf.get("weibo","BASE") + self._cf.get("weibo","ACCOUNT_FILE")
        self._account_dict = self._reader.read_dict_col1(self._account_file)
        self._crawled_user_file = self._cf.get("weibo", "BASE") + self._cf.get("weibo", "CRAWLED_USERS_FILE")
        #self._crawled_dict = self._reader.read_dict(self._crawled_user_file)
        #self._cookie_str = self._cf.get("weibo", "COOKIE_STR")
        self._crawled_dict = {}
        log.logging.info("user_array size = %d \taccount_dict size = %d" % (len(self._user_array), len(self._account_dict)))
        #读取结果保存路径
        self._avatar_dir = self._cf.get("weibo", "BASE") + self._cf.get("weibo", "AVATAR_DIR")
        self._mkdir_p(self._avatar_dir)
        self._imgs_dir = self._cf.get("weibo", "BASE") + self._cf.get("weibo", "IMGS_DIR")
        self._mkdir_p(self._imgs_dir)
        self._users_dir = self._cf.get("weibo", "BASE") + self._cf.get("weibo", "USERS_DIR")
        self._mkdir_p(self._users_dir)
        self._imgdes_dir = self._cf.get("weibo", "BASE") + self._cf.get("weibo", "IMGDES_DIR")
        self._mkdir_p(self._imgdes_dir)
        self._html_dir = self._cf.get("weibo","BASE") + self._cf.get("weibo","HTML_DIR")
        self._mkdir_p(self._html_dir)
        #读取已经爬取的用户头像和图片的签名
        self._crawled_keys = self._reader.read_dict_col2(crawled_img_conf)
        self._crawled_avatar_keys = self._reader.read_dict_col2(crawled_avatar_conf)
        
        self._content_encoding= self._cf.get("weibo","CONTENT_ENCODING")
        self._crawled_html_queue = Queue.Queue(maxsize = 30000)
        self._user_agent = None
        self._compute = 0
        self._use_proxy = False
        self._is_init_running = False
        #获得微博登录账号
        #self._weibo_account = self._cf.get("weibo", "WEIBO_ACCOUNT")
        #self._weibo_password = self._cf.get("weibo", "WEIBO_PASSWORD")
        #刷新代理ip库
        #self._reflush_proxy_host_666(10)
        #self._reflush_proxy_host_xici(10)
        
        
        #初始化http代理并且登录微博
        #self._reflush_proxy_host_kuaidaili(10)
        self._loginSina(self._use_proxy, account_index)

    def run(self):
        #self.work();
        self.follow_user()

    def follow_user(self):
        # 生成登录用户
        # 已经在__init__登录了

        # 生成操作动作
        post_data = {
                'uid'   : 3623353053,
                'objectid' : '',
                'f'     : 1,
                'extra' : '',
                'refer_sort'    : '',
                'refer_flag'    : '',
                'location'      : 'page_100406_home',   # page_100505_follow
                'oid'   : 3623353053,
                'wforce'    : 1,
                'nogroup'   : 'false',
                'fnick' : 'TFBOYS-易烊千玺',
                '_t'    : 0,
        }

        now_time = str(time.time()).replace(".", "")
        req_url = 'http://weibo.com/aj/f/followed?ajwvr=6&__rnd=' + now_time

        json_info = self.getHtmlSource(req_url, '', '', False, post_data)
        log.logging.info(json_info)
                
    def work(self):
        #
        k = 0
        self._work_running = True
        #pool = threadpool.ThreadPool(int(self._spider_work_count))
        
        log.logging.info("user_array size = %d" % (len(self._user_array)))
        while 1:
            user = random.choice(self._user_array)
            self.target_url = user
            #拿到用户id
            uid = self._get_weibo_uid(user)
            if not uid:
                log.logging.error("work - uid is False, will be continue ")
                continue
            #if uid in self._crawled_dict:
                #log.logging.info("work - uid %s already crawed, will be continue " % (uid))
            #    continue
            #self._crawled_dict[uid] = 1
            
            #使用多线程执行telnet函数  
            paras=[]
            paras.append({'user':user,'uid':uid})
            if not self._work_thread(paras[0]) :
                break
            #requests = threadpool.makeRequests(self._work_thread, paras, self._work_thread_end)  
            #[pool.putRequest(req) for req in requests]
            k = k+1
            lucky_number = random.randint(0, 100)
            if lucky_number == 66:
                log.logging.info("Times up, I'm sleeping 60 mins...") 
                time.sleep(3600)
                need_relogin = random.randint(0, 2)
                if need_relogin == 1:
                    self._loginSina(self._use_proxy, 1)
            c_time = time.localtime()
            if c_time[3] >= 1 and c_time[3] <= 5:
                log.logging.info("It's in the night, I need rest...")
                time.sleep(60)
            
            #if k % 100 == 0:
            #    log.logging.info("foreach spider queue complete, threadPool.size %s"%str(k))
                #pool.wait()
        #等待队列执行完成    
        #pool.wait()
        print '++++++++++++++++++++++++++++++++'
        log.logging.info("foreach spider queue suspend, threadPool.size %s"%str(k))
       # try:
            #thread.start_new_thread(self._start_parse_pool)
       #     self._start_parse_pool()
       #     log.logging.info("_start_parse_pool success ...")
       # except:
       #     print "Error: unable to start thread"
            
       # self._work_running = False       
       # log.logging.info("work - end !!!!!!!!!!!!!!!!")

    def _work_thread(self, paras):
        user=paras.get('user')
        uid=paras.get('uid')
        self._work_running = True
        sleep_time = random.uniform(0, 5)
        time.sleep(sleep_time) 
        if not user :
            return False
        #if (self._compute >0 and self._compute % 200) == 0:
        #    self._loginSina(self._use_proxy)
        try:
            nowTime = str(time.time()).replace(".", "")
            page = 1
            host = "http://m.weibo.cn/u/%s?" % uid
            _page_info = {}
            #url = "%s?is_search=0&visible=0&is_tag=0&profile_ftype=1&page=%s" % (user,page)
            userIndexUrl = "http://m.weibo.cn/u/%s?_=%s" % (uid, nowTime)
            #html = self._crawl_weibo(host, url = userIndexUrl)
            html = self.getHtmlSource(userIndexUrl, uid, "gsid", refUrl=False) 
            log.logging.debug(html)
            if not html:
                log.logging.info("work - html is False , will break ... ")
                return False
            stageId =False
            _user_info = self._parse_user_index(html)
            if _user_info :
                _page_info.update(_user_info)
                stageId = _user_info['stageId']
            if not stageId :
                log.logging.info("work - stageId is False , will break ... ")
                return False
            maxpage = 2
            while page < maxpage :
                userFeedListUrl = "http://m.weibo.cn/page/json?containerid=%s_-_WEIBO_SECOND_PROFILE_WEIBO&page=%d"%(stageId,page)
                host = 'http://m.weibo.cn/page/tpl?containerid='+stageId+'_-_WEIBO_SECOND_PROFILE_WEIBO&itemid=&title=%E5%85%A8%E9%83%A8%E5%BE%AE%E5%8D%9A'
                #html = self._crawl_weibo(host, url=userFeedListUrl)
                html = self.getHtmlSource(userFeedListUrl, uid, "gsid", refUrl=host)
                #html = self.getAjaxmsg(userFeedListUrl, host)
                if html :
                    _tmp_dic = json.loads(html,encoding="UTF-8")
                    #_page_info['ok'] = _tmp_dic['ok']
                    #_page_info['count'] = _tmp_dic['count']
                    errno = _tmp_dic.get("errno")
                    msg = _tmp_dic.get("msg")
                    _page_info['cards'] = _tmp_dic.get('cards',None)
                    if errno or msg or not _page_info['cards']:
                        #log.logging.info(html)
                        maxpage = maxpage +1;
                        log.logging.error("work - getUserFeedList error ,weibo_account :%s,errno :%s,  msg :%s"%(self._weibo_account,errno,msg))
                       # if maxpage >2 :
                            #self._loginSina(self._use_proxy)
                       #     return False
                       # else :
                       #     time.sleep(sleep_time)
                       #     continue
                    else:
                        log.logging.info("work - right url and content")
                        self._parse_webo_info(_page_info)
                #_html = json.dumps(_page_info)
                
                #_key = str(uid)+"_"+str(page)
                #self._writer.write_html(_html, self._html_dir+"/"+_key)
                #log.logging.info("work - write html complate, index :"+str(self._compute))
                #self._crawled_html_queue.put(_key) 
                
                page = page +1
                time.sleep(5)
        except Exception as e :
            log.logging.error("work - error msg %s"%(e))
            
        return True
            
    def _parse_webo_info(self, page_info):
        cards = page_info['cards']
        card_group = cards[0]['card_group']
        for i in range(0, self._weibo_number):
            card = card_group[i]
            text = card['mblog']['text']
            user = card['mblog']['user']['screen_name']
            timestamp = card['mblog']['created_timestamp']
            #log.logging.info("Done weibo parser! webo text:%s user:%s timestamp:%s" % (text, user, timestamp))

            sql_str = "INSERT IGNORE INTO `weibos` (`sname`, `content`, `time`, `url`) VALUES"
            sql_str = "%s (\"%s\", \"%s\", %s, \"%s\")," % (sql_str,
                                                            MySQLdb.escape_string(user),
                                                            MySQLdb.escape_string(text),
                                                            timestamp,
                                                            self.target_url)

            if not ("INSERT IGNORE INTO `weibos` (`sname`, `content`, `time`, `url`) VALUES" == sql_str):
                sql_str = sql_str.strip(',')
                #log.logging.info("Sql: %s" % sql_str)
                self.cursor.execute(sql_str)
        self.conn.commit()

    def _parse_user_index(self,html):
        _user_info={}
        try:
            match = re.match('^.*?window\.\$config=(.*?)\;',html)
            if match :
                respCmtJson = match.group(1)
                respCmtJson = self._pre_cac_json(respCmtJson)
                _dict_tmp = json.loads(respCmtJson);
                _user_info['stageId']=_dict_tmp['stageId']
            match = re.match(r'.*?window\.\$render_data =(.*?)\;', html)
            if match :
                respCmtJson = match.group(1)
                respCmtJson = self._pre_cac_json(respCmtJson)
                #print respCmtJson
                _dict_tmp = json.loads(respCmtJson);
                _user_info['stage'] = _dict_tmp['stage']
                _user_info['common'] = _dict_tmp['common']
        except Exception as e :
            log.logging.error("work - error msg %s"%(e))
        return _user_info
    
    def _start_parse_pool(self):
        k=0 
        parse_pool = threadpool.ThreadPool(int(self._parse_work_count))
        if self._crawled_html_queue.empty() :
            self._crawled_html_queue = self._reader.read_listdir(self._html_dir)
        print self._crawled_html_queue.qsize()
        while not self._crawled_html_queue.empty():
            _key = self._crawled_html_queue.get();
            arr=_key.split('_')
            uid = arr[0]
            
            paras=[]
            paras.append({'uid':uid,'_key':_key})
            requests = threadpool.makeRequests(self._parse_thread, paras)  
            [parse_pool.putRequest(req) for req in requests]
            k = k+1
        #等待队列执行完成    
        log.logging.info("foreach parse queue complete, threadPool.size %s"%str(k))
        parse_pool.wait()
        log.logging.info("parse queue complete !")
    
    def _parse_thread(self,paras):
        uid=paras.get('uid')
        _key = paras.get('_key')
        user_info = []
        img_info = []
        user_num = 0
        new_user_dict = {}
        try:
            _html =self._reader.read_html(self._html_dir+"/"+_key)
            if not _html or len(_html.strip()) <=0 :
                return False
            
            _page_info = json.loads(_html, encoding="UTF-8")
            (user_name,gender,loc_text,avatar_url,nums) = self._parse_weibo_user(_stage = _page_info['stage'])
            if not user_name or user_name.strip() == "" :
                return False
            
            need_add_user = 0
            faxian_user_id = -1
            avatar_md5 = self._calc_md5("avatar_" + uid);
            # download用户头像并保存
            if avatar_md5 not in self._crawled_avatar_keys:
                need_add_user = 1
                dest_file = os.path.join(self._avatar_dir, uid + "_avatar.jpg")
                res = urllib.urlretrieve(avatar_url, filename=dest_file)
                if not res :
                    return False
                #pic_data = self._crawl_weibo(avatar_host, avatar_url)
                #if not pic_data:
                #    return False
                #self._write_file(self._avatar_dir, uid + "_avatar.jpg", pic_data)
            else:
                faxian_user_id = self._crawled_avatar_keys[avatar_md5]
                
            
            info_list = [uid, user_name, gender, self._format_str(loc_text)]
            info_list.extend(nums)
            info_list.append(uid + "_avatar.jpg")
            info_list.append(avatar_md5)
            info_list.append(faxian_user_id)
            info_list.append(need_add_user)
            
            _cards = _page_info['cards']
            _card = _cards[0]
            
            self._parse_weibo_cardgroup(uid,_cardgroup=_card['card_group'],img_info=img_info)
            
            # 有有效的图片信息才增添用户信息
            user_info.append(info_list)
            user_num += 1
            #sleep_time = random.uniform(0, 3)
            #log.logging.info("user sleeping %f" % sleep_time)
            #time.sleep(sleep_time)
            
            #保存图片信息
            self._dump_dict("%s/img_info" % (self._imgdes_dir), img_info)        
            log.logging.info("parse - save imgdes complate")
            #保存用户信息
            self._dump_dict("%s/user_info" % (self._users_dir), user_info)
            log.logging.info("parse - save user_info complate")
            
            os.rename(self._html_dir+"/"+_key,self._html_dir+"/"+_key+"_done")
        except Exception as e:
            log.logging.error("parse - error msg %s"%(e))
            
    def _parse_weibo_user(self, _stage={}):
        res = ('','','','',[])
        if not _stage :
            return res
        
        _page = _stage["page"]
        if _page and len(_page) >1 :
            _user_info = _page[1]
            user_name =_user_info['name']
            gender = _user_info['ta']
            loc_text = _user_info['nativePlace']
            avatar_url = _user_info['profile_image_url']     
            #照片, 标签, 关注, 粉丝
            nums = [_user_info['mblogNum'],0,_user_info['attNum'],_user_info['fansNum']]
            return (user_name,gender,loc_text,avatar_url,nums)
        return res
    
    def _parse_weibo_cardgroup(self, uid, _cardgroup, img_info):
        
        # 获取用户的图片
        #pic_host = "ww2.sinaimg.cn"
        img_dir = self._imgs_dir + "/"+ str(uid)  
        self._mkdir_p(img_dir)
        for item in _cardgroup :
            _blog = item.get('mblog',None)
            if not _blog :
                continue
            _pics = _blog.get('pics',None)
            if not _pics :
                continue
            _text = _blog.get('text',None)
            _ct = _blog.get('created_timestamp',None)
	    if int(_ct) < self._timestamp_before_30_day:
                continue
            _push_time = datetime.fromtimestamp(_ct)
            img_num = 0
            for pic_item in _pics :
                if img_num >10 :
                    break
                try:
                    pic_url = pic_item.get('url','')
                    value = self._prepare_calc_img(pic_url)
                    if not value or len(value) < 2:
                        continue
                    img_id = pic_item.get('pid',None)
                    key_buf = str(img_id) + str(uid) + str(pic_url)
                    md5_sign = self._calc_md5(key_buf)
                    # 已经爬取过
                    if md5_sign in self._crawled_keys:
                        log.logging.info("img_id[%s] uid[%s] sign[%s] do not crawled repeatly" % (img_id, uid, md5_sign))
                        continue
                    pic_url = "http://"+value[0]+"/bmiddle/"+value[2]+".jpg"
                    
                    #download图片文件并保存
                    try:
                        log.logging.info("pic[%d] %s " % (img_num, pic_url))
                        dest_file = os.path.join(img_dir, uid +"_" + img_id + ".jpg")
                        res = urllib.urlretrieve(pic_url, filename=dest_file)
                        if not res :
                            continue
                        #pic_data = self._crawl_weibo(pic_host, pic_url)
                        #if not pic_data:
                        #    continue
                        #self._write_file(img_dir, uid +"_" + img_id + ".jpg", pic_data)
                        
                        log.logging.info("write down pic : " + uid+"_"+img_id+".jpg")
                    except Exception as e1 :
                        log.logging.error("for down img error , msg %s"%(e1))
                        sleep_time = random.uniform(0, 3)
                        time.sleep(sleep_time)
                        continue
                    
                    img_num += 1
                    img_info.append([img_id,uid,self._format_str(_text),-1,-1,_ct,pic_url,md5_sign])
                except Exception as e:
                    log.logging.error("for img_dict error , msg %s"%(e))
            
    def _work_thread_end(self, request, n):
        log.logging.info('%s - %s' % (request.requestID, n))#这里的requestID只是显示下，没实际意义
        self._compute = self._compute +1
        '''
        if self._compute % 500 ==0 :
            #刷新代理ip库
            self._reflush_proxy_host_666(10)
            self._loginSina(self._use_proxy)
        '''
    def _crawl_weibo(self, host, url):
        index=0
        count=6
        data = False
        while index < count :
            try:
                data = self._download(host, url)
                #result = urllib2.urlopen(url)
                #data = result.read()
                #for item in self.cookie:
                #    log.logging.debug('Name = %s , Value = %s'%(item.name,item.value))
                if not data :
                    index = index +1
                    log.logging.error("_crawl_weibo failed , index %s , url %s , data %s"%(str(index),url,data))
                    if index < count :
                        time.sleep(1)
                        continue
                    elif index%3 == 0 :
                        #刷新代理ip库
                        #self._reflush_proxy_host_666(10)
                        self._reflush_proxy_host_kuaidaili(10)
                        self._loginSina(self._use_proxy)
                        continue
                    else:
                        break
                else :
                    break
            except Exception as e:
                index = index +1
                log.logging.error("_crawl_weibo error , index %s , url %s , msg %s"%(str(index),url,e))
                if index < count :
                    time.sleep(1)
                    continue
                elif index%3 == 0 :
                    #刷新代理ip库
                    #self._reflush_proxy_host_666(100)
                    self._reflush_proxy_host_kuaidaili(10)
                    self._loginSina(self._use_proxy)
                    continue
                else:
                    break
        return data 
        
    def finish(self):
        #保存用户爬取情况
        self._writer.write_dict_keys(self._crawled_dict, self._crawled_user_file)
        #self._writer.write_queue(self._user_queue, self._user_file)
    def _reflush_proxy_host_kuaidaili(self,num=10):
        url = 'http://svip.kuaidaili.com/api/getproxy/?orderid=934607935005830&num=10&area=%E4%B8%AD%E5%9B%BD&browser=2&protocol=1&method=1&an_ha=1&sp1=1&sp2=1&quality=2&sort=0&dedup=1&format=text&sep=1'
        data = getHtmlSource(url)
        if data :
            self._writer.write_text(data, self._proxy_file)
        self._proxy_dict = self._reader.read_dict_col1(self._proxy_file)
    def _reflush_proxy_host_666(self,num=100):
        url = 'http://vxer.daili666api.com/ip/?tid=557982535725675&num=%d&delay=1&sortby=time&foreign=none&filter=on'%num
        data = getHtmlSource(url)
        if data :
            self._writer.write_text(data, self._proxy_file)
        self._proxy_dict = self._reader.read_dict_col1(self._proxy_file)
            
    def _reflush_proxy_host_xici(self,page=2):
        headers = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                   'Accept-Encoding':'gzip, deflate, sdch',
                   'Accept-Language':'zh-CN,zh;q=0.8',
                   'Cache-Control':'max-age=0',
                   'Connection':'keep-alive',
                   'Cookie':'_free_proxy_session=BAh7B0kiD3Nlc3Npb25faWQGOgZFVEkiJTdlYjZjZDljYTM1OTdlYjU4Mzg5YjI3ZTg1NDlkYzJkBjsAVEkiEF9jc3JmX3Rva2VuBjsARkkiMWpsaytFME41dGJnZjRUVmdKWVlqeUJvL25JZ3Q2MjU5RWZ5Y05XSzBNRDg9BjsARg%3D%3D--a406cf90c305ce102f52b025854f02c9c1ac0a62; CNZZDATA4793016=cnzz_eid%3D1825853456-1445304796-%26ntime%3D1445389263',
                   'Host':'www.xicidaili.com',
                   'RA-Sid':'3A875414-20150413-034229-d8c855-4b3a23',
                   'RA-Ver':'3.0.7',
                   'Upgrade-Insecure-Requests':'1',
                   'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36',
                  }
        try:
            hosts = {}
            #for i in range(1,page):
            #    url = "http://www.xicidaili.com/nn/%d"%(i)
            url = "http://www.xicidaili.com/"
            data = getHtmlSource(url=url,headers=headers)
            if data :
                index = 0
                html_doc = BeautifulSoup(data, from_encoding='utf-8')
                table_doc = html_doc.find("table", attrs={"id" : "ip_list"})
                for tr_item in table_doc.findAll("tr"):
                    #print tr_item
                    td_item = tr_item.findAll("td")
                    if not td_item :
                        continue
                    ip=td_item[1].get_text();
                    port=td_item[2].get_text();
                    if ip and port :
                        hosts[ip+":"+port] = 1
                        index = index +1
                    if index >=20 :
                        break 
            self._writer.write_dict_keys(hosts, self._proxy_file)
            self._proxy_dict = self._reader.read_dict_col1(self._proxy_file)
        except Exception as e:
            log.logging.error(e)
    def _reflush_proxy_host_kuaidaili_norml(self,page=10):
        headers = {'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                   'Accept-Encoding':'gzip, deflate, sdch',
                   'Accept-Language':'zh-CN,zh;q=0.8',
                   'Cache-Control':'max-age=0',
                   'Connection':'keep-alive',
                   'Cookie':'Hm_lvt_7ed65b1cc4b810e9fd37959c9bb51b31=1444896526,1445410618; Hm_lpvt_7ed65b1cc4b810e9fd37959c9bb51b31=1445410630',
                   'Host':'www.kuaidaili.com',
                   'RA-Sid':'3A875414-20150413-034229-d8c855-4b3a23',
                   'RA-Ver':'3.0.7',
                   'Upgrade-Insecure-Requests':'1',
                   'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/45.0.2454.101 Safari/537.36',
                  }
        try:
            hosts = {}
            for i in range(1,page):
                url = "http://www.kuaidaili.com/proxylist/%d/"%i
                data = getHtmlSource(url=url,headers=headers)
                if data :
                    html_doc = BeautifulSoup(data, from_encoding='utf-8')
                    div_doc = html_doc.find("div",attrs={"id":"list"})
                    table_doc = div_doc.findAll("table")[0]
                    for tr_item in table_doc.findAll("tr"):
                        #print tr_item
                        td_item = tr_item.findAll("td")
                        if not td_item :
                            continue
                        ip=td_item[0].get_text();
                        port=td_item[1].get_text();
                        if ip and port :
                            hosts[ip+":"+port] = 1
            self._writer.write_dict_keys(hosts, self._proxy_file)
            self._proxy_dict = self._reader.read_dict_col1(self._proxy_file)
        except Exception as e:
            log.logging.error(e)
                    
    def _get_weibo_uid(self,user):
        arr = user.split(',')
        #print arr[6]
        url = arr[0]
        match = re.search(r'^.*\/(\d+)$', url)
        if not match :
            return False
        uid = match.group(1)
        if not uid or uid == "":
            return False
        return uid
    def _prepare_calc_html(self,html):
        p = re.compile(r'<script>FM.view\((.*?)\)\;?</script>')
        _list = p.findall(html)
        return _list
    def _prepare_calc_img(self,pic_url):
        p = re.compile(r'http://(.*?)/(.*?)/(.*?).jpg')
        m = p.findall(pic_url)
        if m and len(m) >0:
            return m[0]
        else :
            return False
    def _calc_md5(self, key_buf):
        #key_buf = str(img_id) + str(uid) + str(pic_url)
        m = hashlib.md5()
        m.update(key_buf)
        return m.hexdigest()
    def _format_str(self,data):
        return ''.join(data.split())
    def _format_date(self,datestr):
        return time.mktime(time.strptime(datestr,'%Y-%m-%d %H:%M'))
    def _calc_num(self,data):
        p = re.compile(r'\d+')
        for item in p.finditer(data) :
            return int(item.group())
    def _loginSina(self, isProxy, account_index):
        if self._is_init_running :
            return False
        self._is_init_running = True
        index=0
        #_login = login.sina_login()
        _curr_dir = os.path.split(os.path.realpath(__file__))[0]
        self.sina = LoginSinaCom(soft_path=_curr_dir)
        count=6
        i=int(random.uniform(0, len(self._account_dict)))
        #i = account_index
        account = self._account_dict[i]
        #获得微博登录账号
        self._weibo_account = account[:account.find(':')]
        self._weibo_password = account[account.find(':') + 1:]
        while index < count :
            try:
                # set http proxy
                if isProxy :
                    i=int(random.uniform(0, len(self._proxy_dict)))
                    self._proxy_url = self._proxy_dict.get(i)
                    log.logging.error("loginSina - account :%s, proxy_url :%s"%(self._weibo_account, self._proxy_url))
                    #self._init_proxy({"http":self._proxy_url})
                    self.sina = LoginSinaCom(soft_path=_curr_dir,proxyip=self._proxy_url)
                
                # 登录微博 
                res = self.sina.login(self._weibo_account,self._weibo_password)#res = self.sina.check_cookie(self._weibo_account,self._weibo_password, _curr_dir)
                if not res :
                    index = index +1
                    log.logging.error("loginSina - res is %s , index %s , it will be continue"%(str(res),str(index)))
                    if index == count :
                        os._exit()  
                        break
                    else:
                        continue
                else :
                    n=int(random.uniform(0, len(self._agent_dict)))
                    self._user_agent = self._agent_dict.get(n,'Mozilla/5.0 (iPhone; CPU iPhone OS 8_0 like Mac OS X) AppleWebKit/600.1.3 (KHTML, like Gecko) Version/8.0 Mobile/12A4345d Safari/600.1.4')
                    self._is_init_running = False
                    break
            except Exception as e:
                index = index +1
                log.logging.error("loginSina error , index %s ,  msg %s"%(str(index), e))
                if index < count :
                    time.sleep(1)
                    continue
                else:
                    os._exit(-1)
                    break
        return True     
    
    def getHtmlSource(self, url, userid, gsid, refUrl, data = {}):
        content = ""
        for i in range(3): #@UnusedVariable
            proxyip = False
            if self._use_proxy :
                proxyip = self._proxy_url
                #self.sina.proxyip = random.choice(self._proxy_dict)
            try:
                if not url.startswith("http://"):
                    url = "http://"+url
                headers = {
                           'Accept': '*/*',
                           'Accept-Encoding': 'gzip, deflate',
                           'Accept-Language': 'zh-CN,zh;q=0.8',
                           'Cache-Control':'no-cache',
                           'Connection': 'keep-alive',
                           'Content-Type':'application/x-www-form-urlencoded',
                           'Cookie' : 'SINAGLOBAL=4694760597776.621.1450409596140; wvr=6; pf_feednav_bub_hot_2793429614=1; _s_tentry=developer.51cto.com; YF-Ugrow-G0=ad06784f6deda07eea88e095402e4243; login_sid_t=2869eaf3adaa311b9e6b58ac621a4221; Apache=4022889269981.533.1450691658357; ULV=1450691658375:7:7:1:4022889269981.533.1450691658357:1450525348581; SUS=SID-2793429614-1450691685-GZ-iwux1-e82b6c1c11bd6898e2e62eedd2391a5f; SUE=es%3D53ad08b38a3da0f7871ea1e5961c6e86%26ev%3Dv1%26es2%3D4fba71a8a2edf03e72f0eafd601a9b19%26rs0%3DcRaiLgJdpXZDw9TRz%252BjqBgsBWlcVkQA9dSmeJN42Vjs5lZrWjOwWfltZeMW5ET%252FCLOeDhO679Cm2l7myjXsX542HAdl3UB33SFV93WXYEbZC%252BUY8cex8dlirUFvZdd4IQq0hbzDpjZWFWoy%252Byxk%252FHbiduMZCdldYMT2YyZyl0jE%253D%26rv%3D0; SUP=cv%3D1%26bt%3D1450691685%26et%3D1450778085%26d%3Dc909%26i%3D1a5f%26us%3D1%26vf%3D0%26vt%3D0%26ac%3D0%26st%3D0%26uid%3D2793429614%26name%3Dwal_ice%2540163.com%26nick%3Dwal_ice_%26fmp%3D%26lcp%3D2015-12-19%252019%253A10%253A09; SUB=_2A257c7w1DeTxGeRJ4lEV8ifKyjiIHXVYCKr9rDV8PUNbuNBeLXffkW9jReXZARLuCZOp5b1TZG89zbtPKg..; SUBP=0033WrSXqPxfM725Ws9jqgMF55529P9D9WFDONNY2-mL3Z.RmT6vj5_g5JpX5K2t; SUHB=0wnkPZqAw44M0f; ALF=1482227685; SSOLoginState=1450691685; un=wal_ice@163.com; YF-V5-G0=46bd339a785d24c3e8d7cfb275d14258; YF-Page-G0=f017d20b1081f0a1606831bba19e407b; UOR=sports.ifeng.com,widget.weibo.com,news.ifeng.com; pf_feednav_bub_all_2793429614=1; TC-Page-G0=6fdca7ba258605061f331acb73120318; TC-V5-G0=26e4f9c4bdd0eb9b061c93cca7474bf2',
                           'Host': 'weibo.com',
                           'Origin':'http://weibo.com',
                           'Pragma' : 'no-cache',
                           'Referer':'http://weibo.com/tfyiyangqianxi',
                           'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/46.0.2490.80 Safari/537.36',
                           'X-Requested-With': 'XMLHttpRequest',
                           }
                if refUrl:
                    headers['Referer'] = refUrl
                if 'json' in url :
                    headers['Accept'] = 'application/json, text/javascript, */*; q=0.01';
                    content = self.sina.get_content_head(url, headers, data=None)
                else :
                    #headers['Accept'] = 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8';
                    content = getHtmlSource(url, headers=headers, proxyip=proxyip, data = data)
                    
                #headers['Cookie'] = 'gsid_CTandWM=' + gsid + '; _WEIBO_UID='+userid
                if "登录" in content and "密码" in content and "注册" in content :
                    content = ""
                elif "微博精选" in content and "热门转发" in content:
                    content = ""
                elif "抱歉，你的帐号存在异常，暂时无法访问" in content and "解除访问限制" in content:
                    content = ""
                #time.sleep(0.2*random.randint(1, 10))
            except Exception:
                s=sys.exc_info()
                msg = (u"get html Error %s happened on line %d" % (s[1],s[2].tb_lineno))
                log.logging.error(msg)
                content = ""
            if content != "":
                break
        return content
    #获取AJAX加载消息HTML
    def getAjaxmsg(self, url, refUrl):
        '''
        headers = {"Host":"m.weibo.cn",
                   "User-Agent":"Mozilla/5.0 (Windows NT 6.1; rv:13.0) Gecko/20100101 Firefox/13.0.1",
                   "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                   "Accept-Language":"zh-cn,zh;q=0.8,en-us;q=0.5,en;q=0.3",
                   "Accept-Encoding":"gzip, deflate",
                   "Connection":"keep-alive",
                   "Content-Type":"application/x-www-form-urlencoded",
                   "X-Requested-With":"XMLHttpRequest",
                   "Referer":refUrl,
                   }
        '''
        headers = {'Host': 'm.weibo.cn',
                   'User-Agent': 'android',
                   'Accept': '*/*',
                   'Connection': 'keep-alive',
                   'Accept-encoding': 'gzip, deflate',
                   'Accept-Language': 'zh-cn,zh;q=0.8,en-us;q=0.5,en;q=0.3',
                   'X-Requested-With': 'XMLHttpRequest',
                   "Referer":refUrl,
                   }
        html = ''
        for i in range(3): #@UnusedVariable
            try:
                #print url
                html = self.sina.get_content_head(url, headers=headers)
            except Exception as e:
                log.logging.error("getAjaxmsg error , msg %s"%e)
                continue
            if html:
                break
        return html
    
    def _download(self, host, url):
        '''单纯的下载给定url的内容
           @return 页面内容
                        print i.a.get('href')
        '''
        #index=int(random.uniform(0, len(self._agent_dict)))
        try:
            '''
            headers = {
                    "Accept":"text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                    "Accept-Encoding":"gzip, deflate, sdch",
                    "Accept-Language":"zh-CN,zh;q=0.8",
                    "Cache-Control":"max-age=0",
                    "Connection":"keep-alive",
                    #"Cookie":'gsid_CTandWM=gsid; _WEIBO_UID='+self._user_info['uid'],
                    "Cookie":self.cookieStr,
                    "Host":host,
                    "RA-Sid":"3A875414-20150413-034229-d8c855-4b3a"+str(index),
                    "RA-Ver":"3.0.7",
                    "Upgrade-Insecure-Requests":"1",
                    "User-Agent":self._agent_dict.get(index,"Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.107 Safari/537.36")
            }
            '''
            
            headers = {'Host': host,
                   'User-Agent': self._user_agent,
                   'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                   'Accept-encoding': 'gzip, deflate',
                   'Accept-Language': 'zh-cn,zh;q=0.8,en-us;q=0.5,en;q=0.3',
                   'Connection': 'keep-alive',
                  }
            return self.sina.get_content_head(url, headers)
            '''
            headers = {'Host': 'm.weibo.cn',
                       'User-Agent': 'android',
                       'Accept': '*/*',
                       'Connection': 'keep-alive',
                       'Accept-encoding': 'gzip, deflate',
                       'Accept-Language': 'zh-cn,zh;q=0.8,en-us;q=0.5,en;q=0.3',
                       'X-Requested-With': 'XMLHttpRequest',
                       'Referer':"http://m.weibo.cn/u/%s?" % self._user_info['uid']
                       }
            '''
            '''
            if self._use_proxy :
                return weiborequest.getHtmlSource(url=url,headers=headers,proxyip=self._proxy_url)
            else :
                return weiborequest.getHtmlSource(url=url,headers=headers)
            '''
            '''
            request = urllib2.Request(url=url, headers=headers)
            fp = urllib2.urlopen(request, timeout=10)
                
            if fp.info().get('Content-Encoding') == 'gzip':
                buf = StringIO( fp.read())
                f = gzip.GzipFile(fileobj=buf)
                data = f.read().encode('utf-8')
            else:
                data = fp.read()
            fp.close()
            return data
            '''
        except Exception, e:
            log.logging.error("_download error , url %s , msg %s"%(url,e))
            return None
    def _pre_cac_json (self, respCmtJson):
        respCmtJson = re.sub(r"(,?)(\w+?)\s+?:", r"\1'\2' :", respCmtJson);
        respCmtJson = respCmtJson.replace("'", "\"");
        return respCmtJson
    
    def _dump_dict(self, output_file, info_dict):
        with open(output_file, "a") as fp_out:
            for item in info_dict:
                fp_out.write('\t'.join(str(i) for i in item) + '\n')
    
    def _get_html_tag(self, html_doc, tag_name, attrs_key, attrs_value):
        return html_doc.find(tag_name, attrs={attrs_key : attrs_value}).get_text()
    
    def _write_file(self,filepath, filename, data):
        try:
            #path = os.path.dirname(os.path.abspath(__file__))
            #config_path = os.path.join(path, 'config')
            config_file = os.path.join(filepath, filename)
            fw = open(config_file, 'w')
            fw.write(data)
            fw.flush()
            os.fsync(fw)
            fw.close()
        except Exception, e:
            log.logging.error("_write_file error , filename %s , msg %s"%(filename,e))
    def _mkdir_p(self, path):
        try:
            os.makedirs(path,0777)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(path):
                log.logging.info(path + "exists")   
 
