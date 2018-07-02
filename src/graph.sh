for i in `seq 0 50`; do
    echo -n +
    dot tree$i.dot -o tree$i.png -Tpng &
done

while true; do
    if [ -z "`ps aux | grep dot | grep -v grep | grep -v defunct`" ]; then
        echo finished
        break
    fi
    sleep 1
done
