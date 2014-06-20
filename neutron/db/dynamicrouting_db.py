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
import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.orm import exc
from sqlalchemy.orm import joinedload

from oslo.config import cfg

from neutron.api.rpc.agentnotifiers import dr_rpc_agent_api
from neutron.common import constants
from neutron.db import agents_db
from neutron.db import agentschedulers_db
from neutron.db import common_db_mixin
from neutron.db import db_base_plugin_v2 as base_db
from neutron.db import model_base
from neutron.db import models_v2
from neutron.extensions import dynamic_routing as dr
from neutron.extensions import dr_agentscheduler as dr_as
from neutron.openstack.common import jsonutils
from neutron.openstack.common import log as logging
from neutron.openstack.common import uuidutils


LOG = logging.getLogger(__name__)


class RoutingPeer(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    """Represents a routing peer."""

    peer = sa.Column(sa.String(64))
    protocol = sa.Column(sa.String(255))
    configuration = sa.Column(sa.String(4096))


class RoutingPeerAgentBinding(model_base.BASEV2, models_v2.HasId):
    """Binding between routing peers and DR agent. """

    routingpeer_id = sa.Column(sa.String(36),
                               sa.ForeignKey("routingpeers.id",
                                             ondelete='RESTRICT'))
    agent = orm.relation(agents_db.Agent)
    agent_id = sa.Column(sa.String(36),
                         sa.ForeignKey("agents.id",
                                       ondelete='RESTRICT'))

class RoutingInstance(model_base.BASEV2, models_v2.HasId, models_v2.HasTenant):
    """ Represents a routing instance."""

    nexthop = sa.Column(sa.String(64))
    advertise = sa.Column(sa.Boolean)
    discover = sa.Column(sa.Boolean)


class RoutingInstanceNetBinding(model_base.BASEV2, models_v2.HasId):
    """Binding between routing instance and networks"""
    __tablename__ = "routinginstancenetworkbindings"

    routinginstance_id = sa.Column(sa.String(36),
                                   sa.ForeignKey("routinginstances.id",
                                                 ondelete='RESTRICT'))
    routinginstance = orm.relation(RoutingInstance)
    network_id = sa.Column(sa.String(36),
                           sa.ForeignKey("networks.id",
                                         ondelete='RESTRICT'))

class RoutingInstanceAgentBinding(model_base.BASEV2, models_v2.HasId):
    """Binding between routing instance and agents"""
    routinginstance_id = sa.Column(sa.String(36),
                                   sa.ForeignKey("routinginstances.id",
                                                 ondelete='RESTRICT'))
    routinginstance = orm.relation(RoutingInstance)
    agent_id = sa.Column(sa.String(36),
                         sa.ForeignKey("agents.id",
                                       ondelete='RESTRICT'))


class DynamicRoutingDbMixin(agentschedulers_db.AgentSchedulerDbMixin,
                            dr.DynamicRoutingPluginBase,
                            dr_as.RoutingPeerSchedulerPluginBase,
                            base_db.NeutronDbPluginV2):


    """docstring for DynamicRouting_db_mixin"""
    def __init__(self):
        super(DynamicRoutingDbMixin, self).__init__()

    @property
    def dr_rpc_notifier(self):
        if not hasattr(self, '_dr_rpc_notifier'):
            self._dr_rpc_notifier = dr_rpc_agent_api.DynamicRoutingAgentNotifyAPI()
        return self._dr_rpc_notifier

    def create_routingpeer(self, context, routingpeer):
        LOG.debug(_("create_routingpeer() called"))
        rp = routingpeer['routingpeer']
        with context.session.begin(subtransactions=True):
            res_keys = ['peer', 'protocol', 'tenant_id', 'configuration']
            res = dict((k, rp[k]) for k in res_keys)
            configuration_dict = rp.get('configuration', {})
            res['configuration'] = jsonutils.dumps(configuration_dict)
            res['id'] = uuidutils.generate_uuid()
            routingpeer_db = RoutingPeer(**res)
            context.session.add(routingpeer_db)


        return self._make_routingpeer_dict(routingpeer_db)


    def create_routinginstance(self, context, routinginstance):
        LOG.debug(_("create_routinginstance() called"))
        rp = routinginstance['routinginstance']
        with context.session.begin(subtransactions=True):
            res_keys = ['advertise', 'discover', 'nexthop', 'tenant_id']
            res = dict((k, rp[k]) for k in res_keys)
            res['id'] = uuidutils.generate_uuid()
            routinginstance_db = RoutingInstance(**res)
            context.session.add(routinginstance_db)

        return self._make_routinginstance_dict(routinginstance_db)

    def delete_routingpeer(self, context, routingpeer_id):
        LOG.debug(_("delete_routingpeer() called"))
        with context.session.begin(subtransactions=True):
            routingpeer = self._get_routingpeer(context, routingpeer_id)
            context.session.delete(routingpeer)

    def delete_routinginstance(self, context, routinginstance_id):
        LOG.debug(_("delete_routinginstance() called"))
        with context.session.begin(subtransactions=True):
            routinginstance = self._get_routinginstance(context, routinginstance_id)
            context.session.delete(routinginstance)

    def get_routingpeers(self, context, filters=None, fields=None):
        LOG.debug(_("get_routingpeers() called"))
        coll = self._get_collection(context, RoutingPeer,
                                    self._make_routingpeer_dict,
                                    filters=filters,
                                    fields=fields)
        return coll

    def get_routingpeer(self, context, id, fields=None):
        LOG.debug(_("get_routingpeer() called"))
        routingpeer = self._get_routingpeer(context, id)
        return self._make_routingpeer_dict(routingpeer, fields)

    def get_routinginstance(self, context, id, fields=None):
        LOG.debug(_("get_routinginstance() called"))
        routinginstance = self._get_routinginstance(context, id)
        return self._make_routinginstance_dict(routinginstance, fields)

    def update_routingpeer(self, context, id, routingpeer):
        LOG.debug(_("update_routingpeer() called"))
        rp = routingpeer['routingpeer']
        with context.session.begin(subtransactions=True):
            routingpeer = self._get_routingpeer(context, id)
            routingpeer.update(rp)
            return self._make_routingpeer_dict(routingpeer)

    def update_routinginstance(self, context, id, routinginstance):
        LOG.debug(_("update_routinginstance() called"))
        rp = routinginstance['routinginstance']
        with context.session.begin(subtransactions=True):
            routinginstance = self._get_routinginstance(context, id)
            routinginstance.update(rp)
            return self._make_routinginstance_dict(routinginstance)

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
            LOG.debug(_('Router %(routingpeer_id)s is scheduled to '
                        'L3 agent %(agent_id)s'),
                      {'routingpeer_id': routingpeer_id,
                       'agent_id': agent_db.id})

        routingpeer_dict = self._make_routingpeer_dict(routingpeer)
        self.dr_rpc_notifier.add_routingpeer(context, routingpeer_dict, agent_db.host)

    def add_network_to_routinginstance(self, context, routinginstance_id,
                                       network_id):
        """Associate a network to a routing instance."""
        with context.session.begin(subtransactions=True):
            routinginstance = self._get_routinginstance(
                    context,
                    routinginstance_id)
            query = context.session.query(RoutingInstanceNetBinding)
            query = query.filter(
                    RoutingInstanceNetBinding.routinginstance_id ==
                    routinginstance_id,
                    RoutingInstanceNetBinding.network_id == network_id)

            try:
                binding = query.one()
                raise dr.NetworkAlreadyAssociated(
                    routinginstance_id=binding.routinginstance_id,
                    network_id=network_id)
            except exc.NoResultFound:
                pass

            binding = RoutingInstanceNetBinding()
            binding.routinginstance_id = routinginstance.id
            binding.network_id = network_id
            context.session.add(binding)
            LOG.debug(_('Network %(network_id)s is associated to '
                        'routing instance %(routinginstance_id)s'),
                      {'routinginstance_id': routinginstance.id,
                       'network_id': network_id})

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

    def remove_network_from_routinginstance(self, context, routinginstance_id,
                                            network_id):

        with context.session.begin(subtransactions=True):
            routinginstance_db = self._get_routinginstance(
                context, routinginstance_id)
            query = context.session.query(RoutingInstanceNetBinding)
            query = query.filter(
                    RoutingInstanceNetBinding.routinginstance_id ==
                    routinginstance_db.id,
                    RoutingInstanceNetBinding.network_id == network_id)
            try:
                binding = query.one()
            except exc.NoResultFound:
                raise dr.RoutingInstanceNetNotHosted(ri_id=routinginstance_id,
                                                     network_id=network_id)
            context.session.delete(binding)

    def get_routinginstances(self, context, filters=None, fields=None):
        LOG.debug(_("get_routinginstances() called"))
        coll = self._get_collection(context, RoutingInstance,
                                    self._make_routinginstance_dict,
                                    filters=filters,
                                    fields=fields)
        return coll

    def list_networks_on_routinginstance(self, context, routinginstance_id):
        LOG.debug(_("list_networks_on_routinginstance() called"))
        query = context.session.query(RoutingInstanceNetBinding.network_id)
        query = query.filter(RoutingInstanceNetBinding.routinginstance_id ==
                routinginstance_id)

        network_ids = [item[0] for item in query]
        if network_ids:
            return {'networks':
                    self.get_networks(context, filters={'id': network_ids})}
        else:
            return {'networks': []}

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

    def _get_routingpeer(self, context, id):
        try:
            return self._get_by_id(context, RoutingPeer, id)
        except exc.NoResultFound:
            raise dr.RoutingPeerNotFound(routingpeer_id=id)

    def _get_routinginstance(self, context, id):
        try:
            return self._get_by_id(context, RoutingInstance, id)
        except exc.NoResultFound:
            raise dr.RoutingInstanceNotFound(routinginstance_id=id)

    def _make_routinginstance_dict(self, routinginstance, fields=None):
        attr = dr.RESOURCE_ATTRIBUTE_MAP.get('routinginstances')
        res = { k: routinginstance[k] for k in attr }
        return res

    def _make_routingpeer_dict(self, routingpeer, fields=None):
        attr = dr.RESOURCE_ATTRIBUTE_MAP.get('routingpeers')
        res = { k: routingpeer[k] for k in attr }
        return res
