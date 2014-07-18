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
from neutron.common import rpc as n_rpc
from neutron.common import topics
from neutron.extensions import dynamic_routing as dr
from neutron.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class DynamicRoutingAgentNotifyAPI(n_rpc.RpcProxy):
    """API for plugin to notify DR agent"""
    BASE_RPC_API_VERSION = '1.0'

    def __init__(self, topic=topics.DR_AGENT):
        super(DynamicRoutingAgentNotifyAPI, self).__init__(
            topic=topic, default_version=self.BASE_RPC_API_VERSION)

    def _notification_host(self, context, method, payload, host):
        """Notify the agent that is hosting the peer."""
        LOG.debug(_('Nofity agent at %(host)s the message '
                    '%(method)s'), {'host': host,
                                    'method': method})
        self.cast(
            context, self.make_msg(method,
                                   payload=payload),
            topic='%s.%s' % (topics.DR_AGENT, host))

    def add_routingpeer(self, context, payload, host):
        self._notification_host(context, 'add_routingpeer', payload, host)

    def remove_routingpeer(self, context, routingpeer_id, host):
        self._notification_host(context,
                                'remove_routingpeer',
                                routingpeer_id,
                                host)
