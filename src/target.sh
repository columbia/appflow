#!/bin/sh

target=$1
extra=$2

rm ../tlib ../etc ../guis ../model ../guis-extra
ln -s tlib-$target ../tlib
ln -s etc-$target ../etc
ln -s guis-$target ../guis
ln -s model-$target ../model
ln -s guis-$extra ../guis-extra
