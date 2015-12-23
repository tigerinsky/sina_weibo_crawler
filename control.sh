#!/bin/sh

WORK_DIR="/data/crawler/crawlSina"
SERVER_NAME='crawler'

function print_help() {
    echo "$0 [start|stop|restart]"
}

if [ $# -ne 1 ]; then
    print_help
    exit
fi

mkdir -p ${WORK_DIR}/log
mkdir -p ${WORK_DIR}/status

if [ "$1" == "start" ]; then
    if [ ! -e ${WORK_DIR}/status/supervisord.sock ]; then
        supervisord -c conf/supervisord.conf
    else 
        cd ${WORK_DIR} && supervisorctl -c conf/supervisord.conf start ${SERVER_NAME}
    fi
elif [ "$1" == "stop" ]; then
    echo "stop"
    cd ${WORK_DIR} && supervisorctl -c conf/supervisord.conf stop ${SERVER_NAME}
elif [ "$1" == "restart" ]; then
    echo "restart"
    cd ${WORK_DIR} && supervisorctl -c conf/supervisord.conf restart ${SERVER_NAME}
else
    print_help
fi
