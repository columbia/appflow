#!/bin/sh

. ./evalconf.sh

vmname=$1

logname=`date +%Y%m%d_%H%M%S`

echo "log: $logname"

logdir=$basedir/log/$logname
statpath=$logdir/stat

mkdir $logdir
mkdir $statpath

rm -f $basedir/log/latest-$vmname
ln -fs $logname $basedir/log/latest-$vmname
rm -f $basedir/lstat-$vmname
ln -fs log/$logname/stat $basedir/lstat-$vmname

if [ "$2" = "" ]; then
    apps=`cat apps.txt | grep -v \#`
else
    shift
    apps="$*"
fi

#for app in `ls ../apks/ | sed -e 's/.apk//'`; do
for app in $apps; do
    if [ "$app" = "norestart" ]; then
        needrestart=no
        continue
    fi

    echo "# Working on $app"
    serial=`./getip.sh $vmname`

    if [ "$needrestart" = "yes" ]; then
        while true; do
            ./startvm.sh $vmname
            serial=`./getip.sh $vmname`
            ./checkvm.py $serial
            if [ $? -eq 0 ]; then
                break
            fi
            echo "! Checkvm failed. restart."
        done

        ./movewin.sh $vmname $serial
    fi

    ./app.py $serial dver $app
    if [ $? != 0 ]; then
        echo "# Removing $app first"
        ./app.py $serial uninstall $app
        echo "# Installing $app"
        ./app.py $serial install $app
    fi
    echo "# Start testing!"
    ./miner.py --app $app --tag $tags --batch --rounds $rounds --statpath $logdir/stat --serial $serial --log $logdir/$app.log --state $logdir/state.txt

    echo "# Removing $app"
    ./app.py $serial uninstall $app
done
