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
import abc
import six
import webob

from neutron.api import extensions
from neutron.api.v2 import base
from neutron.api.v2 import resource
from neutron.common import constants
from neutron.common import exceptions
from neutron.extensions import agent
from neutron import manager
from neutron.openstack.common import log as logging
from neutron import policy
from neutron.services import service_base
from neutron import wsgi

LOG = logging.getLogger(__name__)

DR_PEER = 'dr-peer'
DR_PEERS = DR_PEER + 's'
DR_AGENT = 'dr-agent'
DR_AGENTS = DR_AGENT + 's'


class InvalidDRAgent(agent.AgentNotFound):
    message = _("Agent %(id)s is not a Dynamic Routing Agent or has been"
                " disabled.")


class RoutingPeerAgentBinding(exceptions.Conflict):
    message = _("The routing peer %(routingpeer_id)s has been already hosted"
                " by the Dynamic Routing Agent %(agent_id)s.")


class RoutingPeerSchedulingFailed(exceptions.Conflict):
    message = _("Failed scheduling routingpeer %(routingpeer_id)s to"
                " the Dynamic Routing Agent %(agent_id)s.")


class RoutingPeerNotHosted(exceptions.Conflict):
    message = _("The routing peer %(routingpeer_id)s is not hosted "
                "by the Dynamic Routing Agent %(agent_id)s.")


class RoutingPeerHostedByDRAgent(exceptions.Conflict):
    message = _("The routing peer %(routingpeer_id)s is already hosted "
                "by the Dynamic Routing Agent %(agent_id)s.")


class DynamicRoutingSchedulerController(wsgi.Controller):
    """Schedule peers for Dyanmic Routing agents"""
    def get_plugin(self):
        plugin = manager.NeutronManager.get_service_plugins().get(
            constants.DR_AGENT_SCHEDULER_EXT_ALIAS)
        if not plugin:
            LOG.error(_('No plugin for Dynamic Routing registered to handle '
                        'router scheduling'))
            msg = _('The resource could not be found.')
            raise webob.exc.HTTPNotFound(msg)
        return plugin

    def index(self, request, **kwargs):
        plugin = self.get_plugin()
        policy.enforce(request.context,
                       "get_%s" % DR_PEERS,
                       {})
        return plugin.list_peers_on_dr_agent(request.context,
                                             kwargs['agent_id'])

    def create(self, request, body, **kwargs):
        plugin = self.get_plugin()
        policy.enforce(request.context,
                       "create_%s" % DR_PEER,
                       {})
        return plugin.add_routingpeer_to_dr_agent(
            request.context,
            kwargs['agent_id'],
            body['routingpeer_id'])

    def delete(self, request, id, **kwargs):
        plugin = self.get_plugin()
        policy.enforce(request.context,
                       "delete_%s" % DR_PEER, {})
        return plugin.remove_routingpeer_from_dr_agent(
            request.context, kwargs['agent_id'], id)


class DynamicRoutingAgentsHostingPeerController(wsgi.Controller):
    def get_plugin(self):
        plugin = manager.NeutronManager.get_service_plugins().get(
            constants.DR_AGENT_SCHEDULER_EXT_ALIAS)
        if not plugin:
            LOG.error(_('No plugin for dynamic routing registered'))
            msg = _('The resource could not be found.')
            raise webob.exc.HTTPNotFound(msg)
        return plugin

    def index(self, request, **kwargs):
        plugin = self.get_plugin()
        policy.enforce(request.context,
                       "get_%s" % DR_AGENTS,
                       {})
        return plugin.list_dr_agents_hosting_peer(request.context,
                                                  kwargs['routingpeer_id'])


