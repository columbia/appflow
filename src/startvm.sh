#!/bin/sh

vmname="$1"
echo restarting $vmname

vmip=`./getip.sh $vmname`
serial="$vmip:5555"
if [ "$serial" != "0.0.0.0:5555" ]; then
    echo serial $serial
fi

if [ "`adb devices | grep $serial`" != "" ]; then
    adb -s $serial shell poweroff &
    sleep 10
fi
playerpid=`pgrep -f "player --vm-name $vmname"`
vboxpid=`pgrep -f "VBoxHeadless --comment $vmname"`

if [ "$playerpid" != "" ]; then
    echo "player not stopped, kill"
    kill $playerpid
fi
if [ "$vboxpid" != "" ]; then
    echo "vbox not stopped, kill"
    kill $vboxpid
fi

sleep 5

nohup /opt/genymobile/genymotion/player --vm-name "$vmname" > ../log/vmout_$vmname.log &

sleep 60
