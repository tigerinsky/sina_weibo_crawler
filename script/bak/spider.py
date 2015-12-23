#!/user/bin/env python
#coding: utf-8

'''
Created on 2015年8月18日

@author: liuweise
'''

import os
import traceback
import errno
import sys
import json
import urllib2
import time
import random
from StringIO import StringIO
import gzip
import re
import Queue
import ConfigParser
import hashlib
import log
import sinaio
import login
import re
from bs4 import BeautifulSoup
from time import sleep
import threadpool
import cookielib
from loginsinacom import LoginSinaCom
import weiborequest

reload(sys)
sys.setdefaultencoding('utf8')

class Spider(object):
    '''
    classdocs
    '''


    def __init__(self, cf):
        '''
        Constructor
        '''
        self._cf = cf
        self._reader = sinaio.Reader()
        self._writer = sinaio.Writer()
        self._crawled_keys = {}
    def prepare(self, crawled_avatar_conf, crawled_img_conf):
        log.logging.info("prepare - come in ")
        self._spider_work_count=self._cf.get("weibo","SPIDER_WORK_COUNT")
        self._parse_work_count=self._cf.get("weibo","PARSE_WORK_COUNT")
        #读取种子用户和已爬取用户
        self._user_file = self._cf.get("weibo", "BASE") + self._cf.get("weibo", "USERS_FILE")
        self._user_queue = self._reader.read_queue(self._user_file)
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
        log.logging.info("user_queue size = %d \taccount_dict size = %d" % (self._user_queue.qsize(), len(self._account_dict)))
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
        
        self._compute = 0
        self._use_proxy = True
        self._is_init_running = False
        #获得微博登录账号
        #self._weibo_account = self._cf.get("weibo", "WEIBO_ACCOUNT")
        #self._weibo_password = self._cf.get("weibo", "WEIBO_PASSWORD")
        #刷新代理ip库
        self._reflush_proxy_host_666(10)
        #初始化http代理并且登录微博
        self._init_proxy_and_dologin(self._use_proxy)
                
    def work(self, time_now):
        #
        k = 0
        pool = threadpool.ThreadPool(int(self._spider_work_count))
        log.logging.info("user_queue size = %d" % (self._user_queue.qsize()))
        while not self._user_queue.empty():
            log.logging.info("user_queue1111 size = %d" % (self._user_queue.qsize()))
            user = self._user_queue.get()
            #拿到用户id
            uid = self._get_weibo_uid(user)
            if not uid:
                log.logging.info("work - uid is False, will be continue ")
                continue
            if uid in self._crawled_dict:
                log.logging.info("work - uid %s already crawed, will be continue " % (uid))
                continue
            self._crawled_dict[uid] = 1
            
            #使用多线程执行telnet函数  
            paras=[]
            paras.append({'user':user,'uid':uid})
            requests = threadpool.makeRequests(self._work_thread, paras, self._work_thread_end)  
            [pool.putRequest(req) for req in requests]
            k = k+1
            
            if k % 1000 == 0:
                print '++++++++++++++++++++++++++++++++'
                log.logging.info("foreach spider queue suspend, threadPool.size %s"%str(k))
                pool.wait()
        #等待队列执行完成    
        log.logging.info("foreach spider queue complete, threadPool.size %s"%str(k))
        pool.wait()

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
               
        log.logging.info("work - end !!!!!!!!!!!!!!!!")
            
    def _work_thread(self, paras):
        user=paras.get('user')
        uid=paras.get('uid')
       
        sleep_time = random.uniform(0, 3)
        time.sleep(sleep_time) 
        if not user :
            return False
        try:
            page = 1
            host = "weibo.com"
            while page < 2 :
                url = "%s?is_search=0&visible=0&is_tag=0&profile_ftype=1&page=%s" % (user,page)
                html = self._crawl_weibo(host, url) 
                if not html:
                    log.logging.info("work - html is False , will break ... ")
                    break
                #html = str(html).decode(self._content_encoding)
                log.logging.info("work - uid %s , page %s , count %d" % (uid, str(page),self._compute))
                #log.logging.info("work - uid %s , page %s , html %s" % (uid, str(page), self._format_str(html)))
                if "404错误" in self._format_str(html) :
                    log.logging.error("work - found 404 error , while return !!!")
                    return False
                
                docs = self._prepare_calc_html(html)
                if not docs and len(docs) <=0 :
                    log.logging.info("work - docs is False or len(docs) is %d"%(len(docs)))
                    break
                _html = ""
                for doc_json in docs :
                    try:
                        doc_obj = json.loads(doc_json,"UTF-8")
                        html_doc = doc_obj.get('html',False) 
                        if not html_doc or html_doc.strip() == "" :
                            continue       
                        _html = _html + html_doc +"<br/>"                 
                    except Exception as e1:
                        log.logging.error("for docs error , json %s , msg %s"%(doc_json,e1))
                        
                
                #_html = ''.join(_html.split())
                log.logging.debug(''.join(_html.split()))
                
                _key = str(uid)+"_"+str(page)
                self._writer.write_html(_html, self._html_dir+"/"+_key)
                log.logging.info("work - write html complate")
                self._crawled_html_queue.put(_key) 
                
                page = page +1
        except Exception as e :
            log.logging.error("work - error msg %s"%(e))
            
    def _parse_thread(self,paras):
        uid=paras.get('uid')
        _key = paras.get('_key')
        user_info = []
        img_info = []
        user_num = 0
        new_user_dict = {}
        
        try:        
            _html =self._reader.read_html(self._html_dir+"/"+_key)
            if _html and len(_html.strip()) >0 :
                (user_name, gender, loc_text, avatar_url, nums, wb_info) = self._parse_weibo(_html)
                log.logging.info("parse - parse weibo complate, user_name %s " % (user_name))
                if not user_name or user_name.strip() == "" :
                    return False
                 
                avatar_md5 = self._calc_md5("avatar_" + uid);
                avatar_host = "tp2.sinaimg.cn"
                need_add_user = 0
                faxian_user_id = -1
                # download用户头像并保存
                if avatar_md5 not in self._crawled_avatar_keys:
                    need_add_user = 1
                    pic_data = self._crawl_weibo(avatar_host, avatar_url)
                    if not pic_data:
                        return False
                    self._write_file(self._avatar_dir, uid + "_avatar.jpg", pic_data)
                else:
                    faxian_user_id = self._crawled_avatar_keys[avatar_md5]
                
                info_list = [uid, user_name, gender, self._format_str(loc_text)]
                info_list.extend(nums)
                info_list.append(uid + "_avatar.jpg")
                info_list.append(avatar_md5)
                info_list.append(faxian_user_id)
                info_list.append(need_add_user)
                
                # 获取用户的图片
                img_dir = self._imgs_dir + "/"+ str(uid)  
                self._mkdir_p(img_dir)
                
                pic_host = "ww1.sinaimg.cn"
                if wb_info and len(wb_info) >0 :
                    for wb_item in wb_info :
                        self._save_user_img(pic_host, img_dir, uid, wb_item, img_info)
                        log.logging.info("parse - save user img complate, img_info's length %s " % (str(len(img_info))))
                
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
        
        except Exception as e :
            log.logging.error("parse - error msg %s"%(e))
            
    def _work_thread_end(self, request, n):
        log.logging.info('%s - %s' % (request.requestID, n))#这里的requestID只是显示下，没实际意义
        self._compute = self._compute +1
        if self._compute % 500 ==0 :
            #刷新代理ip库
            self._reflush_proxy_host_666(10)
            self._init_proxy_and_dologin(self._use_proxy)
        
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
                        self._reflush_proxy_host_666(10)
                        self._init_proxy_and_dologin(self._use_proxy)
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
                    self._reflush_proxy_host_666(100)
                    self._init_proxy_and_dologin(self._use_proxy)
                    continue
                else:
                    break
        return data 
    def _save_user_img(self,host,img_dir,uid,wb_item, img_info):
        #print wb_item.get("text")
        #print wb_item.get("pics")
        #print wb_item.get("push_time")
        #print wb_item.get("resource")
        #print wb_item.get("nums")
        
        img_num = 0
        img_dict = wb_item.get("pics")
        push_time = wb_item.get("push_time")
        content = wb_item.get("text")
        ctime = self._format_date(push_time)
        for item in img_dict :
            if img_num >10 :
                break
            try:
                value = self._prepare_calc_img(item)
                if not value or len(value) < 2:
                    continue
                img_id=value[2]
                pic_url=item
                key_buf = str(img_id) + str(uid) + str(pic_url)
                md5_sign = self._calc_md5(key_buf)
                # 已经爬取过
                if md5_sign in self._crawled_keys:
                    log.logging.info("img_id[%s] uid[%s] sign[%s] do not crawled repeatly" % (img_id, uid, md5_sign))
                    continue
                pic_url = "http://"+value[0]+"/bmiddle/"+value[2]+".jpg"
                
                #download图片文件并保存
                sleep_time = random.uniform(0, 3)
                try:
                    log.logging.debug("pic[%d] %s sleeping %f" % (img_num, pic_url, sleep_time))
                    pic_data = self._crawl_weibo(host, pic_url)
                    if not pic_data:
                        continue
                    self._write_file(img_dir, uid +"_" + img_id + ".jpg", pic_data)
                    log.logging.debug("write down pic : " + uid+"_"+img_id+".jpg")
                except Exception as e1 :
                    log.logging.error("for down img error , msg %s"%(e1))
                    time.sleep(sleep_time)
                    continue
                    
                img_num += 1
                img_info.append([img_id,uid,self._format_str(content),-1,-1,ctime,pic_url,md5_sign])
            except Exception as e :
                log.logging.error("for img_dict error , msg %s"%(e))
            
    def _parse_weibo(self,data):
        try:
            html_doc = BeautifulSoup(data, from_encoding='utf-8')
            #print(html_doc.prettify())
            #用户名，头像，描述，性别  
            pcd_header = html_doc.find("div", attrs={"class" : "PCD_header"})
            if pcd_header:
                #用户名称
                user_name = self._get_html_tag(html_doc, "h1", "class", "username")
                #用户头像
                avatar_img = html_doc.find("img", attrs={"class":"photo"})
                avatar_url = avatar_img.get("src")
                intro = html_doc.find("div", attrs={"class":"pf_intro"}).get_text()
                
                gender="-1"
                opt = html_doc.find("div",attrs={"class":"list_content W_f14"});#self._format_str(pcd_header.get_text())
                opt_str = self._format_str(opt.get_text())
                if "他" in opt_str :
                    gender="男"
                if "她" in opt_str:
                    gender="女"
            #所在地，生日        
            pcd_person_info = html_doc.find("div", attrs={"class" : "PCD_person_info"})
            if pcd_person_info :
                ul_detail = html_doc.find("ul",attrs={"class":"ul_detail"})
                loc_li = ul_detail.findAll("li")[0]
                loc_text = loc_li.find("span",attrs={"class":"item_text W_fl"}).get_text()
                #print loc_text.strip()
                if "Lv" in  loc_text.strip() :
                    loc_li = ul_detail.findAll("li")[1]
                    loc_text = loc_li.find("span",attrs={"class":"item_text W_fl"}).get_text()
                   #print loc_text.strip()
                
                if loc_text and len(loc_text.strip()) >0:
                    loc_text = ','.join(loc_text.strip().split(" "))
                bir_li = ul_detail.findAll("li")[1]
                bir_text = bir_li.find("span",attrs={"class":"item_text W_fl"}).get_text()
                #print bir_text.strip()
            #粉丝，关注，微博数
            pcd_counter = html_doc.find("div", attrs={"class" : "PCD_counter"})
            if pcd_counter :
                num_spans = pcd_counter.findAll("td",attrs={"class":"S_line1"})
                nums = [self._calc_num(item.get_text()) for item in num_spans]
                #print nums
            #相册列表    
            pcd_photolist = html_doc.find("div", attrs={"class" : "PCD_photolist"})
            if pcd_photolist :
                #print pcd_photolist.prettify()
                pass
            #获得帖子列表
            wb_info=[]
            wb_main = html_doc.find("div", attrs={"class" : "WB_feed WB_feed_profile"})
            if wb_main:
                for feed_item in wb_main.findAll("div",attrs={"action-type":"feed_list_item"}):
                    try:
                        details = feed_item.find("div",attrs={"class":"WB_detail"})
                        #print feed_item.prettify()
                        text = details.find("div",attrs={"class":"WB_text W_f14"}).get_text()
                        if "转发微博" in text :
                            continue
                        
                        media_box = feed_item.find("div",attrs={"class":"media_box"})
                        img_pics = media_box.findAll("img",attrs={"action-type":"fl_pics"})
                        pics = [str(item.get("src")) for item in img_pics]
                        img_pics = media_box.findAll("img",attrs={"class":"bigcursor"})
                        if len(pics) <=0 :
                            pics = [str(item.get("src")) for item in img_pics]
                        
                        wb_from = feed_item.find("div",attrs={"class":"WB_from S_txt2"})
                        push_time = wb_from.findAll("a",attrs={"class":"S_txt2"})[0].get("title");
                        resource = wb_from.findAll("a",attrs={"class":"S_txt2"})[1].get_text();

                        wb_handle = feed_item.find("div",attrs={"class":"WB_feed_handle"})
                        wb_num_spans = wb_handle.findAll("span",attrs={"class":"line S_line1"})
                        wb_nums = [str(item.get_text()) for item in wb_num_spans]
                        
                        wb_info.append({"text":text,"pics":pics,"push_time":push_time,"resource":resource,"nums":wb_nums})
                    except Exception as e:
                        log.logging.error("for feed_list error , msg %s" %(e))
            # 关注的微博用户        
            pcd_ut_a= html_doc.find("div", attrs={"class" : "PCD_ut_a"})
            if pcd_ut_a :
                pass
            
            return (user_name, gender, loc_text, avatar_url, nums, wb_info)
        except Exception as e:
            log.logging.error("_parse_weibo error , msg %s" % (e))
            return ("", "-1", "", "", "", "")
        
    def finish(self):
        #保存用户爬取情况
        self._writer.write_dict_keys(self._crawled_dict, self._crawled_user_file)
        #self._writer.write_queue(self._user_queue, self._user_file)
    
    def _reflush_proxy_host_666(self,num=100):
        url = 'http://vxer.daili666api.com/ip/?tid=557982535725675&num=%d&delay=1&sortby=time&foreign=none&filter=on'%num
        data = weiborequest.getHtmlSource(url)
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
            data = weiborequest.getHtmlSource(url=url,headers=headers)
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
    def _reflush_proxy_host_kuaidaili(self,page=10):
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
                data = weiborequest.getHtmlSource(url=url,headers=headers)
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
        match = re.search(r'^.*\/(.*)$', url)
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
    def _init_proxy_and_dologin(self, isProxy):
        if self._is_init_running :
            return False
        self._is_init_running = True
        index=0
        #_login = login.sina_login()
        _curr_dir = os.path.split(os.path.realpath(__file__))[0]
        self.sina = LoginSinaCom(soft_path=_curr_dir)
        count=len(self._proxy_dict)
        i=int(random.uniform(0, len(self._account_dict)))
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
                    log.logging.error("_init_proxy_and_dologin - account :%s, proxy_url :%s"%(self._weibo_account, self._proxy_url))
                    #self._init_proxy({"http":self._proxy_url})
                    self.sina = LoginSinaCom(soft_path=_curr_dir,proxyip=self._proxy_url)
                
                # 登录微博 
                res = self.sina.login(self._weibo_account,self._weibo_password)#self.sina.check_cookie(self._weibo_account,self._weibo_password, _curr_dir)
                if not res :
                    index = index +1
                    log.logging.error("_init_proxy_and_dologin - res is %s , index %s , it will be continue"%(str(res),str(index)))
                    if index == count :
                        os._exit()  
                        break
                    else:
                        continue
                else :
                    #self._user_info = self.sina.getLoginUserInfo()
                    #self.cookieStr = res
                    #print self.cookieStr
                    self._is_init_running = False
                    break
            except Exception as e:
                index = index +1
                log.logging.error("_init_proxy_and_dologin error , index %s ,  msg %s"%(str(index), e))
                if index < count :
                    time.sleep(1)
                    continue
                else:
                    os._exit(-1)
                    break
        return True     
    def _init_proxy(self, singleProxyDict):
        proxyHandler = urllib2.ProxyHandler(singleProxyDict)
        #print "proxyHandler=",proxyHandler
        self.cookie = cookielib.LWPCookieJar()
        cookieHandler = urllib2.HTTPCookieProcessor(self.cookie)
        #print "self.cookie=",self.cookie
        proxyOpener = urllib2.build_opener(cookieHandler, proxyHandler, urllib2.HTTPHandler)
        #print "proxyOpener=",proxyOpener
        urllib2.install_opener(proxyOpener)
        return True   
    def _download(self, host, url):
        '''单纯的下载给定url的内容
           @return 页面内容
                        print i.a.get('href')
        '''
        index=int(random.uniform(0, len(self._agent_dict)))
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
                   'User-Agent': self._agent_dict.get(index,"Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.107 Safari/537.36"),
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
                
 
