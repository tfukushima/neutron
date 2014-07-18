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
import mock
from webob import exc

from neutron.extensions import dynamic_routing
from neutron.openstack.common import uuidutils
from neutron.plugins.common import constants
from neutron.tests.unit import test_api_v2
from neutron.tests.unit import test_api_v2_extension

_uuid = uuidutils.generate_uuid
_get_path = test_api_v2._get_path


class DynamicRoutingExtensionTestCase(test_api_v2_extension.ExtensionTestCase):

    fmt = 'json'

    def setUp(self):
        super(DynamicRoutingExtensionTestCase, self).setUp()
        plural_mappings = {'routingpeer': 'routingpeers'}
        self._setUpExtension(
            'neutron.extensions.dynamic_routing.DynamicRoutingPluginBase',
            constants.DYNAMIC_ROUTING, dynamic_routing.RESOURCE_ATTRIBUTE_MAP,
            dynamic_routing.Dynamic_routing, '',
            plural_mappings=plural_mappings)

    def test_routingpeer_list(self):
        routingpeer_id = _uuid()
        return_value = [{'routingpeer_id': routingpeer_id,
                         'peer': '34.23.10.1',
                         'protocol': 'bgp',
                         'configurations': {
                             'remote-as': '34500',
                             'password': 'dummy_pass'}}]

        instance = self.plugin.return_value
        instance.get_routingpeers.return_value = return_value

        res = self.api.get(_get_path('routingpeers', fmt=self.fmt))
        self.assertEqual(res.status_int, exc.HTTPOk.code)

        instance.get_routingpeers.assert_called_with(mock.ANY,
                                                     fields=mock.ANY,
                                                     filters=mock.ANY)

    def test_routingpeer_show(self):
        routingpeer_id = _uuid()
        return_value = {'routingpeer_id': routingpeer_id,
                        'peer': '34.23.10.1',
                        'protocol': 'bgp',
                        'configurations': {
                            'remote-as': '34500',
                            'password': 'dummy_pass'}}

        instance = self.plugin.return_value
        instance.get_routingpeer.return_value = return_value

        res = self.api.get(
            _get_path('routingpeers/{0}'.format(routingpeer_id)))
        self.assertEqual(res.status_int, exc.HTTPOk.code)

        instance.get_routingpeer.assert_called_with(
            mock.ANY, unicode(routingpeer_id), fields=mock.ANY)


class DynamicRoutingExtensionTestCaseXML(DynamicRoutingExtensionTestCase):
    fmt = 'xml'
