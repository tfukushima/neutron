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
import copy
import mock
from webob import exc

from neutron.extensions import dr_agentscheduler
from neutron.extensions import dynamic_routing
from neutron.openstack.common import uuidutils
from neutron.plugins.common import constants as service_constants
from neutron.tests.unit import test_api_v2
from neutron.tests.unit import test_api_v2_extension

_uuid = uuidutils.generate_uuid
_get_path = test_api_v2._get_path


class DynamicRoutingSchedulerPluginTestCase(
    test_api_v2_extension.ExtensionTestCase):
    """Test routing peer scheduler exposed extension"""

    fmt = 'json'

    def setUp(self):
        super(DynamicRoutingSchedulerPluginTestCase, self).setUp()
        plural_mappings = {'routingpeer': 'routingpeers',
                           'agent': 'agents',
                           'routinginstance': 'routinginstances'}
        self._setUpExtension(
            'neutron.extensions.dr_agentscheduler.'
            'DynamicRoutingSchedulerPluginBase',
            service_constants.DR_AGENT_SCHEDULER,
            {}, dr_agentscheduler.Dr_agentscheduler, '',
            plural_mappings=plural_mappings)

    def test_list_peers_on_dr_agent(self):
        return_value = {'routingpeers': []}
        agent_id = _uuid()

        instance = self.plugin.return_value
        instance.list_peers_on_dr_agent.return_value = return_value

        res = self.api.get(_get_path('agents/%s/dr-peers' % agent_id,
                                     fmt=self.fmt))
        self.assertEqual(res.status_int, exc.HTTPOk.code)

        instance.list_peers_on_dr_agent.assert_called_with(mock.ANY, agent_id)
        res = self.deserialize(res)
        self.assertIn('routingpeers', res)

    def test_add_routingpeer_to_dr_agent(self):
        agent_id = _uuid()
        routingpeer_id = _uuid()

        data = {'routingpeer_id': routingpeer_id}

        instance = self.plugin.return_value
        res = self.api.post(_get_path('agents/%s/dr-peers' % agent_id,
                                     fmt=self.fmt),
                            self.serialize(data),
                            content_type='application/%s' % self.fmt)
        self.assertEqual(res.status_int, exc.HTTPCreated.code)

        instance.add_routingpeer_to_dr_agent.assert_called_with(
            mock.ANY, agent_id, routingpeer_id)

    def test_remove_routingpeer_from_dr_agent(self):
        agent_id = _uuid()
        routingpeer_id = _uuid()

        instance = self.plugin.return_value
        res = self.api.delete(_get_path('agents/%s/dr-peers/%s'
                                        % (agent_id, routingpeer_id),
                                        fmt=self.fmt))
        self.assertEqual(res.status_int, exc.HTTPNoContent.code)

        instance.remove_routingpeer_from_dr_agent.assert_called_with(
            mock.ANY, agent_id, routingpeer_id)

    def test_list_dr_agents_hosting_peer(self):
        return_value = {'agents': []}
        routingpeer_id = _uuid()

        instance = self.plugin.return_value
        instance.list_peers_on_dr_agent.return_value = return_value

        res = self.api.get(_get_path('routingpeers/%s/dr-agents'
                                     % routingpeer_id,
                                     fmt=self.fmt))
        self.assertEqual(res.status_int, exc.HTTPOk.code)

        instance.list_dr_agents_hosting_peer.assert_called_with(
            mock.ANY, routingpeer_id)
        res = self.deserialize(res)
        self.assertIn('agents', res)

    def test_list_agents_on_routinginstance(self):
        return_value = {'agents': []}
        routinginstance_id = _uuid()

        instance = self.plugin.return_value
        instance.list_peers_on_dr_agent.return_value = return_value

        res = self.api.get(_get_path('routinginstances/%s/dr-agents'
                                     % routinginstance_id,
                                     fmt=self.fmt))
        self.assertEqual(res.status_int, exc.HTTPOk.code)

        instance.list_agents_on_routinginstance.assert_called_with(
            mock.ANY, routinginstance_id)
        res = self.deserialize(res)
        self.assertIn('agents', res)

    def test_add_agent_to_routinginstance(self):
        routinginstance_id = _uuid()
        agent_id = _uuid()

        data = {'agent_id': agent_id}

        instance = self.plugin.return_value
        res = self.api.post(_get_path('routinginstances/%s/dr-agents'
                                      % routinginstance_id,
                                      fmt=self.fmt),
                            self.serialize(data),
                            content_type='application/%s' % self.fmt)
        self.assertEqual(res.status_int, exc.HTTPCreated.code)

        instance.add_agent_to_routinginstance.assert_called_with(
            mock.ANY, routinginstance_id, agent_id)

    def test_remove_agent_from_routinginstance(self):
        routinginstance_id = _uuid()
        agent_id = _uuid()

        instance = self.plugin.return_value

        res = self.api.delete(_get_path('routinginstances/%s/dr-agents/%s'
                                        % (routinginstance_id, agent_id)))

        self.assertEqual(res.status_int, exc.HTTPNoContent.code)

        instance.remove_agent_from_routinginstance.assert_called_with(
            mock.ANY, routinginstance_id, agent_id)


