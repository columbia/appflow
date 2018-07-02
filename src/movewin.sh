. ./evalconf.sh

vmname=$1
serial=$2

winid=`./getwin.sh $serial`

for entry in $winpos; do
    entryname=`echo $entry | cut -d @ -f 1-1`
    entryx=`echo $entry | cut -d @ -f 2-2`
    entryy=`echo $entry | cut -d @ -f 3-3`
    if [ "$entryy" = "" ]; then
        entryy="0"
    fi
    if [ "$entryname" = "$vmname" ]; then
        xdotool windowmove $winid $entryx $entryy
        exit 0
    fi
done

exit 2
