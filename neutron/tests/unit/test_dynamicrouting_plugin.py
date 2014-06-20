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
from oslo.config import cfg

from neutron.api.v2 import attributes
from neutron import context
from neutron.db import dr_agentschedulers_db as dras_db
from neutron.db import dr_db
from neutron.extensions import agent
from neutron.extensions import dr_agentscheduler as dras
from neutron.extensions import dynamic_routing
from neutron.openstack.common import importutils
from neutron.openstack.common import uuidutils
from neutron.tests.unit import test_agent_ext_plugin
from neutron.tests.unit import test_db_plugin

from webob import exc

_uuid = uuidutils.generate_uuid


class DynamicRoutingTestExtensionManager(object):

    def get_resources(self):
        attributes.RESOURCE_ATTRIBUTE_MAP.update(
            dynamic_routing.RESOURCE_ATTRIBUTE_MAP)
        attributes.RESOURCE_ATTRIBUTE_MAP.update(
            agent.RESOURCE_ATTRIBUTE_MAP)
        resources = agent.Agent.get_resources()
        resources.extend(dynamic_routing.Dynamic_routing.get_resources())
        resources.extend(dras.Dr_agentscheduler.get_resources())
        return resources

    def get_actions(self):
        return []

    def get_request_extensions(self):
        return []


class TestDynamicRoutingPlugin(dr_db.DynamicRoutingDbMixin):

    supported_extension_aliases = ["dynamic_routing"]

    def get_plugin_description(self):
        return ("Dynamic Routing Service Plugin test class that only   "
                "exposes dynamic routing functionality, without agents,"
                "nor schedulers.")


class TestDynamicRoutingSchedulerPlugin(
    dr_db.DynamicRoutingDbMixin,
    dras_db.DynamicRoutingAgentSchedulerDbMixin):

    dr_scheduler = importutils.import_object(
        cfg.CONF.dynamic_routing_scheduler_driver)

    supported_extension_aliases = ["dynamic_routing",
                                   "dynamic_routing_agent_scheduler"]

    def get_plugin_description(self):
        return ("Dynamic Routing Service Plugin test class that test   "
                "dynamic routing functionality, with scheduler.")


class DynamicRoutingEntityCreationMixin(object):

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


class DynamicRoutingBaseTestCase(DynamicRoutingEntityCreationMixin):

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

    def test_routinginstance_update_advertise_routes(self):
        with self.routinginstance() as ri:
            routinginstance_id = ri['routinginstance']['id']
            body = self._show('routinginstances', routinginstance_id)
            self.assertEqual(body['routinginstance']['advertise_routes'], [])

            data = {'routinginstance': {
                       'advertise_routes': ['12.43.5.0/24',
                                            '112.35.62.23/32']}}
            self._update('routinginstances', routinginstance_id, data)
            body = self._show('routinginstances', routinginstance_id)
            self.assertEqual(len(body['routinginstance']['advertise_routes']),
                             2)
            self.assertIn('12.43.5.0/24',
                          body['routinginstance']['advertise_routes'])
            self.assertIn('112.35.62.23/32',
                          body['routinginstance']['advertise_routes'])

            data = {'routinginstance': {
                       'advertise_routes': ['5.62.23.123/32']}}
            self._update('routinginstances', routinginstance_id, data)
            body = self._show('routinginstances', routinginstance_id)
            self.assertEqual(len(body['routinginstance']['advertise_routes']),
                             1)
            self.assertIn('5.62.23.123/32',
                          body['routinginstance']['advertise_routes'])

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