class DynamicRoutingSchedulerPluginTestCaseXML(
    DynamicRoutingSchedulerPluginTestCase):

    fmt = 'xml'


class DynamicRoutingExtensionTestCase(test_api_v2_extension.ExtensionTestCase):
    """Test all the extension endpoints that should be exposed"""

    fmt = 'json'

    def setUp(self):
        super(DynamicRoutingExtensionTestCase, self).setUp()
        plural_mappings = {'routingpeer': 'routingpeers'}
        self._setUpExtension(
            'neutron.extensions.dynamic_routing.DynamicRoutingPluginBase',
            service_constants.DYNAMIC_ROUTING,
            dynamic_routing.RESOURCE_ATTRIBUTE_MAP,
            dynamic_routing.Dynamic_routing, '',
            plural_mappings=plural_mappings)

    def test_routingpeer_list(self):
        return_value = [{'id': _uuid(),
                         'extra_config': {},
                         'peer': '34.23.10.1',
                         'remote_as': '34500',
                         'password': 'dummy_pass'}]

        instance = self.plugin.return_value
        instance.get_routingpeers.return_value = return_value

        res = self.api.get(_get_path('routingpeers', fmt=self.fmt))
        self.assertEqual(res.status_int, exc.HTTPOk.code)

        instance.get_routingpeers.assert_called_with(mock.ANY,
                                                     fields=mock.ANY,
                                                     filters=mock.ANY)
        res = self.deserialize(res)
        self.assertIn('routingpeers', res)
        self.assertEqual(1, len(res['routingpeers']))

    def test_routingpeer_show(self):
        return_value = {'id': _uuid(),
                        'extra_config': {},
                        'peer': '34.23.10.1',
                        'remote_as': '34500',
                        'password': 'dummy_pass'}
        routingpeer_id = return_value['id']
        instance = self.plugin.return_value
        instance.get_routingpeer.return_value = return_value

        res = self.api.get(
            _get_path('routingpeers/{0}'.format(routingpeer_id),
                      fmt=self.fmt))
        self.assertEqual(res.status_int, exc.HTTPOk.code)

        instance.get_routingpeer.assert_called_with(
            mock.ANY, unicode(routingpeer_id), fields=mock.ANY)

        self._ensure_data_integrity_routingpeer(res,
                                                return_value)

    def test_routingpeer_create(self):
        data = {'routingpeer': {'peer': '34.23.10.1',
                                'extra_config': None,
                                'tenant_id': _uuid(),
                                'remote_as': 34500,
                                'password': 'dummy_pass'}}
        return_value = copy.deepcopy(data['routingpeer'])
        return_value.update({'id': _uuid()})

        instance = self.plugin.return_value
        instance.create_routingpeer.return_value = return_value

        res = self.api.post(_get_path('routingpeers', fmt=self.fmt),
                            self.serialize(data),
                            content_type='application/%s' % self.fmt)
        instance.create_routingpeer.assert_called_with(mock.ANY,
                                                       routingpeer=data)
        self.assertEqual(res.status_int, exc.HTTPCreated.code)
        self._ensure_data_integrity_routingpeer(res,
                                                return_value)

    def test_routingpeer_update(self):
        routingpeer_id = _uuid()
        return_value = {'id': routingpeer_id,
                        'extra_config': {},
                        'peer': '34.23.10.1',
                        'remote_as': 34523,
                        'password': 'dummy_pass'}
        update_data = {'routingpeer': {'password': 'dummiest_pass'}}

        instance = self.plugin.return_value
        instance.update_routingpeer.return_value = return_value

        res = self.api.put(_get_path('routingpeers', id=routingpeer_id,
                                     fmt=self.fmt),
                           self.serialize(update_data))

        instance.update_routingpeer.assert_called_with(
            mock.ANY, routingpeer_id, routingpeer=update_data)
        self.assertEqual(res.status_int, exc.HTTPOk.code)

        self._ensure_data_integrity_routingpeer(res,
                                                return_value)

    def test_routingpeer_delete(self):
        routingpeer_id = _uuid()

        res = self.api.delete(_get_path('routingpeers', id=routingpeer_id))

        instance = self.plugin.return_value
        instance.delete_routingpeer.assert_called_with(
            mock.ANY, routingpeer_id)
        self.assertEqual(res.status_int, exc.HTTPNoContent.code)

    def test_routinginstance_list(self):
        return_value = [{'id': _uuid(),
                         'nexthop': '34.23.10.1',
                         'advertise': True,
                         'discover': True}]

        instance = self.plugin.return_value
        instance.get_routinginstances.return_value = return_value

        res = self.api.get(_get_path('routinginstances', fmt=self.fmt))
        self.assertEqual(res.status_int, exc.HTTPOk.code)

        instance.get_routinginstances.assert_called_with(mock.ANY,
                                                         fields=mock.ANY,
                                                         filters=mock.ANY)
        res = self.deserialize(res)
        self.assertIn('routinginstances', res)
        self.assertEqual(1, len(res['routinginstances']))

    def test_routinginstance_show(self):
        return_value = {'id': _uuid(),
                        'nexthop': '34.23.10.1',
                        'advertise': True,
                        'discover': False}
        ri_id = return_value['id']
        instance = self.plugin.return_value
        instance.get_routinginstance.return_value = return_value

        res = self.api.get(
            _get_path('routinginstances/{0}'.format(ri_id),
                      fmt=self.fmt))
        self.assertEqual(res.status_int, exc.HTTPOk.code)

        instance.get_routinginstance.assert_called_with(
            mock.ANY, unicode(ri_id), fields=mock.ANY)

        self._ensure_data_integrity_routinginstance(res,
                                                    return_value)

    def test_routinginstance_create(self):
        data = {'routinginstance': {'nexthop': '34.23.10.1',
                                    'tenant_id': _uuid(),
                                    'advertise': True,
                                    'discover': True}}
        return_value = copy.deepcopy(data['routinginstance'])
        return_value.update({'id': _uuid()})

        instance = self.plugin.return_value
        instance.create_routinginstance.return_value = return_value

        res = self.api.post(_get_path('routinginstances', fmt=self.fmt),
                            self.serialize(data),
                            content_type='application/%s' % self.fmt)
        instance.create_routinginstance.assert_called_with(
            mock.ANY, routinginstance=data)
        self.assertEqual(res.status_int, exc.HTTPCreated.code)
        self._ensure_data_integrity_routinginstance(res,
                                                    return_value)

    def test_routinginstance_update(self):
        routinginstance_id = _uuid()
        return_value = {'id': routinginstance_id,
                        'nexthop': '34.23.10.1',
                        'advertise': True,
                        'discover': False}
        update_data = {'routinginstance': {'discover': False}}

        instance = self.plugin.return_value
        instance.update_routinginstance.return_value = return_value

        res = self.api.put(_get_path('routinginstances',
                                     id=routinginstance_id,
                                     fmt=self.fmt),
                           self.serialize(update_data))

        instance.update_routinginstance.assert_called_with(
            mock.ANY, routinginstance_id, routinginstance=update_data)
        self.assertEqual(res.status_int, exc.HTTPOk.code)

        self._ensure_data_integrity_routinginstance(res,
                                                    return_value)

    def test_add_network_to_routinginstance(self):
        routinginstance_id = _uuid()
        network_id = _uuid()
        data = {'network_id': network_id}

        path = _get_path('routinginstances',
                         routinginstance_id,
                         'networks',
                         fmt=self.fmt)
        res = self.api.post(path,
                            self.serialize(data),
                            content_type='application/%s' % self.fmt)
        instance = self.plugin.return_value
        instance.add_network_to_routinginstance.assert_called_with(
            mock.ANY, routinginstance_id, network_id)
        self.assertEqual(res.status_int, exc.HTTPCreated.code)

    def test_remote_network_from_routinginstance(self):
        routinginstance_id = _uuid()
        network_id = _uuid()
        path = _get_path('routinginstances/%s/networks/%s' %
            (routinginstance_id, network_id))
        res = self.api.delete(path)
        instance = self.plugin.return_value
        instance.remove_network_from_routinginstance.assert_called_with(
            mock.ANY, routinginstance_id, network_id)
        self.assertEqual(res.status_int, exc.HTTPNoContent.code)

    def test_list_networks_in_routinginstance(self):
        return_value = {'networks': []}
        routinginstance_id = _uuid()
        instance = self.plugin.return_value
        instance.list_networks_on_routinginstance.return_value = return_value

        path = _get_path('routinginstances/%s/networks' % routinginstance_id,
                         fmt=self.fmt)
        res = self.api.get(path)
        self.assertEqual(res.status_int, exc.HTTPOk.code)

        res = self.deserialize(res)
        self.assertIn('networks', res)

    def test_routinginstance_delete(self):
        routinginstance_id = _uuid()

        res = self.api.delete(_get_path('routinginstances',
                                        id=routinginstance_id))

        instance = self.plugin.return_value
        instance.delete_routinginstance.assert_called_with(
            mock.ANY, routinginstance_id)
        self.assertEqual(res.status_int, exc.HTTPNoContent.code)

    def _ensure_data_integrity_routingpeer(self, res, expected):
        res = self.deserialize(res)
        self.assertIn('routingpeer', res)
        res = res['routingpeer']
        self.assertEqual(res['peer'], expected['peer'])
        self.assertEqual(res['remote_as'], expected['remote_as'])
        self.assertEqual(res['extra_config'], expected['extra_config'])
        self.assertNotIn('password', res)

    def _ensure_data_integrity_routinginstance(self, res, expected):
        res = self.deserialize(res)
        self.assertIn('routinginstance', res)
        res = res['routinginstance']
        self.assertEqual(res['id'], expected['id'])
        self.assertEqual(res['nexthop'], expected['nexthop'])
        self.assertEqual(res['advertise'], expected['advertise'])
        self.assertEqual(res['discover'], expected['discover'])


class DynamicRoutingExtensionTestCaseXML(DynamicRoutingExtensionTestCase):
    fmt = 'xml'
