#!/bin/bash

cd $(dirname "$0")
DIR=`pwd`

. ${DIR}/conf/conf.sh

mkdir -p ${LOG_DIR}

tmp_id=1
timestamp=`date +%s`
tmp_file="${BASE_DIR}/data/tmpid"
if [ -f ${tmp_file} ]
then
    tmp_id=`cat ${tmp_file}`
fi
#users="${BASE_DIR}/data/users.txt"
#users_now="${BASE_DIR}/data/users"
#if [ -f ${users_now} ]
#then
#    mv ${users_now} ${users_now}.${timestamp}
#fi
#echo "tmp_id :$tmp_id" 
#cat $users | tail -n +$tmp_id | head -n 200 >$users_now
#num=`cat $users_now|wc -l`
#echo "num :$num"
#if [ "$num" -eq "0" ]
#then
#    echo "1">$tmp_file
#else
#    cou=$[num+tmp_id]
#    echo "cou :$cou"
#    echo $cou >$tmp_file
#fi

#img_info="${BASE_DIR}/result/imgdes/img_info"
#user_info="${BASE_DIR}/result/users/user_info"
#if [ -f ${img_info} ]
#then
#    mv ${img_info} ${img_info}.${timestamp}
#fi
#if [ -f ${user_info} ]
#then
#    mv ${user_info} ${user_info}.${timestamp}
#fi

#date
#echo 'get crawled info from mysql'
#******** get crawled info from mysql *****
#sh ${SCRIPT_DIR}/get_data.sh \
#    ${CRAWLED_AVATAR_CONF} \
#    ${CRAWLED_PIC_CONF}

#echo 'get crawled info from mysql done!'

#******** crawl *****
date
echo 'spidering ...'
python ${SCRIPT_DIR}/main.py \
    ${BASE_DIR}/conf/spider.conf \
    ${CRAWLED_AVATAR_CONF} \
    ${CRAWLED_PIC_CONF}
echo 'spider done!'

date
#echo 'uploading ...'
#******** upload data *********
#/home/retu/php/bin/php -c /home/retu/php/etc/php.ini ${BASE_DIR}/upload/upload.php
#echo 'upload done!'

#ps -ef|grep crawlSina|grep -v grep|cut -c 9-15| xargs kill -s 9
#cp ./data/users.2.bak ./data/users.2
