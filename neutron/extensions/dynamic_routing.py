# Copyright (c) 2013 OpenStack Foundation.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# @author Jaume Devesa, Midokura SARL, devvesa@gmail.com
import abc
import six
import webob

from neutron.api import extensions
from neutron.api.v2 import attributes as attr
from neutron.api.v2 import base
from neutron.api.v2 import resource
from neutron.api.v2 import resource_helper as rh
from neutron.common import exceptions
from neutron import manager
from neutron.openstack.common import log as logging
from neutron.plugins.common import constants
from neutron import policy
from neutron.services import service_base
from neutron import wsgi


LOG = logging.getLogger(__name__)


RESOURCE_ATTRIBUTE_MAP = {
    'routingpeers': {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:uuid': None},
               'is_visible': True, 'primary_key': True},
        'peer': {'allow_post': True, 'allow_put': False,
                 'validate': {'type:ip_address': None},
                 'is_visible': True, 'default': None,
                 'required_by_policy': False,
                 'enforce_policy': False},
        'remote_as': {'allow_post': True, 'allow_put': True,
                      'validate': {'type:range': (0, 65535)},
                      'convert_to': attr.convert_to_int,
                      'is_visible': True, 'default': None,
                      'required_by_policy': False,
                      'enforce_policy': False},
        'password': {'allow_post': True,
                     'allow_put': True,
                     'is_visible': False,
                     'required_by_policy': False,
                     'default': None,
                     'enforce_policy': False},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'validate': {'type:string': None},
                      'required_by_policy': True,
                      'is_visible': True},
        'extra_config': {'allow_post': True, 'allow_put': True,
                         'validate': {'type:dict_or_none': None},
                         'is_visible': True, 'default': None,
                         'required_by_policy': False,
                         'enforce_policy': False},
    },
    'routinginstances': {
        'id': {'allow_post': False, 'allow_put': False,
               'validate': {'type:uuid': None},
               'is_visible': True,
               'required_by_policy': False,
               'enforce_policy': False},
        'nexthop': {'allow_post': True, 'allow_put': True,
                    'validate': {'type:ip_address': None},
                    'is_visible': True, 'default': '',
                    'required_by_policy': False,
                    'enforce_policy': False},
        'tenant_id': {'allow_post': True, 'allow_put': False,
                      'validate': {'type:string': None},
                      'required_by_policy': True,
                      'is_visible': True},
        'discover': {'allow_post': True, 'allow_put': True,
                     'validate': {'type:boolean': None},
                     'is_visible': True,
                     'required_by_policy': False,
                     'enforce_policy': False},
        'advertise': {'allow_post': True, 'allow_put': True,
                      'validate': {'type:boolean': None},
                      'is_visible': True,
                      'required_by_policy': False,
                      'enforce_policy': False},
        'advertise_routes': {'allow_post': False, 'allow_put': True,
                             'validate': {'type:subnet_list': None},
                             'is_visible': True,
                             'convert_to': attr.convert_none_to_empty_list,
                             'required_by_policy': False,
                             'enforce_policy': False}
    },

}


# Dynamic Routing Exceptions
class RoutingPeerNotFound(exceptions.NotFound):
    message = _("RoutingPeer %(routingpeer_id)s could not be found.")


class RoutingInstanceNotFound(exceptions.NotFound):
    message = _("RoutingInstance %(routinginstance_id)s could not be found.")


class NetworkAlreadyAssociated(exceptions.Conflict):
    message = _("Network %(network_id)s already associated to routing "
                "instance %(routinginstance_id)s.")


class PeerExists(exceptions.Conflict):
    message = _("Peer %(peer)s already exists.")


class RoutingInstanceNetNotHosted(exceptions.NotFound):
    message = _("The network %(network_id)s not associated to "
                "routing instance %(ri_id)s.")


class RoutingInstanceAgentNotHosted(exceptions.NotFound):
    message = _("The agent %(agent_id)s not associated to "
                "routing instance %(ri_id)s.")


