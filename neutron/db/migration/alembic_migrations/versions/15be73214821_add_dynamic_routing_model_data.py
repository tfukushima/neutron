# Copyright 2014 OpenStack Foundation
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.
#

"""add dynamic routing model data

Revision ID: 15be73214821
Revises: 5589aa32bf80
Create Date: 2014-07-02 13:16:08.604175

"""

# revision identifiers, used by Alembic.
revision = '15be73214821'
down_revision = '5589aa32bf80'

# Change to ['*'] if this migration applies to all plugins
migration_for_plugins = ['*']

from alembic import op
import sqlalchemy as sa

from neutron.db import migration


def upgrade(active_plugins=None, options=None):
    if not migration.should_run(active_plugins, migration_for_plugins):
        return

    op.create_table(
        'routingpeers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('extra_config', sa.String(length=4096), nullable=False),
        sa.Column('password', sa.String(length=255), nullable=True),
        sa.Column('peer', sa.String(length=64), nullable=False),
        sa.Column('remote_as', sa.Integer, nullable=False),
        sa.Column('tenant_id', sa.String(length=255), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('peer'),
    )

    op.create_table(
        'routingpeeragentbindings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('routingpeer_id', sa.String(length=36), nullable=False),
        sa.Column('agent_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['routingpeer_id'],
                                ['routingpeers.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'],
                                ['agents.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'routinginstances',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('nexthop', sa.String(length=64), nullable=True),
        sa.Column('tenant_id', sa.String(length=255), nullable=False),
        sa.Column('advertise', sa.Boolean, default=False, nullable=False),
        sa.Column('discover', sa.Boolean, default=False, nullable=False),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'routinginstanceagentbindings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('routinginstance_id', sa.String(length=36), nullable=False),
        sa.Column('agent_id', sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('agent_id'),
        sa.ForeignKeyConstraint(['routinginstance_id'],
                                ['routinginstances.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['agent_id'],
                                ['agents.id'],
                                ondelete='CASCADE'),
    )

    op.create_table(
        'routinginstancenetworkbindings',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('routinginstance_id', sa.String(length=36), nullable=False),
        sa.Column('network_id', sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['routinginstance_id'],
                                ['routinginstances.id'],
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['network_id'],
                                ['networks.id'],
                                ondelete='CASCADE'),
    )

    op.create_table(
        'advertiseroutes',
        sa.Column('advertise_route', sa.String(length=64), nullable=False),
        sa.Column('routinginstance_id', sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(['routinginstance_id'],
                                ['routinginstances.id'],
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('advertise_route', 'routinginstance_id')
    )


def downgrade(active_plugins=None, options=None):
    if not migration.should_run(active_plugins, migration_for_plugins):
        return

    op.drop_table('advertiseroutes')
    op.drop_table('routinginstancenetworkbindings')
    op.drop_table('routinginstanceagentbindings')
    op.drop_table('routinginstances')
    op.drop_table('routingpeeragentbindings')
    op.drop_table('routingpeers')
