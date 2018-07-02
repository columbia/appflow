#!/bin/sh

. ./evalconf.sh

serial=`adb get-serialno`
app=$1
round=$2
needrestart=no
logpath=log.txt

if [ "$round" = "" ]; then
    round=1
fi

echo "working on $serial"

if [ "$needrestart" = "yes" ]; then
    while true; do
        ./startvm.sh $vm
        serial=`./getip.sh $vm`
        ./checkvm.py $serial
        if [ $? -eq 0 ]; then
            break
        fi
        echo "! Checkvm failed. restart."
    done

    ./movewin.sh $vm $serial
fi


./app.py $serial dver $app
if [ $? != 0 ]; then
    ./app.py $serial uninstall $app
    ./app.py $serial install $app
fi

rm -f $logpath
./miner.py --app $app --serial $serial --batch --tag $tags --round $round --log $logpath