class RoutingInstanceNetworksController(wsgi.Controller):
    def get_plugin(self):
        plugin = manager.NeutronManager.get_service_plugins().get(
            constants.DYNAMIC_ROUTING)
        if not plugin:
            LOG.error(_('No plugin for dynamic routing registered'))
            msg = _('The resource could not be found.')
            raise webob.exc.HTTPNotFound(msg)
        return plugin

    def index(self, request, **kwargs):
        plugin = manager.NeutronManager.get_service_plugins().get(
            constants.DYNAMIC_ROUTING)
        policy.enforce(
            request.context, "list_networks_on_routing_instance", {})
        return plugin.list_networks_on_routinginstance(
            request.context, kwargs['routinginstance_id'])

    def create(self, request, body, **kwargs):
        plugin = self.get_plugin()
        policy.enforce(request.context, "add_network_to_routinginstance", {})
        return plugin.add_network_to_routinginstance(
            request.context,
            kwargs['routinginstance_id'],
            body['network_id'])

    def delete(self, request, id, **kwargs):
        plugin = self.get_plugin()
        policy.enforce(
            request.context, "remove_network_from_routinginstance", {})
        return plugin.remove_network_from_routinginstance(
            request.context, kwargs['routinginstance_id'], id)


class Dynamic_routing(extensions.ExtensionDescriptor):

    @classmethod
    def get_name(cls):
        return "Neutron Dynamic Routing"

    @classmethod
    def get_alias(cls):
        return "dynamic_routing"

    @classmethod
    def get_description(cls):
        return("Discover and advertise routes dynamically")

    @classmethod
    def get_namespace(cls):
        return "http://docs.openstack.org/ext/neutron/dynamicrouting/api/v1.0"

    @classmethod
    def get_updated(cls):
        return "2014-07-01T15:37:00-00:00"

    @classmethod
    def get_resources(cls):
        plural_mappings = rh.build_plural_mappings(
            {}, RESOURCE_ATTRIBUTE_MAP)
        attr.PLURALS.update(plural_mappings)
        action_map = {}
        exts = rh.build_resource_info(plural_mappings,
                                      RESOURCE_ATTRIBUTE_MAP,
                                      constants.DYNAMIC_ROUTING,
                                      action_map=action_map)
        parent = dict(member_name="routinginstance",
                      collection_name="routinginstances")
        controller = resource.Resource(RoutingInstanceNetworksController(),
                                       base.FAULT_MAP)
        exts.append(extensions.ResourceExtension(
            'networks', controller, parent))

        return exts

    @classmethod
    def get_plugin_interface(cls):
        return DynamicRoutingPluginBase

    def update_attributes_map(self, attributes):
        super(Dynamic_routing, self).update_attributes_map(
            attributes, extension_attrs_map=RESOURCE_ATTRIBUTE_MAP)


@six.add_metaclass(abc.ABCMeta)
class DynamicRoutingPluginBase(service_base.ServicePluginBase):
    """Base functionality for Dynamic Routing Extension"""

    def get_plugin_name(self):
        return constants.DYNAMIC_ROUTING

    def get_plugin_type(self):
        return constants.DYNAMIC_ROUTING

    def get_plugin_description(self):
        return "Dynamic Routing Plugin"

    @abc.abstractmethod
    def get_routingpeers(self, context, filters=None, fields=None):
        pass

    @abc.abstractmethod
    def get_routingpeer(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def create_routingpeer(self, context, routingpeer):
        pass

    @abc.abstractmethod
    def delete_routingpeer(self, context, id):
        pass

    @abc.abstractmethod
    def update_routingpeer(self, context, id, routingpeer):
        pass

    @abc.abstractmethod
    def get_routinginstances(self, context, filters=None, fields=None):
        pass

    @abc.abstractmethod
    def get_routinginstance(self, context, id, fields=None):
        pass

    @abc.abstractmethod
    def create_routinginstance(self, context, routinginstance):
        pass

    @abc.abstractmethod
    def delete_routinginstance(self, context, id):
        pass

    @abc.abstractmethod
    def update_routinginstance(self, context, id, routinginstance):
        pass

    @abc.abstractmethod
    def list_networks_on_routinginstance(self, context, id):
        pass

    @abc.abstractmethod
    def add_network_to_routinginstance(self, context, routinginstance_id,
                                       network_id):
        pass

    @abc.abstractmethod
    def remove_network_from_routinginstance(self, context, routinginstance_id,
                                            network_id):
        pass
