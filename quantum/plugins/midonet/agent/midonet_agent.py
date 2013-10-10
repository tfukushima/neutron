# vim: tabstop=4 shiftwidth=4 softtabstop=4

# Copyright (C) 2012 Midokura Japan K.K.
# Copyright (C) 2013 Midokura PTE LTD
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#
# @author: Rossella Sblendido, Midokura Japan KK
# @author: Tomoe Sugihara, Midokura Japan KK
# @author: Ryu Ishimoto, Midokura Japan KK

from midonetclient import api
from oslo.config import cfg
from webob import exc as w_exc

from quantum.openstack.common import log as logging
from quantum.agent.linux import dhcp
from quantum.agent.linux import interface
from quantum.agent.linux import ip_lib
from quantum.plugins.midonet import config

LOG = logging.getLogger(__name__)


class DhcpDriverNoOp(dhcp.DhcpLocalProcess):
    @classmethod
    def existing_dhcp_networks(cls, conf, root_helper):
        """Return a list of existing networks ids that we have configs for."""
        return []

    @classmethod
    def check_version(cls):
        """Execute version checks on DHCP server."""
        return float(1)

    @classmethod
    def reload_allocations(self):
        """Force the DHCP server to reload the assignment database."""
        pass

    def spawn_process(self):
        """Enables DHCP for this network."""
        pass

    def disable(self, retain_port=False):
        """Disable DHCP for this network."""

        if not retain_port:
            self.device_delegate.destroy(self.network, self.interface_name)

        self._remove_config_files()


midonet_interface_driver_opts = [
    cfg.StrOpt('midonet_host_uuid_path',
               default='/etc/midolman/host_uuid.properties',
               help='path to midonet host uuid file'),
]

cfg.CONF.register_opts(midonet_interface_driver_opts)


class MidonetInterfaceDriver(interface.LinuxInterfaceDriver):
    def __init__(self, conf):
        super(MidonetInterfaceDriver, self).__init__(conf)
        # Read config values
        midonet_conf = conf.MIDONET
        midonet_uri = midonet_conf.midonet_uri
        admin_user = midonet_conf.username
        admin_pass = midonet_conf.password
        admin_project_id = midonet_conf.project_id
        provider_router_id = midonet_conf.provider_router_id
        mode = midonet_conf.mode

        self.mido_api = api.MidonetApi(midonet_uri, admin_user,
                                       admin_pass,
                                       project_id=admin_project_id)

    def _get_host_uuid(self):
        """
        Get MidoNet host id from host_uuid.properties file.
        """
        f = open(cfg.CONF.midonet_host_uuid_path)
        lines = f.readlines()
        host_uuid = filter(lambda x: x.startswith('host_uuid='),
                           lines)[0].strip()[len('host_uuid='):]
        return host_uuid

        """
        This method is called by the Dhcp agent or by the L3 agent when
        a new network is created
        """
    def plug(self, network_id, port_id, device_name, mac_address,
             bridge=None, namespace=None, prefix=None):

        if not ip_lib.device_exists(device_name,
                                    self.root_helper,
                                    namespace=namespace):
            ip = ip_lib.IPWrapper(self.root_helper)
            tap_name = device_name.replace(prefix or 'tap', 'tap')

            # Create ns_dev in a namespace if one is configured.
            root_dev, ns_dev = ip.add_veth(tap_name,
                                           device_name,
                                           namespace2=namespace)

            ns_dev.link.set_address(mac_address)

            # Add an interface created by ovs to the namespace.
            namespace_obj = ip.ensure_namespace(namespace)
            namespace_obj.add_device_to_namespace(ns_dev)

            ns_dev.link.set_up()
            root_dev.link.set_up()

            vport_id = port_id
            host_dev_name = device_name

            # create if-vport mapping.
            host_uuid = self._get_host_uuid()
            try:
                host = self.mido_api.get_host(host_uuid)
            except w_exc.HTTPError as e:
                LOG.error('Failed to create a if-vport mapping on host=%s',
                          host_uuid)
                raise e
            try:
                host.add_host_interface_port().port_id(vport_id) \
                    .interface_name(host_dev_name).create()
            except w_exc.HTTPError as e:
                LOG.warn('Faild binding vport=%r to device=%r',
                         vport_id, host_dev_name)
        else:
            LOG.warn(_("Device %s already exists"), device_name)

    def unplug(self, device_name, bridge=None, namespace=None, prefix=None):
        # the port will be deleted by the dhcp agent that will call the plugin
        device = ip_lib.IPDevice(device_name,
                                 self.root_helper,
                                 namespace)
        device.link.delete()
        LOG.debug(_("Unplugged interface '%s'"), device_name)

        ip_lib.IPWrapper(
            self.root_helper, namespace).garbage_collect_namespace()