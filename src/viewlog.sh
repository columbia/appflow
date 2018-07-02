app=$1

logdir="../log"

if [ "$2" = "" ]; then
    logfile=`ls $logdir/*/$1.log | grep -v latest | tail -n 1`
else
    if [ "`ls $logdir/*$2*/$1.log`" != "" ]; then
        logfile="$logdir/*$2*/$1.log"
    else
        logfile="$logdir/*$2*/log_$1.txt"
    fi
fi

vim $logfile
