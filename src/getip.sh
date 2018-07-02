#!/bin/sh

vmname=$1
vmip=`genymotion-shell -c "devices list" 2>/dev/null | grep -v selected | grep $vmname | grep virtual | cut -d '|' -f 5-5`
vmip2=`echo -n $vmip`

echo -n $vmip2

