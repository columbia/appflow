app=$1

logdir="../log"

logfile=`ls $logdir/*/$1.log | grep -v latest | tail -n 1`

tail -f $logfile
