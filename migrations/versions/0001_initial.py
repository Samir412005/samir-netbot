"""Initial MVP schema, immutable v1 metadata snapshot."""
from alembic import op
import sqlalchemy as sa
revision='0001'
down_revision=None
branch_labels=None
depends_on=None

def upgrade():
    op.create_table('users',sa.Column('id',sa.BigInteger(),primary_key=True,autoincrement=False),sa.Column('language',sa.String(2),nullable=False),sa.Column('points',sa.Integer(),nullable=False),sa.Column('banned',sa.Boolean(),nullable=False),sa.Column('referrer',sa.BigInteger(),nullable=True))
    op.create_table('gifts',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('user_id',sa.BigInteger(),sa.ForeignKey('users.id'),nullable=False),sa.Column('day',sa.Integer(),nullable=False),sa.Column('claimed_at',sa.BigInteger(),nullable=False),sa.UniqueConstraint('user_id','day',name='uq_gift_user_day'))
    op.create_table('pair_codes',sa.Column('code_hash',sa.String(64),primary_key=True),sa.Column('user_id',sa.BigInteger(),sa.ForeignKey('users.id'),nullable=False),sa.Column('expires_at',sa.BigInteger(),nullable=False))
    op.create_table('devices',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('user_id',sa.BigInteger(),sa.ForeignKey('users.id'),nullable=False),sa.Column('name',sa.String(80),nullable=False),sa.Column('token_hash',sa.String(64),unique=True,nullable=False),sa.Column('last_seen',sa.BigInteger(),nullable=False),sa.Column('revoked',sa.Boolean(),nullable=False))
    op.create_table('offers',sa.Column('bid',sa.Integer(),primary_key=True),sa.Column('name',sa.String(100),nullable=False),sa.Column('operator',sa.String(50),nullable=False),sa.Column('size',sa.String(50),nullable=False),sa.Column('price_points',sa.Integer(),nullable=False),sa.Column('category',sa.String(20),nullable=False),sa.Column('ussd',sa.String(160),nullable=False),sa.Column('success_regex',sa.String(200),nullable=False),sa.Column('enabled',sa.Boolean(),nullable=False))
    op.create_table('commands',sa.Column('id',sa.String(36),primary_key=True),sa.Column('user_id',sa.BigInteger(),sa.ForeignKey('users.id'),nullable=False),sa.Column('device_id',sa.Integer(),sa.ForeignKey('devices.id'),nullable=False),sa.Column('offer_id',sa.Integer(),sa.ForeignKey('offers.bid'),nullable=False),sa.Column('idempotency_key',sa.String(100),nullable=False),sa.Column('state',sa.String(16),nullable=False),sa.Column('ussd',sa.String(160),nullable=False),sa.Column('offer_name',sa.String(100),nullable=False),sa.Column('success_regex',sa.String(200),nullable=False),sa.Column('created_at',sa.BigInteger(),nullable=False),sa.Column('expires_at',sa.BigInteger(),nullable=False),sa.Column('response',sa.Text(),nullable=False),sa.Column('reason',sa.String(200),nullable=False),sa.Column('notified',sa.Boolean(),nullable=False),sa.UniqueConstraint('user_id','idempotency_key',name='uq_command_user_key'))
    op.create_table('interests',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('user_id',sa.BigInteger(),sa.ForeignKey('users.id'),nullable=False),sa.Column('feature',sa.String(30),nullable=False),sa.UniqueConstraint('user_id','feature',name='uq_interest'))
    op.create_table('audit',sa.Column('id',sa.Integer(),primary_key=True),sa.Column('user_id',sa.BigInteger(),nullable=False),sa.Column('event',sa.String(80),nullable=False),sa.Column('at',sa.BigInteger(),nullable=False))

def downgrade():
    for name in ('audit','interests','commands','offers','devices','pair_codes','gifts','users'): op.drop_table(name)
