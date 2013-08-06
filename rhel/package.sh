#!/bin/bash -e

version=$1
package=python-quantum-midonet

git archive HEAD --prefix=$package-$version/ -o /home/midokura/rpmbuild/SOURCES/$package-$version.tar
gzip /home/midokura/rpmbuild/SOURCES/$package-$version.tar
rpmbuild -ba rhel/$package.spec
