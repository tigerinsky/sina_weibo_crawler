#!/user/bin/env python
#coding: utf-8

'''
Created on 2015年8月25日

@author: liuweise
'''
import re
from urllib import unquote

if __name__ == '__main__':
    reason="%CE%AA%C1%CB%C4%FA%B5%C4%D5%CA%BA%C5%B0%B2%C8%AB%A3%AC%C7%EB%CA%E4%C8%EB%D1%E9%D6%A4%C2%EB"
    print unquote(reason).decode("gb2312")
    #p = re.compile(r'http://(.*?)/(.*?)/(.*?).jpg')
    #match=p.findall('http://ww1.sinaimg.cn/square/58066dd9jw1ev9su79oujj21kw11xh7r.jpg')
    #print match[0][0]
    
    #p = re.compile(r'\d+')
    #for item in p.finditer("|1959关注|4859粉丝|39194微博") :
    #    print item.group()

    