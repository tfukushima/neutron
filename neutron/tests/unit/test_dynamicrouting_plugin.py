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
import contextlib
from neutron.api.v2 import attributes
from neutron import context
from neutron.db import dr_db
from neutron.extensions import dynamic_routing
from neutron.openstack.common import uuidutils
from neutron.tests.unit import test_db_plugin

from webob import exc

_uuid = uuidutils.generate_uuid


class DynamicRoutingTestExtensionManager(object):

    def get_resources(self):
        attributes.RESOURCE_ATTRIBUTE_MAP.update(
            dynamic_routing.RESOURCE_ATTRIBUTE_MAP)
        return dynamic_routing.Dynamic_routing.get_resources()

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []


class TestDynamicRoutingPluginNoAgent(dr_db.DynamicRoutingDbMixin):

    supported_extension_aliases = ["dynamic_routing"]

    def get_plugin_description(self):
        return ("Dynamic Routing Service Plugin test class that only   "
                "exposes dynamic routing functionality, without agents,"
                "nor schedulers.")


class DynamicRoutingBaseTestCase(object):

    fmt = 'json'

    def test_routingpeer_create(self):
        peer = '87.12.34.43'
        tenant_id = _uuid()
        remote_as = 2000
        extra_config = {"dummy_value": "yes it is"}
        expected_value = [('peer', peer), ('tenant_id', tenant_id),
                          ('remote_as', remote_as),
                          ('extra_config', extra_config)]
        with self.routingpeer(peer=peer, remote_as=remote_as,
                              tenant_id=tenant_id,
                              extra_config=extra_config) as routingpeer:
            for k, v in expected_value:
                self.assertEqual(routingpeer['routingpeer'][k], v)

    def test_routinginstance_create(self):
        nexthop = '8.8.8.8'
        tenant_id = _uuid()
        advertise = False
        discover = True
        expected_value = [('nexthop', nexthop), ('tenant_id', tenant_id),
                          ('advertise', advertise), ('discover', discover)]
        with self.routinginstance(
            nexthop=nexthop, advertise=advertise,
            discover=discover, tenant_id=tenant_id) as ri:
            for k, v in expected_value:
                self.assertEqual(ri['routinginstance'][k], v)

    def test_routingpeer_list(self):
        with contextlib.nested(self.routingpeer('123.23.23.12'),
                               self.routingpeer('123.32.43.13'),
                               self.routingpeer('123.43.12.54')
                               ) as routingpeers:
            self._test_list_resources('routingpeer', routingpeers)

    def test_routinginstance_list(self):
        with contextlib.nested(self.routinginstance(),
                               self.routinginstance(),
                               self.routinginstance()
                               ) as routinginstances:
            self._test_list_resources('routinginstance', routinginstances)

    def test_routingpeer_update(self):
        remote_as1 = 12345
        remote_as2 = 12357
        with self.routingpeer(remote_as=remote_as1) as rp:
            body = self._show('routingpeers', rp['routingpeer']['id'])
            self.assertEqual(body['routingpeer']['remote_as'], remote_as1)

            body = self._update('routingpeers', rp['routingpeer']['id'],
                                {'routingpeer': {'remote_as': remote_as2}})

            body = self._show('routingpeers', rp['routingpeer']['id'])
            self.assertEqual(body['routingpeer']['remote_as'], remote_as2)

    def test_routinginstance_update(self):
        advertise1 = False
        advertise2 = True
        with self.routinginstance(advertise=advertise1) as ri:
            body = self._show('routinginstances', ri['routinginstance']['id'])
            self.assertEqual(body['routinginstance']['advertise'], advertise1)

            body = self._update('routinginstances',
                                ri['routinginstance']['id'],
                                {'routinginstance': {'advertise': advertise2}})

            body = self._show('routinginstances', ri['routinginstance']['id'])
            self.assertEqual(body['routinginstance']['advertise'], advertise2)

    def test_routingpeer_show_non_existent(self):
        req = self.new_show_request('routingpeers', _uuid(), fmt=self.fmt)
        res = req.get_response(self.ext_api)
        self.assertEqual(res.status_int, exc.HTTPNotFound.code)

    def test_routinginstance_show_non_existent(self):
        req = self.new_show_request('routinginstances', _uuid())
        res = req.get_response(self.ext_api)
        self.assertEqual(res.status_int, exc.HTTPNotFound.code)

    def test_routingpeer_create_two_equal_peers(self):
        with self.routingpeer() as rp1:
            res = self._create_routingpeer(rp1['routingpeer']['tenant_id'],
                                           rp1['routingpeer']['peer'])
            self.assertEqual(res.status_int, exc.HTTPConflict.code)

    def test_routinginstance_add_delete_network_to_routinginstance(self):
        with self.network() as net:
            with self.routinginstance() as ri:
                net_id = net['network']['id']
                routinginstance_id = ri['routinginstance']['id']
                data = {'network_id': net_id}
                req = self.new_create_request(
                    'routinginstances', data, self.fmt, routinginstance_id,
                    'networks')
                res = req.get_response(self.ext_api)
                self.assertEqual(res.status_int, exc.HTTPCreated.code)

                req_show = self.new_show_request(
                    'routinginstances', routinginstance_id, self.fmt,
                    'networks')
                res_show = req_show.get_response(self.ext_api)
                nets = self.deserialize(self.fmt, res_show)
                self.assertEqual(len(nets['networks']), 1)

                req = self.new_delete_request(
                    'routinginstances', routinginstance_id, self.fmt,
                    'networks', net_id)
                res = req.get_response(self.ext_api)
                self.assertEqual(res.status_int, exc.HTTPNoContent.code)

                res_show = req_show.get_response(self.ext_api)
                nets = self.deserialize(self.fmt, res_show)
                self.assertEqual(len(nets['networks']), 0)

    def test_routinginstance_avoid_add_network_two_times(self):
        with self.network() as net:
            with self.routinginstance() as ri:
                net_id = net['network']['id']
                routinginstance_id = ri['routinginstance']['id']
                data = {'network_id': net_id}
                req = self.new_create_request(
                    'routinginstances', data, self.fmt, routinginstance_id,
                    'networks')
                res = req.get_response(self.ext_api)
                self.assertEqual(res.status_int, exc.HTTPCreated.code)

                res = req.get_response(self.ext_api)
                self.assertEqual(res.status_int, exc.HTTPConflict.code)

    def test_routinginstance_disassociate_unknow_network(self):
        with self.network() as net:
            with self.routinginstance() as ri:
                net_id = net['network']['id']
                routinginstance_id = ri['routinginstance']['id']
                req = self.new_delete_request(
                    'routinginstances', routinginstance_id, self.fmt,
                    'networks', net_id)
                res = req.get_response(self.ext_api)
                self.assertEqual(res.status_int, exc.HTTPNotFound.code)

    def _create_routingpeer(self, tenant_id, peer, remote_as=1000,
                            password=None, extra_config=None, fmt=None,
                            set_context=False):
        fmt = fmt or self.fmt
        data = {'routingpeer': {'tenant_id': tenant_id,
                                'peer': peer,
                                'remote_as': remote_as}}
        if password:
            data['routingpeer']['password'] = password
        if extra_config:
            data['routingpeer']['extra_config'] = extra_config
        routingpeer_req = self.new_create_request('routingpeers', data, fmt)
        if set_context and tenant_id:
            routingpeer_req.environ['neutron.context'] = context.Context(
                '', tenant_id)
        return routingpeer_req.get_response(self.ext_api)

    def _create_routinginstance(self, nexthop='13.143.87.1', advertise=True,
                                discover=False, tenant_id=_uuid(), fmt=None,
                                set_context=False):
        data = {'routinginstance': {'tenant_id': tenant_id,
                                    'nexthop': nexthop,
                                    'advertise': advertise,
                                    'discover': discover}}
        routinginstance_req = self.new_create_request('routinginstances',
                                                      data, fmt or self.fmt)
        if set_context and tenant_id:
            routinginstance_req.environ['neutron.context'] = context.Context(
                '', tenant_id)
        return routinginstance_req.get_response(self.ext_api)

    @contextlib.contextmanager
    def routingpeer(self, peer='13.132.43.2', remote_as=1000,
                    tenant_id=_uuid(), password=None, extra_config=None,
                    fmt=None, set_context=False):
        fmt = fmt or self.fmt
        routingpeer = self._create_routingpeer(
            tenant_id, peer, remote_as, password,
            extra_config, fmt, set_context)
        routingpeer = self.deserialize(fmt, routingpeer)
        yield routingpeer
        self._delete('routingpeers', routingpeer['routingpeer']['id'])

    @contextlib.contextmanager
    def routinginstance(self, nexthop='13.143.87.1', advertise=True,
                        discover=False, tenant_id=_uuid(), fmt=None,
                        set_context=False):
        fmt = fmt or self.fmt
        routinginstance = self._create_routinginstance(
            nexthop, advertise, discover, tenant_id, fmt,
            set_context)
        routinginstance = self.deserialize(fmt, routinginstance)
        yield routinginstance
        self._delete('routinginstances',
                     routinginstance['routinginstance']['id'])


class DynamicRoutingPluginTests(test_db_plugin.NeutronDbPluginV2TestCase,
                                DynamicRoutingBaseTestCase):

    def setUp(self, plugin=None, ext_mgr=None, service_plugins=None):
        if not plugin:
            plugin = ('neutron.tests.unit.test_dynamicrouting_plugin.'
                      'TestDynamicRoutingPluginNoAgent')
        ext_mgr = ext_mgr or DynamicRoutingTestExtensionManager()
        super(DynamicRoutingPluginTests, self).setUp(
            plugin=plugin, ext_mgr=ext_mgr, service_plugins=service_plugins)
