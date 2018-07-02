#!/bin/sh

vm=$1
vmip=`./getip.sh $vm`

for app in `ls ../apks/ | grep .apk | sed -e 's/.apk//'`; do
    ./app.py $vmip dver $app
    if [ $? != 0 ]; then
        ./app.py $vmip uninstall $app
        ./app.py $vmip install $app
    fi
done
