"""Private user-taught single-shot USSD offers."""
from alembic import op
import sqlalchemy as sa
revision='0002'
down_revision='0001'
branch_labels=None
depends_on=None

def upgrade():
    with op.batch_alter_table('offers') as batch:
        batch.add_column(sa.Column('owner_user_id',sa.BigInteger(),nullable=True))
        batch.add_column(sa.Column('learn_key',sa.String(160),nullable=True))
        batch.create_unique_constraint('uq_offer_learn_key',['learn_key'])

def downgrade():
    with op.batch_alter_table('offers') as batch:
        batch.drop_constraint('uq_offer_learn_key',type_='unique')
        batch.drop_column('learn_key')
        batch.drop_column('owner_user_id')
