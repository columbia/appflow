serial=$1
ip=`echo $serial | cut -d : -f 1-1`

for winid in `xdotool search --class Genymotion`; do
    winname=`xdotool getwindowname $winid`
    if [ "`echo $winname | grep $ip`" != "" ]; then
        echo -n $winid
        exit 0
    fi
done

exit 2

