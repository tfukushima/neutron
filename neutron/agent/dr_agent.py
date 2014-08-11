# Copyright 2014 Midokrua SARL.  All rights reserved.
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
# @author: Jaume Devesa, devvesa@gmail.com, Midokura SARL

import sys

from oslo.config import cfg

from neutron.agent.common import config
from neutron.agent.linux import external_process
from neutron.agent import rpc as agent_rpc
from neutron.common import config as common_config
from neutron.common import constants
from neutron.common import rpc as n_rpc
from neutron.common import topics
from neutron import context
from neutron import manager
from neutron.openstack.common import importutils
from neutron.openstack.common import log as logging
from neutron.openstack.common import loopingcall
from neutron.openstack.common import periodic_task
from neutron.openstack.common import service
from neutron import service as neutron_service


LOG = logging.getLogger(__name__)


class DRAgentPluginApi(n_rpc.RpcProxy):
    """Agent side of the Dynamic Routing rpc API."""

    BASE_RPC_API_VERSION = '1.0'

    def __init__(self, topic, host):
        super(DRAgentPluginApi,
              self).__init__(topic=topic,
                             default_version=self.BASE_RPC_API_VERSION)
        self.host = host

    def get_peers(self, context):
        """Get the peers connected with the dynamic routing protocol.

        :param context: an instance of neutron.context.
        :returns: a list of dictionaries of a routing peer like below:
            [
              {
               'remote_as': 1324,
               'tenant_id': '7a616a993a5848e8a46c2ab97e870c21',
               'peer': '10.23.43.22',
               'password': None,
               'id': '9539ea6c-c773-49b7-957b-70c47d947ff4',
               'extra_config': {}
               },
            ]
        """
        return self.call(context,
                         self.make_msg('sync_routingpeers',
                                       host=self.host),
                         topic=self.topic)

    def get_advertisenetworks(self, context):
        """Get the routes advertised from the peers connected with the dynamic
        routing protocol.

        :param context: an instance of neutron.context.
        :returns: a list of dictionaries of a subnet like below:
            [
               {
                'name': '',
                'network_id': 'ed2e3c10-2e43-4297-9006-2863a2d1abbc',
                'tenant_id': 'c1210485b2424d48804aad5d39c61b8f',
                'allocation_pools': [{'start': '10.10.0.2', 'end': '10.10.0.254'}],
                'gateway_ip': '10.10.0.1',
                'ip_version': 4,
                'cidr': '10.10.0.0/24',
                'id': '4156c7a5-e8c4-4aff-a6e1-8f3c7bc83861',
                'enable_dhcp': true
               },
            ]
        """
        networks = self.call(context,
                             self.make_msg('sync_advertisenetworks',
                                           host=self.host),
                             topic=self.topic)
        return networks

    def put_discovernetworks(self, context, networks):
        return self.call(context,
                         self.make_msg('sync_discovernetworks',
                                       host=self.host,
                                       networks=networks),
                         topic=self.topic)


def dump_remote_best_path_change(event):
    LOG.debug(_('the best path changed:'), event.remote_as, event.prefix,
              event.nexthop, event.is_withdraw)


