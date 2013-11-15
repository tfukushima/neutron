# Get version number from command line
pkgver=$1
if [ '$pkgver' == '' ]
then
	echo "Please specify the package version, e.g. 'ppackage-midonet-only-debian.sh 1:2013.1.2.mido5-0ubuntu1.mido1' to package as version 1:2013.1.2.mido5-0ubuntu1.mido1"
	exit
else
    echo "Packaging with version number $pkgver"
fi

# package debian
fpm --name 'python-quantum-plugin-midonet' --architecture 'noarch' --license '2013, Midokura' \
--vendor 'Midokura' --maintainer "Ubuntu Developers" --url 'http://midokura.com' \
--description 'Quantum is a virtual network service for Openstack - Python library
  Quantum MidoNet plugin is a MidoNet virtual network service plugin for Openstack Neutron.' \
-d 'python-quantum' -d 'python2.7' -d 'python >= 2.7.1-0ubuntu2' -d 'python << 2.8' \
--replaces 'python-quantum' \
--provides 'python2.7-quantum-plugin-midonet' \
-s dir -C quantum/plugins/midonet/ --prefix /usr/lib/python2.7/dist-packages/quantum/plugins/midonet/ --version $pkgver --deb-priority 'optional' -t deb .
