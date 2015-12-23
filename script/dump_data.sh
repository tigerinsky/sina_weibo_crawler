#!/bin/bash

cd $(dirname "$0")
DIR=`pwd`
. ${DIR}/../conf/conf.sh

function check_size() {
    local file=$1
    local check_size=$2 #单位k
    file_size=`ls -s ${file} | cut -d ' ' -f 1`
    if [ ${file_size} -lt ${check_size} ]
    then
        return 1
    fi
    return 0
}

function dump_data() {
    date
    echo "dump $2" 
    ${MYSQL} -h${DB_HOST} -P${DB_PORT} -u${DB_USER} -p${DB_PWD} ${DB_ARGS} < $1 > $2.bak 
    if [ $? -ne 0 ]
    then
        echo "dump $2 error"
        return 1
    fi
    if [ $# -gt 2 ]
    then
        check_size $2 $3
        if [ $? -ne 0 ]
        then
            echo "$2 size too small"
            return 1
        fi
    fi
    sed '1d' $2.bak > $2
    rm -rf $2.bak
}

dump_data ${SQL_DIR}/get_all_crawled_avatar.sql $1|| exit 1
dump_data ${SQL_DIR}/get_all_crawled_pic.sql $2|| exit 1
