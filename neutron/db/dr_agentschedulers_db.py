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
from oslo.config import cfg
import sqlalchemy as sa
from sqlalchemy import orm
from neutron.api.rpc.agentnotifiers import dr_rpc_agent_api
from neutron.common import constants
from neutron.db import agentschedulers_db as as_db
from neutron.db import dr_db
from neutron.db import model_base
from neutron.db import models_v2
from neutron.extensions import dr_agentscheduler as dr_as

DR_AGENT_SCHEDULER_OPTS = [
    cfg.StrOpt('dynamic_routing_scheduler_driver',
               default='neutron.scheduler.dr_agent_scheduler'
                       '.DynamicRoutingHAScheduler',
               help=_('Driver to use for scheduling '
                      'peers to dynamic routing agent')),
    cfg.BoolOpt('dynamic_routing_auto_schedule', default=True,
                help=_('Allow auto scheduling of peers to DR agent.')),
]

cfg.CONF.register_opts(DR_AGENT_SCHEDULER_OPTS)

class RoutingPeerAgentBinding(model_base.BASEV2, models_v2.HasId):
    
    """Binding between routing peers and DR agent. """

    routingpeer_id = sa.Column(sa.String(36),
                               sa.ForeignKey("routingpeers.id",
                                             ondelete='RESTRICT'))
    agent_id = sa.Column(sa.String(36),
                         sa.ForeignKey("agents.id",
                                       ondelete='RESTRICT'))

class RoutingInstanceAgentBinding(model_base.BASEV2, models_v2.HasId):
    """Binding between routing instance and agents"""
    routinginstance_id = sa.Column(sa.String(36),
                                   sa.ForeignKey("routinginstances.id",
                                                 ondelete='RESTRICT'))
    routinginstance = orm.relation(dr_db.RoutingInstance)
    agent_id = sa.Column(sa.String(36),
                         sa.ForeignKey("agents.id",
                                       ondelete='RESTRICT'))

