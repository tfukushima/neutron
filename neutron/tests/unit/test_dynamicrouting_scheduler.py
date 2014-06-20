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
import mock
import time

from oslo.config import cfg

from neutron.api.v2 import attributes
from neutron import context as n_context
from neutron.extensions import agent
from neutron.extensions import dr_agentscheduler as dras
from neutron.extensions import dynamic_routing
from neutron import manager
from neutron.openstack.common import uuidutils
from neutron.tests.unit import test_agent_ext_plugin
from neutron.tests.unit import test_db_plugin
from neutron.tests.unit import test_dynamicrouting_plugin


_uuid = uuidutils.generate_uuid


DB_PLUGIN_KLASS = ('neutron.services.dynamic_routing.plugin.'
                   'DynamicRoutingPlugin')


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


class DynamicRoutingSchedulerTestCase(
    test_db_plugin.NeutronDbPluginV2TestCase,
    test_agent_ext_plugin.AgentDBTestMixIn,
    test_dynamicrouting_plugin.DynamicRoutingEntityCreationMixin):

    def setUp(self):
        ext_mgr = DynamicRoutingTestExtensionManager()
        super(DynamicRoutingSchedulerTestCase, self).setUp(
            plugin=DB_PLUGIN_KLASS, ext_mgr=ext_mgr)
        self.adminContext = n_context.get_admin_context()
        self.plugin = manager.NeutronManager.get_plugin()

    def test_autoschedule_routingpeer(self):
        with self.routingpeer() as rp:
            self._register_one_dr_agent(host='host1')
            auto_scheduled = self.plugin.auto_schedule_routingpeers(
                self.adminContext, 'host1')
            self.assertTrue(auto_scheduled)
            r = self.plugin.list_active_sync_routingpeers_on_dr_agent(
                self.adminContext, 'host1')

            # assert routingpeer has automatically scheduled to
            # agent
            self.assertEqual(r[0], rp['routingpeer']['id'])

    def test_autoschedule_routinginstance(self):
        with self.routinginstance() as ri:
            self._register_one_dr_agent(host='host1')
            auto_scheduled = self.plugin.auto_schedule_routinginstances(
                self.adminContext, 'host1')
            self.assertTrue(auto_scheduled)
            r = self.plugin.list_active_sync_routinginstances_on_dr_agent(
                self.adminContext, 'host1')

            # assert routinginstance has automatically scheduled to
            # agent
            self.assertEqual(r[0], ri['routinginstance']['id'])

    def test_autoschedule_routingpeer_when_no_agent(self):
        """Assert autoschedule returns false if not agent."""
        with self.routinginstance():
            auto_scheduled = self.plugin.auto_schedule_routingpeers(
                self.adminContext, 'host1')
            self.assertFalse(auto_scheduled)

    def test_autoschedule_routinginstance_when_no_agent(self):
        """Assert autoschedule returns false if not agent."""
        with self.routinginstance():
            auto_scheduled = self.plugin.auto_schedule_routinginstances(
                self.adminContext, 'host1')
            self.assertFalse(auto_scheduled)

    def test_autoschedule_routingpeer_two_agents(self):
        """Test autoscheduling when there are two agents.

        Peer only will be auto scheduled to the first agent that has
        requested synchrony.
        """
        with self.routingpeer() as rp:
            self._register_one_dr_agent(host='host1')
            self._register_one_dr_agent(host='host2')
            auto_scheduled = self.plugin.auto_schedule_routingpeers(
                self.adminContext, 'host1')
            self.assertTrue(auto_scheduled)
            auto_scheduled = self.plugin.auto_schedule_routingpeers(
                self.adminContext, 'host2')
            self.assertFalse(auto_scheduled)

            # assert routingpeer has automatically scheduled to
            # agent
            r = self.plugin.list_active_sync_routingpeers_on_dr_agent(
                self.adminContext, 'host1')
            self.assertEqual(len(r), 1)
            self.assertEqual(r[0], rp['routingpeer']['id'])

            # Second agent won't have these peers
            r = self.plugin.list_active_sync_routingpeers_on_dr_agent(
                self.adminContext, 'host2')
            self.assertEqual(len(r), 0)

    def test_autoschedule_routinginstance_two_agents(self):
        """Test autoscheduling when there are two agents.

        Peer only will be auto scheduled to the first agent that has
        requested synchrony.
        """
        with self.routinginstance() as ri:
            self._register_one_dr_agent(host='host1')
            self._register_one_dr_agent(host='host2')
            auto_scheduled = self.plugin.auto_schedule_routinginstances(
                self.adminContext, 'host1')
            self.assertTrue(auto_scheduled)
            auto_scheduled = self.plugin.auto_schedule_routinginstances(
                self.adminContext, 'host2')
            self.assertFalse(auto_scheduled)

            # assert routingpeer has automatically scheduled to
            # agent
            r = self.plugin.list_active_sync_routinginstances_on_dr_agent(
                self.adminContext, 'host1')
            self.assertEqual(len(r), 1)
            self.assertEqual(r[0], ri['routinginstance']['id'])

            # Second agent won't have these peers
            r = self.plugin.list_active_sync_routinginstances_on_dr_agent(
                self.adminContext, 'host2')
            self.assertEqual(len(r), 0)

    def test_behaviour_when_agent_down(self):
        """Check nothing will raise an exception if agent down."""
        with contextlib.nested(
                self.routingpeer(),
                self.routinginstance(),
                mock.patch.object(self.plugin, 'agent_notifiers',
                                  return_value=[])):

            self._register_one_dr_agent(host='host1')
            agents = self.plugin.get_agents(self.adminContext)
            agent_id = agents[0]['id']
            update = {'agent': {'admin_state_up': False}}
            self.plugin.update_agent(self.adminContext,
                                     agent_id,
                                     update)

            auto_si = self.plugin.auto_schedule_routinginstances(
                 self.adminContext, 'host1')
            self.assertFalse(auto_si)

            auto_sp = self.plugin.auto_schedule_routingpeers(
                 self.adminContext, 'host1')
            self.assertFalse(auto_sp)

            ri = self.plugin.list_active_sync_routinginstances_on_dr_agent(
                     self.adminContext, 'host1')
            self.assertEqual(len(ri), 0)

            rp = self.plugin.list_active_sync_routingpeers_on_dr_agent(
                     self.adminContext, 'host1')
            self.assertEqual(len(rp), 0)

    def test_behaviour_heartbeat_timeout(self):
        """Check nothing will raise an exception if heartbeat is timeout."""
        cfg.CONF.set_override('agent_down_time', 1)
        self._register_one_dr_agent(host='host1')

        # That will force the agent dr set as down
        time.sleep(2)
        with self.routinginstance():
            auto_sp = self.plugin.auto_schedule_routingpeers(
                 self.adminContext, 'host1')
            self.assertFalse(auto_sp)

        with self.routinginstance():
            auto_sp = self.plugin.auto_schedule_routinginstances(
                 self.adminContext, 'host1')
            self.assertFalse(auto_sp)

    def test_agent_can_be_autoasociated_to_two_routingpeers(self):
        """Calling autoschedule two peers can be associated"""
        with contextlib.nested(
                 self.routingpeer(peer='12.43.84.33'),
                 self.routingpeer(peer='34.29.43.124')):
            self._register_one_dr_agent(host='host1')
            auto_sp = self.plugin.auto_schedule_routingpeers(
                 self.adminContext, 'host1')
            self.assertTrue(auto_sp)
            rp = self.plugin.list_active_sync_routingpeers_on_dr_agent(
                     self.adminContext, 'host1')
            self.assertEqual(len(rp), 2)

    def test_agent_cannot_be_autoasociated_to_two_routinginstances(self):
        """An agent only can be associated to a routing instance.

        If you create two routing instances and call auto_schedule,
        the agent only will take as associated one of them, even
        it returns True
        """
        with contextlib.nested(
                 self.routinginstance(nexthop='12.43.84.33'),
                 self.routinginstance(nexthop='34.29.43.124')):
            self._register_one_dr_agent(host='host1')
            auto_sp = self.plugin.auto_schedule_routinginstances(
                 self.adminContext, 'host1')
            self.assertTrue(auto_sp)
            rp = self.plugin.list_active_sync_routinginstances_on_dr_agent(
                     self.adminContext, 'host1')
            self.assertEqual(len(rp), 1)

    def test_agent_return_false_when_anything_to_schedule(self):
        """The autoschedule returns false when there is nothing to schedule."""
        self._register_one_dr_agent(host='host1')
        auto_sp = self.plugin.auto_schedule_routinginstances(
                      self.adminContext, 'host1')
        self.assertFalse(auto_sp)

        auto_sp = self.plugin.auto_schedule_routingpeers(
                      self.adminContext, 'host1')
        self.assertFalse(auto_sp)
