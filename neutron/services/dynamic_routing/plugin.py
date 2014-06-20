# Copyright 2011 OpenStack Foundation
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.
# @author: Jaume Devesa, devvesa@gmail.com, Midokura SARL
from oslo.config import cfg

from neutron.api.rpc.agentnotifiers import dr_rpc_agent_api as dr_rpc
from neutron.common import constants as q_const
from neutron.common import rpc as n_rpc
from neutron.common import topics
from neutron.plugins.common import constants
from neutron.db import dr_db
from neutron.db import dr_agentschedulers_db as dr_as_db
from neutron.openstack.common import importutils
from neutron.services.dynamic_routing import dr_rpc_base

class DynamicRoutingPluginRpcCallbacks(
    n_rpc.RpcCallback,
    dr_rpc_base.DynamicRoutingRpcCallbackMixin):

    RPC_API_VERSION = "1.0"
               
                                       
class DynamicRoutingPlugin(dr_db.DynamicRoutingDbMixin,
                           dr_as_db.DynamicRoutingAgentSchedulerDbMixin):

    supported_extension_aliases = ["dynamic_routing",
                                   "dynamic_routing_agent_scheduler"]

    def __init__(self):
        self.dr_scheduler = importutils.import_object(
            cfg.CONF.dynamic_routing_scheduler_driver)
        self._setup_rpc()
        super(DynamicRoutingPlugin, self).__init__()

    def _setup_rpc(self):
        self.topic = topics.DRAGENT
        self.conn = n_rpc.create_connection(new=True)
        self.agent_notifiers.update(
            {q_const.AGENT_TYPE_DYNAMIC_ROUTING:
                dr_rpc.DynamicRoutingAgentNotifyAPI()})
        self.endpoints = [DynamicRoutingPluginRpcCallbacks()]
        self.conn.create_consumer(self.topic, self.endpoints,
                                  fanout=False)
        self.conn.consume_in_threads()

    def get_plugin_description(self):
        return ("Dynamic Routing Service Plugin provides endpoints to "
                "manage routing protocols and dynamically advertise and "
                "discover upstream routes")
