# Copyright 2012 VMware, Inc.  All rights reserved.
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
from neutron.openstack.common import service
from neutron.openstack.common import log as logging
from neutron.openstack.common import loopingcall
from neutron import context
from neutron import manager
from neutron import service as neutron_service

LOG = logging.getLogger(__name__)


class DRAgentCallbackMixin(object):
    """Agent side of the Dynamic Routing rpc API."""

    def __init__(self, topic, context):
        super(DRAgentPluginApi,
              self).__init__(topic=topic,
                             default_version=self.BASE_RPC_API_VERSION)
        self.context = context
        self.host = cfg.CONF.host

    def get_peers(self):
        peers = self.call(self.context,
                          self.make_msg('get_peers'),
                          topic.self.topic)
        return peers


class DRAgent(manager.Manager):
    """Manager for Dynamic Routing. """

    OPTS = []
    RPC_API_VERSION = '1.1'

    def __init__(self, host, conf=None):
        self.context = context.get_admin_context_without_session()

    def add_routingpeer(self, context, payload):
        # TODO(tfukushima): implement this call using the Ryu's BGP speaker
        #                  driver
        pass

    def remove_routingpeer(self, context, payload):
        # TODO(tfukushima): implement this call using the Ryu's BGP speaker
        #                  driver
        pass


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
    conf = cfg.CONF
    conf.register_opts(DRAgentWithStateReport.OPTS)
    config.register_agent_state_opts_helper(conf)
    config.register_root_helper(conf)
    conf.register_opts(external_process.OPTS)
    common_config.init(sys.argv[1:])
    config.setup_logging(conf)
    server = neutron_service.Service.create(
        binary='neutron-dr-agent',
        topic=topics.DR_AGENT,
        report_interval=cfg.CONF.AGENT.report_interval,
        manager=manager)
    service.launch(server).wait()