class DynamicRoutingAgentSchedulerDbMixin(
    dr_as.RoutingPeerSchedulerPluginBase,
    as_db.AgentSchedulerDbMixin):

    dr_scheduler = None

    def auto_schedule_routingpeers(self, context, host):
        if self.dr_scheduler:
            return self.dr_scheduler.auto_schedule_routingpeers(
                context, host)

    def auto_schedule_routinginstances(self, context, host):
        if self.dr_scheduler:
            return self.dr_scheduler.auto_schedule_routinginstances(
                context, host)


    def list_peers_on_dr_agent(self, context, agent_id):
        LOG.debug(_("list_peers_on_dr_agent() called"))
        query = context.session.query(RoutingPeerAgentBinding.routingpeer_id)
        query = query.filter(RoutingPeerAgentBinding.agent_id == agent_id)

        peer_ids = [item[0] for item in query]
        if peer_ids:
            return {'routingpeers':
                    self.get_routingpeers(context, filters={'id': peer_ids})}
        else:
            return {'routingpeers': []}

    def add_routingpeer_to_dr_agent(self, context, agent_id, routingpeer_id):
        """Add a dr agent to host a routingpeer."""
        routingpeer = self._get_routingpeer(context, routingpeer_id)
        with context.session.begin(subtransactions=True):
            agent_db = self._get_agent(context, agent_id)
            if (agent_db['agent_type'] != constants.AGENT_TYPE_DYNAMIC_ROUTING
                    or not agent_db['admin_state_up']): # or
                # not self.get_l3_agent_candidates(router, [agent_db])):
                raise dr_as.InvalidDRAgent(id=agent_id)
            query = context.session.query(RoutingPeerAgentBinding)
            query = query.filter(
                    RoutingPeerAgentBinding.agent_id == agent_db.id,
                    RoutingPeerAgentBinding.routingpeer_id == routingpeer_id)

            try:
                binding = query.one()
                raise dr_as.RoutingPeerHostedByDRAgent(routingpeer_id=routingpeer_id,
                                                       agent_id=binding.agent_id)
            except exc.NoResultFound:
                pass

            binding = RoutingPeerAgentBinding()
            binding.agent_id = agent_db.id
            binding.routingpeer_id = routingpeer_id
            context.session.add(binding)
            LOG.debug(_('Routingpeer %(routingpeer_id)s is scheduled to '
                        'DR agent %(agent_id)s'),
                      {'routingpeer_id': routingpeer_id,
                       'agent_id': agent_db.id})

        routingpeer_dict = self._make_routingpeer_dict(routingpeer)
        self.dr_rpc_notifier.add_routingpeer(context, routingpeer_dict, agent_db.host)

    def remove_routingpeer_from_dr_agent(self, context, agent_id,
                                         routingpeer_id):
        with context.session.begin(subtransactions=True):
            agent_db = self._get_agent(context, agent_id)
            query = context.session.query(RoutingPeerAgentBinding)
            query = query.filter(
                    RoutingPeerAgentBinding.agent_id == agent_db.id,
                    RoutingPeerAgentBinding.routingpeer_id == routingpeer_id)
            try:
                binding = query.one()
            except exc.NoResultFound:
                raise dr_as.RoutingPeerNotHosted(routingpeer_id=routingpeer_id,
                                                 agent_id=agent_db.id)
            context.session.delete(binding)

        self.dr_rpc_notifier.remove_routingpeer(context, routingpeer_id,
                                                agent_db.host)

    def list_dr_agents_hosting_peer(self, context, routingpeer_id):
        with context.session.begin(subtransactions=True):
            bindings = self._get_dr_bindings_hosting_peers(
                context, [routingpeer_id])
            results = []
            for binding in bindings:
                dr_agent_dict = self._make_agent_dict(binding.agent)
                results.append(dr_agent_dict)
            if results:
                return {'agents': results}
            else:
                return {'agents': []}

    def list_agents_on_routinginstance(self, context, routinginstance_id):
        LOG.debug(_("list_agents_on_routinginstance() called"))
        query = context.session.query(RoutingInstanceAgentBinding.agent_id)
        query = query.filter(RoutingInstanceNetBinding.routinginstance_id ==
                routinginstance_id)

        agent_ids = [item[0] for item in query]
        if agent_ids:
            return {'agents':
                    self.get_agents(context, filters={'id': agent_ids})}
        else:
            return {'agents': []}

    def add_agent_to_routinginstance(self, context, routinginstance_id,
                                     agent_id):
        """Associate a agent to a routing instance."""
        with context.session.begin(subtransactions=True):
            routinginstance = self._get_routinginstance(
                    context,
                    routinginstance_id)
            query = context.session.query(RoutingInstanceAgentBinding)
            query = query.filter(
                    RoutingInstanceAgentBinding.routinginstance_id ==
                    routinginstance_id,
                    RoutingInstanceAgentBinding.agent_id == agent_id)

            try:
                binding = query.one()
                raise dr.AgentAlreadyAssociated(
                    routinginstance_id=binding.routinginstance_id,
                    agent_id=agent_id)
            except exc.NoResultFound:
                pass

            binding = RoutingInstanceAgentBinding()
            binding.routinginstance_id = routinginstance.id
            binding.agent_id = agent_id
            context.session.add(binding)
            LOG.debug(_('Agent %(agent_id)s is associated to '
                        'routing instance %(routinginstance_id)s'),
                      {'routinginstance_id': routinginstance.id,
                       'agent_id': agent_id})

    def _get_dr_bindings_hosting_peers(self, context, routingpeer_ids):
        if not routingpeer_ids:
            return []
        query = context.session.query(RoutingPeerAgentBinding)
        if len(routingpeer_ids) > 1:
            query = query.options(joinedload('agent')).filter(
                RoutingPeerAgentBinding.routingpeer_id.in_(routingpeer_ids))
        else:
            query = query.options(joinedload('agent')).filter(
                RoutingPeerAgentBinding.routingpeer_id == routingpeer_ids[0])
        return query.all()

    def remove_agent_from_routinginstance(self, context, routinginstance_id,
                                          agent_id):
        with context.session.begin(subtransactions=True):
            routinginstance_db = self._get_routinginstance(
                context, routinginstance_id)
            query = context.session.query(RoutingInstanceAgentBinding)
            query = query.filter(
                    RoutingInstanceAgentBinding.routinginstance_id ==
                    routinginstance_db.id,
                    RoutingInstanceAgentBinding.agent_id == agent_id)
            try:
                binding = query.one()
            except exc.NoResultFound:
                raise dr.RoutingInstanceAgentNotHosted(ri_id=routinginstance_id,
                                                       agent_id=agent_id)
            context.session.delete(binding)

    def list_active_sync_routingpeers_on_dr_agent(self, context, host):
        agent = self._get_agent_by_type_and_host(
                context, constants.AGENT_TYPE_DYNAMIC_ROUTING, host)
        if not agent.admin_state_up:
            return []
        query = context.session.query(RoutingPeerAgentBinding.routingpeer_id)
        query = query.filter(
            RoutingPeerAgentBinding.agent_id == agent.id)
        return [item[0] for item in query]

    def list_active_sync_routinginstances_on_dr_agent(self, context, host):
        agent = self._get_agent_by_type_and_host(
                context, constants.AGENT_TYPE_DYNAMIC_ROUTING, host)
        if not agent.admin_state_up:
            return []
        query = context.session.query(
            RoutingInstanceAgentBinding.routinginstance_id)
        query = query.filter(
            RoutingInstanceAgentBinding.agent_id == agent.id)
        return [item[0] for item in query]