class RoutingInstanceAgentsController(wsgi.Controller):
    def get_plugin(self):
        plugin = manager.NeutronManager.get_service_plugins().get(
            constants.DR_AGENT_SCHEDULER_EXT_ALIAS)
        if not plugin:
            LOG.error(_('No plugin for dynamic routing registered'))
            msg = _('The resource could not be found.')
            raise webob.exc.HTTPNotFound(msg)
        return plugin

    def index(self, request, **kwargs):
        plugin = self.get_plugin()
        policy.enforce(request.context, "list_agents_on_routing_instance", {})
        return plugin.list_agents_on_routinginstance(
            request.context, kwargs['routinginstance_id'])

    def create(self, request, body, **kwargs):
        plugin = self.get_plugin()
        policy.enforce(request.context, "add_agent_to_routinginstance", {})
        return plugin.add_agent_to_routinginstance(
            request.context,
            kwargs['routinginstance_id'],
            body['agent_id'])

    def delete(self, request, id, **kwargs):
        plugin = self.get_plugin()
        policy.enforce(
            request.context, "remove_agent_from_routinginstance", {})
        return plugin.remove_agent_from_routinginstance(
            request.context, kwargs['routinginstance_id'], id)


class Dr_agentscheduler(extensions.ExtensionDescriptor):
    """Extension class supporting Dynamic Routing scheduler.
    """
    @classmethod
    def get_name(cls):
        return "Dynamic Routing Agent Scheduler"

    @classmethod
    def get_alias(cls):
        return constants.DR_AGENT_SCHEDULER_EXT_ALIAS

    @classmethod
    def get_description(cls):
        return "Schedule peers among dynamic routing agents"

    @classmethod
    def get_namespace(cls):
        return "http://docs.openstack.org/ext/dr_agent_scheduler/api/v1.0"

    @classmethod
    def get_updated(cls):
        return "2014-07-09T10:00:00-00:00"

    @classmethod
    def get_resources(cls):
        """Returns Ext Resources."""
        exts = []
        parent = dict(member_name="agent",
                      collection_name="agents")

        controller = resource.Resource(DynamicRoutingSchedulerController(),
                                       base.FAULT_MAP)
        exts.append(extensions.ResourceExtension(
            DR_PEERS, controller, parent))

        parent = dict(member_name="routingpeer",
                      collection_name="routingpeers")
        controller = resource.Resource(
            DynamicRoutingAgentsHostingPeerController(), base.FAULT_MAP)
        exts.append(extensions.ResourceExtension(
            DR_AGENTS, controller, parent))

        parent = dict(member_name="routinginstance",
                      collection_name="routinginstances")
        controller = resource.Resource(RoutingInstanceAgentsController(),
                                       base.FAULT_MAP)
        exts.append(extensions.ResourceExtension(
            DR_AGENTS, controller, parent))

        return exts

    def get_extended_resources(self, version):
        return {}


@six.add_metaclass(abc.ABCMeta)
class DynamicRoutingSchedulerPluginBase(service_base.ServicePluginBase):

    def get_plugin_name(self):
        return constants.DR_AGENT_SCHEDULER_EXT_ALIAS

    def get_plugin_type(self):
        return constants.DR_AGENT_SCHEDULER_EXT_ALIAS

    def get_plugin_description(self):
        return "Dynamic Routing Plugin Scheduler"

    @abc.abstractmethod
    def list_peers_on_dr_agent(self, context, agent_id):
        pass

    @abc.abstractmethod
    def add_routingpeer_to_dr_agent(self, context, agent_id, routingpeer_id):
        pass

    @abc.abstractmethod
    def remove_routingpeer_from_dr_agent(self, context, agent_id,
                                         routingpeer_id):
        pass

    @abc.abstractmethod
    def list_dr_agents_hosting_peer(self, context, routingpeer_id):
        pass

    @abc.abstractmethod
    def list_agents_on_routinginstance(self, context, id):
        pass

    @abc.abstractmethod
    def add_agent_to_routinginstance(self, context, routinginstance_id,
                                     agent_id):
        pass

    @abc.abstractmethod
    def remove_agent_from_routinginstance(self, context, routinginstance_id,
                                          agent_id):
        pass
