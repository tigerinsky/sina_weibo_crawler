#!/user/bin/env python
#coding: utf-8

'''
Created on 2015年8月18日

@author: liuweise
'''

import os
import sys
import time
import log
import ConfigParser
import spider

reload(sys)
sys.setdefaultencoding('utf8')

if __name__ == '__main__':
    cf = ConfigParser.ConfigParser()
    #cf.read("../conf/spider.conf")
    cf.read(sys.argv[1])
    #初始logging
    log.init_log(cf.get("weibo", "BASE") + cf.get("weibo", "LOG_FILE"), log.logging.INFO)
    log.logging.info("read conf ok [%s]" % time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
    
    crawled_avatar_conf = sys.argv[2] #cf.get("weibo", "BASE") + cf.get("weibo", "CRAWLED_USERS_AVATAR_FILE")
    crawled_pic_conf = sys.argv[3] #cf.get("weibo", "BASE") + cf.get("weibo", "CRAWLED_USERS_PIC_FILE")

    thread = []

    for i in range(0, 1):
        Spider = spider.Spider(cf, crawled_avatar_conf, crawled_pic_conf, i)
        #爬取
        time_now = int(time.time())
        log.logging.info("spider weibo job start [%s]", time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time_now)))
        Spider.start()
        thread.append(Spider)

    for t in thread:
        t.join()
    #保存用户爬取情况
    #Spider.finish()

    log.logging.info("spider weibo job done [%s]" % time.strftime('%Y-%m-%d %H:%M:%S', time.localtime((time.time()))))
    sys.exit(0)	