class DRAgent(manager.Manager):
    """Manager for Dynamic Routing."""

    OPTS = [
        cfg.StrOpt(
            'bgp_speaker_driver',
            default='neutron.agent.linux.bgp.ryu_driver.RyuBGPDriver',
            help=_('Class of BGP speaker to be instantiated.')),
        cfg.IntOpt(
            'local_as_number',
            help=_('AS number of the host where this agent runs.')),
        cfg.StrOpt(
            'router_id',
            help=_('The BGP identifier, which MUST be the IPv4 address of the '
                   'node where the dynamic routing agent holds the BGP '
                   'speaker lives.')),
    ]

    RPC_API_VERSION = '1.1'
    # This class should be set after the configuration file is loaded
    # explicitly.
    BGP_DRIVER_CLASS = None

    def __init__(self, host, conf=None):
        self.context = context.get_admin_context_without_session()
        self.plugin_rpc = DRAgentPluginApi(topics.DRAGENT, host)
        self.fullsync = True
        self.peers = set()
        self.advertise_networks = set()
        self.driver = self.__class__.BGP_DRIVER_CLASS(
            cfg.CONF.local_as_number,
            cfg.CONF.router_id,
            best_path_change_handler=dump_remote_best_path_change)
        super(DRAgent, self).__init__()

    def add_routingpeer(self, context, routing_peer):
        """Add a new routing peer.

        :param context: an instance of neutron.context
        :param routing_peer: a dictionary of the peer ID and its AS number
        """
        peer_id = routing_peer['peer']
        peer_as = routing_peer['remote_as']
        password = routing_peer['password'] or None  # Forbid empty passwords
        self.driver.add_peer(peer_id, peer_as, password=password)
        self.peers.add(peer_id)

    def remove_routingpeer(self, context, routing_peer):
        """Remove the given routing peer.

        :param context: an instance of neutron.context
        :param routing_peer: a dictionary of the peer ID and its AS number
        """
        peer_id = routing_peer['peer']
        self.driver.del_peer(peer_id)
        self.peers.remove(peer_id)

    @periodic_task.periodic_task
    def periodic_sync_peers_task(self, context):
        self._sync_peers_task(context)

    def _sync_peers_task(self, context):
        LOG.debug(_("Starting _sync_peers_task - fullsync:%s"),
                  self.fullsync)
        if not self.fullsync:
            return
        # peers = self.plugin_rpc.get_peers(self.context)
        # networks = self.plugin_rpc.get_advertisenetworks(self.context)
        # TODO(tfukushina): Taku, this is a periodic task that will ask
        # periodically the peers and the networks to advertise. You have to
        # merge the obtainted values with the previous ones, saved into
        # self.peers and self.advertise_networks. For any doubt, please check
        # out the module neutron.agent.l3_agent. Is quite similar (but more
        # complex) that we want to do.
        # self.peers.update(peers)
        # self.advertise_networks.update(networks)


class DRAgentWithStateReport(DRAgent):

    def __init__(self, host, conf=None):
        super(DRAgentWithStateReport, self).__init__(host, conf)
        self.state_rpc = agent_rpc.PluginReportStateAPI(topics.PLUGIN)
        self.agent_state = {
            'agent_type': constants.AGENT_TYPE_DYNAMIC_ROUTING,
            'binary': 'neutron-dr-agent',
            'configurations': {},
            'host': host,
            'topic': topics.DR_AGENT,
            'start_flag': True}
        report_interval = cfg.CONF.AGENT.report_interval
        if report_interval:
            self.heartbeat = loopingcall.FixedIntervalLoopingCall(
                self._report_state)
            self.heartbeat.start(interval=report_interval)

    def _report_state(self):
        LOG.debug(_("Report state task started"))
        try:
            self.state_rpc.report_state(self.context, self.agent_state)
            self.agent_state.pop('start_flag', None)
            LOG.debug(_("Report state task successfully completed"))
        except AttributeError:
            LOG.warn(_("Neutron server does not support state report."
                       " State report for this agent will be disabled."))
            self.heartbeat.stop()
            return


def main(manager='neutron.agent.dr_agent.DRAgentWithStateReport'):
    cfg.CONF.register_opts(DRAgentWithStateReport.OPTS)
    config.register_agent_state_opts_helper(cfg.CONF)
    config.register_root_helper(cfg.CONF)
    cfg.CONF.register_opts(external_process.OPTS)

    # Configure the BGP speaker driver based on the setting in dr_agent.ini.
    DRAgentWithStateReport.BGP_DRIVER_CLASS = importutils.import_class(
        cfg.CONF.bgp_speaker_driver)

    common_config.init(sys.argv[1:])
    config.setup_logging(conf)
    server = neutron_service.Service.create(
        binary='neutron-dr-agent',
        topic=topics.DR_AGENT,
        report_interval=cfg.CONF.AGENT.report_interval,
        manager=manager)
    service.launch(server).wait()
