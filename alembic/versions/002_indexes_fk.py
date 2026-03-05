"""Add composite indexes and update foreign key constraints

Revision ID: 002_indexes_fk
Revises: 001_initial
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '002_indexes_fk'
down_revision = '001_initial'
branch_labels = None
depends_on = None


def upgrade():
    # Drop existing foreign key constraints
    op.drop_constraint('fk_property_source', 'properties', type_='foreignkey')
    op.drop_constraint('fk_pricehistory_property', 'property_price_history', type_='foreignkey')
    op.drop_constraint('fk_alert_property', 'alerts', type_='foreignkey')
    op.drop_constraint('fk_alert_savedsearch', 'alerts', type_='foreignkey')
    op.drop_constraint('fk_enrichment_property', 'llm_enrichments', type_='foreignkey')
    
    # Recreate with CASCADE/SET NULL
    op.create_foreign_key('fk_property_source', 'properties', 'sources', ['source_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_pricehistory_property', 'property_price_history', 'properties', ['property_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_alert_property', 'alerts', 'properties', ['property_id'], ['id'], ondelete='SET NULL')
    op.create_foreign_key('fk_alert_savedsearch', 'alerts', 'saved_searches', ['saved_search_id'], ['id'], ondelete='CASCADE')
    op.create_foreign_key('fk_enrichment_property', 'llm_enrichments', 'properties', ['property_id'], ['id'], ondelete='CASCADE')
    
    # Add composite indexes for common query patterns
    op.create_index('ix_properties_status_price_county', 'properties', ['status', 'price', 'county'])
    op.create_index('ix_properties_county_type_beds', 'properties', ['county', 'property_type', 'bedrooms'])
    op.create_index('ix_sold_properties_county_date_price', 'sold_properties', ['county', 'sale_date', 'price'])


def downgrade():
    # Drop composite indexes
    op.drop_index('ix_properties_status_price_county', table_name='properties')
    op.drop_index('ix_properties_county_type_beds', table_name='properties')
    op.drop_index('ix_sold_properties_county_date_price', table_name='sold_properties')
    
    # Revert foreign keys to original
    op.drop_constraint('fk_property_source', 'properties', type_='foreignkey')
    op.drop_constraint('fk_pricehistory_property', 'property_price_history', type_='foreignkey')
    op.drop_constraint('fk_alert_property', 'alerts', type_='foreignkey')
    op.drop_constraint('fk_alert_savedsearch', 'alerts', type_='foreignkey')
    op.drop_constraint('fk_enrichment_property', 'llm_enrichments', type_='foreignkey')
    
    op.create_foreign_key('fk_property_source', 'properties', 'sources', ['source_id'], ['id'])
    op.create_foreign_key('fk_pricehistory_property', 'property_price_history', 'properties', ['property_id'], ['id'])
    op.create_foreign_key('fk_alert_property', 'alerts', 'properties', ['property_id'], ['id'])
    op.create_foreign_key('fk_alert_savedsearch', 'alerts', 'saved_searches', ['saved_search_id'], ['id'])
    op.create_foreign_key('fk_enrichment_property', 'llm_enrichments', 'properties', ['property_id'], ['id'])