class DynamicRoutingSchedulingTestCase(
    test_agent_ext_plugin.AgentDBTestMixIn,
    DynamicRoutingBaseTestCase):

    def test_schedule_routinginstance(self):
        """Test happy path over full scheduling cycle."""
        with self.routinginstance() as ri:
            routinginstance_id = ri['routinginstance']['id']
            self._register_one_dr_agent()
            agent = self._list('agents')['agents'][0]
            data = {'agent_id': agent['id']}
            req = self.new_create_request(
                'routinginstances', data, self.fmt,
                routinginstance_id, 'dr-agents')
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPCreated.code)

            req_show = self.new_show_request(
                'routinginstances', routinginstance_id, self.fmt,
                'dr-agents')
            res = req_show.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPOk.code)
            res = self.deserialize(self.fmt, res)
            self.assertIn('agents', res)
            self.assertTrue(res['agents'][0]['id'],
                            agent['id'])

            req = self.new_delete_request('routinginstances',
                                          routinginstance_id,
                                          self.fmt,
                                          'dr-agents',
                                          agent['id'])
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPNoContent.code)

            res = req_show.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPOk.code)
            res = self.deserialize(self.fmt, res)
            self.assertIn('agents', res)
            self.assertEqual(res['agents'], [])

    def test_schedule_routinginstance_invalid_agent_type(self):
        """Test error if invalid agent.

        Test we can not schdule a routing instance to an agent different from
        a Dynamic Routing agent.
        """
        with self.routinginstance() as ri:
            routinginstance_id = ri['routinginstance']['id']
            self._register_one_l3_agent()  # Register wrong agent
            agent = self._list('agents')['agents'][0]
            data = {'agent_id': agent['id']}
            req = self.new_create_request(
                'routinginstances', data, self.fmt,
                routinginstance_id, 'dr-agents')
            res = req.get_response(self.ext_api)

            # Raises an AgentNotFound exception if the agent is invalid
            self.assertEqual(res.status_int, exc.HTTPNotFound.code)

    def test_schedule_routinginstance_two_times_same_agent(self):
        """Test error if you schedule two times same agent"""
        with self.routinginstance() as ri:
            routinginstance_id = ri['routinginstance']['id']
            self._register_one_dr_agent()
            agent = self._list('agents')['agents'][0]
            data = {'agent_id': agent['id']}
            req = self.new_create_request(
                'routinginstances', data, self.fmt,
                routinginstance_id, 'dr-agents')
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPCreated.code)

            # Second time it raises a conflict
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPConflict.code)

    def test_schedule_routinginstance_two_different_agents(self):
        """Test a routing instance can be associated to two agents."""
        with self.routinginstance() as ri:
            routinginstance_id = ri['routinginstance']['id']
            self._register_one_dr_agent(host='host1')
            self._register_one_dr_agent(host='host2')

            agent1 = self._list('agents')['agents'][0]
            data1 = {'agent_id': agent1['id']}
            req = self.new_create_request(
                'routinginstances', data1, self.fmt,
                routinginstance_id, 'dr-agents')
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPCreated.code)

            agent2 = self._list('agents')['agents'][1]
            data2 = {'agent_id': agent2['id']}
            req = self.new_create_request(
                'routinginstances', data2, self.fmt,
                routinginstance_id, 'dr-agents')
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPCreated.code)

    def test_agent_only_associated_to_a_routinginstance(self):
        """Test agent only can be associated to a routing instance."""
        with self.routinginstance(nexthop='23.23.23.0') as ri1:
            with self.routinginstance(nexthop='23.23.23.1') as ri2:
                self._register_one_dr_agent()

                agent = self._list('agents')['agents'][0]
                data = {'agent_id': agent['id']}
                req = self.new_create_request(
                    'routinginstances', data, self.fmt,
                    ri1['routinginstance']['id'], 'dr-agents')
                res = req.get_response(self.ext_api)
                self.assertEqual(res.status_int, exc.HTTPCreated.code)

                req = self.new_create_request(
                    'routinginstances', data, self.fmt,
                    ri2['routinginstance']['id'], 'dr-agents')
                res = req.get_response(self.ext_api)
                self.assertEqual(res.status_int, exc.HTTPConflict.code)

    def test_raise_disassociate_unexistent_routinginstance_binding(self):
        """Test raise an exception when disassociating no binding."""
        with self.routinginstance() as ri:
            routinginstance_id = ri['routinginstance']['id']
            req = self.new_delete_request('routinginstances',
                                          routinginstance_id,
                                          self.fmt,
                                          'dr-agents',
                                          _uuid())
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPNotFound.code)

    def test_schedule_routingpeer(self):
        """Test happy path over full scheduling cycle."""
        with self.routingpeer() as rp:
            data = {'routingpeer_id': rp['routingpeer']['id']}
            self._register_one_dr_agent()
            agent = self._list('agents')['agents'][0]
            req = self.new_create_request(
                'agents', data, self.fmt, agent['id'],
                'dr-peers')
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPCreated.code)

            req_show = self.new_show_request(
                'agents', agent['id'], self.fmt,
                'dr-peers')
            res = req_show.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPOk.code)
            res = self.deserialize(self.fmt, res)
            self.assertIn('routingpeers', res)
            self.assertTrue(res['routingpeers'][0]['peer'],
                            rp['routingpeer']['peer'])

            req_show_rev = self.new_show_request(
                'routingpeers', rp['routingpeer']['id'], self.fmt,
                'dr-agents')
            res = req_show_rev.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPOk.code)
            res = self.deserialize(self.fmt, res)
            self.assertIn('agents', res)
            self.assertTrue(res['agents'][0]['id'],
                            agent['id'])

            req = self.new_delete_request('agents', agent['id'], self.fmt,
                                          'dr-peers', rp['routingpeer']['id'])
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPNoContent.code)

            res = req_show.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPOk.code)
            res = self.deserialize(self.fmt, res)
            self.assertIn('routingpeers', res)
            self.assertEqual(res['routingpeers'], [])

            res = req_show_rev.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPOk.code)
            res = self.deserialize(self.fmt, res)
            self.assertIn('agents', res)
            self.assertEqual(res['agents'], [])

    def test_schedule_routingpeer_invalid_agent_type(self):
        """Test error if invalid agent.

        Test we can not schdule a routing peer to an agent different from
        a Dynamic Routing agent.
        """
        with self.routingpeer() as rp:
            data = {'routingpeer_id': rp['routingpeer']['id']}
            self._register_one_l3_agent()
            agent = self._list('agents')['agents'][0]
            req = self.new_create_request(
                'agents', data, self.fmt, agent['id'],
                'dr-peers')
            res = req.get_response(self.ext_api)

            # Raises an AgentNotFound exception if the agent is invalid
            self.assertEqual(res.status_int, exc.HTTPNotFound.code)

    def test_schedule_routingpeer_two_times_same_agent(self):
        """Test error if you schedule two times same agent"""
        with self.routingpeer() as rp:
            data = {'routingpeer_id': rp['routingpeer']['id']}
            self._register_one_dr_agent()
            agent = self._list('agents')['agents'][0]
            req = self.new_create_request(
                'agents', data, self.fmt, agent['id'],
                'dr-peers')
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPCreated.code)

            # Second time it raises an exception
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPConflict.code)

    def test_schedule_routingpeer_two_different_agents(self):
        """Test is valid to configure routingpeers to two agents."""
        with self.routingpeer() as rp:
            data = {'routingpeer_id': rp['routingpeer']['id']}
            self._register_one_dr_agent(host='host1')
            self._register_one_dr_agent(host='host2')

            agent1 = self._list('agents')['agents'][0]
            req = self.new_create_request(
                'agents', data, self.fmt, agent1['id'],
                'dr-peers')
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPCreated.code)

            agent2 = self._list('agents')['agents'][1]
            req = self.new_create_request(
                'agents', data, self.fmt, agent2['id'],
                'dr-peers')
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPCreated.code)

    def test_schedule_two_routingpeers_same_agent(self):
        """Test is valid to an agent host two routingpeers."""
        with self.routingpeer() as rp1:
            with self.routingpeer(peer='12.12.2.32') as rp2:
                data1 = {'routingpeer_id': rp1['routingpeer']['id']}
                data2 = {'routingpeer_id': rp2['routingpeer']['id']}
                self._register_one_dr_agent(host='host1')
                agent = self._list('agents')['agents'][0]

                req = self.new_create_request(
                    'agents', data1, self.fmt, agent['id'],
                    'dr-peers')
                res = req.get_response(self.ext_api)
                self.assertEqual(res.status_int, exc.HTTPCreated.code)

                req = self.new_create_request(
                    'agents', data2, self.fmt, agent['id'],
                    'dr-peers')
                res = req.get_response(self.ext_api)
                self.assertEqual(res.status_int, exc.HTTPCreated.code)

    def test_delete_unexistent_binding_between_agent_and_routingpeer(self):
        """Test raise exception when delete unknown binding."""
        self._register_one_dr_agent(host='host1')
        agent = self._list('agents')['agents'][0]
        req = self.new_delete_request('agents', agent['id'], self.fmt,
                                      'dr-peers', _uuid())
        res = req.get_response(self.ext_api)
        self.assertEqual(res.status_int, exc.HTTPNotFound.code)

    def test_create_binding_no_agent(self):
        """Test raise exception when no DR agent registered."""
        with self.routingpeer() as rp:
            data = {'routingpeer_id': rp['routingpeer']['id']}
            req = self.new_create_request(
                'agents', data, self.fmt, _uuid(),
                'dr-peers')
            res = req.get_response(self.ext_api)
            self.assertEqual(res.status_int, exc.HTTPNotFound.code)


