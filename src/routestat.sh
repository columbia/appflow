for file in `ls ../log/*/*.log | grep -v latest`; do
    grep -H ROUTE $file | tail -n 1
done
