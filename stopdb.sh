# stop the mongodb
if [[ "$MONGODIR" == "" ]]; then
    echo Variable MONGODIR is undefined.
    exit 1
fi
mongod --dbpath $MONGODIR/citegraph/data/db --shutdown
