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
from sqlalchemy.orm import exc
from sqlalchemy import sql

from neutron.common import constants
from neutron.db import agents_db
from neutron.db import dr_agentschedulers_db as dr_as_db
from neutron.db import dr_db

from neutron.openstack.common import log as logging

LOG = logging.getLogger(__name__)


class DynamicRoutingScheduler(object):

    def auto_schedule_routingpeers(self, context, host):
        """Schedule non-hosted routing peers to a DR agent.
        """
        with context.session.begin(subtransactions=True):
            query = context.session.query(agents_db.Agent)
            query = query.filter(agents_db.Agent.agent_type ==
                                 constants.AGENT_TYPE_DYNAMIC_ROUTING,
                                 agents_db.Agent.host == host,
                                 agents_db.Agent.admin_state_up == sql.true())
            try:
                dr_agent = query.one()
            except (exc.NoResultFound):
                LOG.debug(_('No enabled DR agent on host %s'), host)
                return False

            if agents_db.AgentDbMixin.is_agent_down(
                dr_agent.heartbeat_timestamp):
                LOG.warn(_('DR agent %s is not active'), dr_agent.id)
                return False

            stmt = ~sql.exists().where(
                dr_db.RoutingPeer.id ==
                dr_as_db.RoutingPeerAgentBinding.routingpeer_id)

            unscheduled_peers_ids = [peer_id_[0] for peer_id_ in
                                     context.session.query(
                                     dr_db.RoutingPeer.id).filter(stmt)]

            if not unscheduled_peers_ids:
                return False

            for unscheduler_peer_id in unscheduled_peers_ids:
                self._bind_peer(context, unscheduler_peer_id, dr_agent.id)

        return True

    def auto_schedule_routinginstances(self, context, host):
        """Schedule non-hosted routing instances to a DR agent.
        """
        with context.session.begin(subtransactions=True):
            query = context.session.query(agents_db.Agent)
            query = query.filter(agents_db.Agent.agent_type ==
                                 constants.AGENT_TYPE_DYNAMIC_ROUTING,
                                 agents_db.Agent.host == host,
                                 agents_db.Agent.admin_state_up == sql.true())
            try:
                dr_agent = query.one()
            except (exc.NoResultFound):
                LOG.debug(_('No enabled DR agent on host %s'), host)
                return False

            if agents_db.AgentDbMixin.is_agent_down(
                dr_agent.heartbeat_timestamp):
                LOG.warn(_('DR agent %s is not active'), dr_agent.id)
                return False

            if self._is_instance_hosted(context, dr_agent['id']):
                # Agent only can host a single routing instance
                return False

            stmt = ~sql.exists().where(
                dr_db.RoutingInstance.id ==
                dr_as_db.RoutingInstanceAgentBinding.routinginstance_id)

            unscheduled_instances_ids = [instance_id_[0] for instance_id_ in
                                         context.session.query(
                                         dr_db.RoutingInstance.id).filter(
                                             stmt)]

            if not unscheduled_instances_ids:
                return False

            self._bind_instance(context, unscheduled_instances_ids[0],
                                dr_agent.id)
        return True

    def _bind_peer(self, context, routingpeer_id, agent_id):
        with context.session.begin(subtransactions=True):
            binding = dr_as_db.RoutingPeerAgentBinding()
            binding.agent_id = agent_id
            binding.routingpeer_id = routingpeer_id
            context.session.add(binding)
            LOG.debug(_('Routingpeer %(routingpeer_id)s is scheduled to '
                        'DR agent %(agent_id)s'),
                      {'routingpeer_id': routingpeer_id,
                       'agent_id': agent_id})

    def _is_instance_hosted(self, context, agent_id):
        with context.session.begin(subtransactions=True):
            query = context.session.query(
                dr_as_db.RoutingInstanceAgentBinding)
            query.filter(
                dr_as_db.RoutingInstanceAgentBinding.agent_id == agent_id)
            try:
                query.one()
                return True
            except exc.NoResultFound:
                return False

    def _bind_instance(self, context, routinginstance_id, agent_id):
        with context.session.begin(subtransactions=True):
            binding = dr_as_db.RoutingInstanceAgentBinding()
            binding.agent_id = agent_id
            binding.routinginstance_id = routinginstance_id
            context.session.add(binding)
            LOG.debug(_('Routinginstance %(routinginstance_id)s is scheduled '
                        'to DR agent %(agent_id)s'),
                      {'routinginstance_id': routinginstance_id,
                       'agent_id': agent_id})
