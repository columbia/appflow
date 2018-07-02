apps=$1
seeds=$2
appcnts=$3

for i in $appcnts; do
    for seed in $seeds; do
        ret=`./classify.py --reallyquiet --app SEL$i --seed $seed --apps $apps 2>&1 | grep final | cut -d : -f 2-2`
        echo -n " " $ret
    done
    echo
done
