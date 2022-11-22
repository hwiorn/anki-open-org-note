#!/bin/bash
pushd $(dirname $0)/..
CUR_TAG=$(git describe --tags)
OUT="org-open-note_$CUR_TAG.ankiaddon"
sed "s/__MOD__/$(date +%s)/g" meta.json.tpl > meta.json
rm -f $OUT
zip -9r $OUT \
	meta.json \
	__init__.py  \
	config.json  \
	icons
popd
echo done