class DynamicRoutingPluginTests(test_db_plugin.NeutronDbPluginV2TestCase,
                                DynamicRoutingBaseTestCase):

    def setUp(self, plugin=None, ext_mgr=None, service_plugins=None):
        if not plugin:
            plugin = ('neutron.tests.unit.test_dynamicrouting_plugin.'
                      'TestDynamicRoutingPlugin')
        ext_mgr = ext_mgr or DynamicRoutingTestExtensionManager()
        super(DynamicRoutingPluginTests, self).setUp(
            plugin=plugin, ext_mgr=ext_mgr, service_plugins=service_plugins)


class DynamicRoutingPluginSchedulerTests(
    test_db_plugin.NeutronDbPluginV2TestCase,
    DynamicRoutingSchedulingTestCase):

    def setUp(self, plugin=None, ext_mgr=None, service_plugins=None):
        if not plugin:
            plugin = ('neutron.tests.unit.test_dynamicrouting_plugin.'
                      'TestDynamicRoutingSchedulerPlugin')
        ext_mgr = ext_mgr or DynamicRoutingTestExtensionManager()
        super(DynamicRoutingPluginSchedulerTests, self).setUp(
            plugin=plugin, ext_mgr=ext_mgr, service_plugins=service_plugins)
        self.adminContext = context.get_admin_context()
