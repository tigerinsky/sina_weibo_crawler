#!/bin/bash

cd $(dirname "$0")
DIR=`pwd`
. ${DIR}/../conf/conf.sh

date
echo 'start dump data from mysql'
sh ${SCRIPT_DIR}/dump_data.sh $1 $2
if [ $? -ne 0 ]
then
    date
    echo 'dump data error'
    exit 1
fi

