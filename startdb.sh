# start the mongodb
if [[ "$MONGODIR" == "" ]]; then
    echo Variable MONGODIR is undefined.
    exit 1
fi
mkdir -p log
mkdir -p $MONGODIR/citegraph/data/db
mongod --dbpath $MONGODIR/citegraph/data/db --port 27016 --bind_ip_all --fork --logpath ./log/mongodb.log
