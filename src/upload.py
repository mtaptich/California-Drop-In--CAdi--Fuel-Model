import os
import pandas as pd
from sqlalchemy import create_engine
import string, random

class Methods:
	def __init__(s, database='CABiomass', User='Mike', host='localhost'):
		# Start server 
		s.start_server(database, User, host)

	def start_server(s, database, User, host):
		# save database
		s.database = database

		# save cursor
		s.cur  = create_engine('postgresql://%s@%s:5432/%s' % (User, host,database))

	def pg_post(s, SQLcommand):
		connection = s.cur.connect()
		connection.execute(SQLcommand);
		connection.close()

	def pg_df(s, SQLcommand):
		
		return pd.read_sql(SQLcommand, s.cur)


	def df_pg(s, dataframe, table_name, if_exists='replace'):
		
		return dataframe.to_sql(table_name, s.cur, if_exists=if_exists)


	def downstream_logistics(s, dataframe, scenario='s5', DLtable='sjk_ca_feedstocks_intermodal_pipeline'):
		# Create connection
		connection = s.cur.connect()

		# Create a randomly-generated and temporary table
		table_random_downstream = "temp_"+''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(20))
		
		# Send solution to server 
		dataframe.columns = ['origin', 'destination', 'gas', 'diesel']
		s.df_pg(dataframe, table_random_downstream);

		# combine solution results with OD matrix
		SQLcommand = """DROP TABLE IF EXISTS %(downstream_logistics_scenario)s; \
			CREATE TABLE %(downstream_logistics_scenario)s AS \
			SELECT a.*, b.gas, b.diesel \
			FROM %(DLtable)s a \
			RIGHT JOIN %(table_random_downstream)s b  \
			ON a.origin = b.origin AND a.destination = b.destination """ %{'downstream_logistics_scenario': scenario+"_sjk_optimal", 'DLtable': DLtable, 'table_random_downstream': table_random_downstream}
	
		connection.execute(SQLcommand)

		# Drop the temporary table
		connection.execute('DROP TABLE IF EXISTS %s;' % table_random_downstream);

		# Close connection
		connection.close();

	def supply_chain(s, dataframe, scenario='s5', if_exists='replace'):
		# Create connection
		connection = s.cur.connect()

		# Create a randomly-generated and temporary table
		table_random = "temp_"+''.join(random.choice(string.ascii_lowercase + string.digits) for _ in range(20))

		# Send solution to server 
		s.df_pg(dataframe, table_random);

		# combine solution results with OD matrix
		SQLcommand = """DROP TABLE IF EXISTS %(logistics_scenario)s; \
			CREATE TABLE %(logistics_scenario)s AS \
			SELECT a.county, a.refinery, a.terminal, a.cropres, a.forestres, a.scrapwood, a.m2g, a.ft, a.pg, a.pd ,a.mt_gas_at_refinery, a.mt_diesel_at_refinery, a.mt_gas_to_terminal, a.mt_diesel_to_terminal, CASE WHEN a.cropres > 0 THEN g.node_geom ELSE NULL END AS crop_geom, CASE WHEN a.cropres > 0 THEN b.the_geom ELSE NULL END AS upstream_geom_crop, b.km AS upstream_crop_km, b.km_road AS upstream_crop_km_road, b.km_rail AS upstream_crop_km_rail, CASE WHEN a.forestres > 0 OR a.scrapwood > 0 THEN g.node_geom ELSE NULL END AS wood_geom, CASE WHEN a.forestres > 0 OR a.scrapwood > 0 THEN c.the_geom ELSE NULL END AS upstream_geom_wood, c.km AS upstream_wood_km, c.km_road AS upstream_wood_km_road, c.km_rail AS upstream_wood_km_rail, d.the_geom AS refinery_geom, d.type AS refinery_type, e.the_geom AS downsteam_geom, e.km AS downstream_km, e.km_road AS downstream_km_road, e.km_rail AS downstream_km_rail, (e.km - e.km_rail - e.km_road) AS downstream_km_pipleline, f.the_geom as terminal_geom, f.million_gals_gasoline_2012 AS gas_capcity, f.million_gals_diesel_2012 AS diesel_capacity  \
			FROM %(table_random)s a \
			JOIN cij_ca_feedstocks_intermodal_crop b  \
			ON b.origin = a.county AND a.refinery = b.destination \
			JOIN cij_ca_feedstocks_intermodal_forest c \
			ON a.county=c.origin AND a.refinery=c.destination \
			JOIN facility_locations_about_cities d \
			ON a.refinery=d.id \
			JOIN sjk_ca_feedstocks_intermodal_pipeline e \
			ON a.refinery=e.origin AND a.terminal=e.destination \
			JOIN downstream_locations_california f \
			ON a.terminal=f.id \
			JOIN (SELECT * FROM scenario_cocc WHERE type='cultivated') g \
			ON a.county=CAST(g.id AS integer) \
			JOIN (SELECT * FROM scenario_cocc WHERE type='forested') h \
			ON a.county=CAST(h.id AS integer)""" %{'logistics_scenario': scenario+"_supply_chain", 'table_random': table_random}

		connection.execute(SQLcommand)

		# Drop the temporary table
		connection.execute('DROP TABLE IF EXISTS %s;' % table_random);

		# Update emissions handling... hard-coded for now.
		SQLcommand = """ALTER TABLE %(logistics_scenario)s ADD COLUMN handling_emissions double precision; \
		UPDATE %(logistics_scenario)s SET handling_emissions = cropres*%(cropres_ef)s + forestres*%(forestres_ef)s + scrapwood*%(scrapwood_ef)s """ % {'logistics_scenario': scenario+"_supply_chain",'cropres_ef': 24.5, 'forestres_ef': 14.5, 'scrapwood_ef': 33}
		connection.execute(SQLcommand);

		SQLcommand = """ALTER TABLE %(logistics_scenario)s ADD COLUMN handling_emissions_cropres double precision; \
		UPDATE %(logistics_scenario)s SET handling_emissions_cropres = cropres*%(cropres_ef)s""" % {'logistics_scenario': scenario+"_supply_chain",'cropres_ef': 24.5, 'forestres_ef': 14.5, 'scrapwood_ef': 33}
		connection.execute(SQLcommand);

		SQLcommand = """ALTER TABLE %(logistics_scenario)s ADD COLUMN handling_emissions_forestres double precision; \
		UPDATE %(logistics_scenario)s SET handling_emissions_forestres =  forestres*%(forestres_ef)s """ % {'logistics_scenario': scenario+"_supply_chain",'cropres_ef': 24.5, 'forestres_ef': 14.5, 'scrapwood_ef': 33}
		connection.execute(SQLcommand);

		SQLcommand = """ALTER TABLE %(logistics_scenario)s ADD COLUMN handling_emissions_scrapwood double precision; \
		UPDATE %(logistics_scenario)s SET handling_emissions_scrapwood =  scrapwood*%(scrapwood_ef)s """ % {'logistics_scenario': scenario+"_supply_chain",'cropres_ef': 24.5, 'forestres_ef': 14.5, 'scrapwood_ef': 33}
		connection.execute(SQLcommand);



		# Update upstream logistics... hard-coded for now.
		SQLcommand = """ALTER TABLE %(logistics_scenario)s ADD COLUMN upstream_transport_emissions double precision; \
		UPDATE %(logistics_scenario)s SET upstream_transport_emissions = CASE WHEN cropres > 0 THEN upstream_crop_km_road*%(road_ef)s*cropres + upstream_crop_km_rail*%(rail_ef)s*cropres  ELSE 0 END + CASE WHEN forestres > 0 OR scrapwood > 0 THEN upstream_wood_km_road*%(road_ef)s*(forestres + scrapwood) + upstream_wood_km_rail*%(rail_ef)s*(forestres + scrapwood) ELSE 0 END  """ % {'logistics_scenario': scenario+"_supply_chain",'road_ef': 0.13, 'rail_ef': 0.02}
		connection.execute(SQLcommand);

		SQLcommand = """ALTER TABLE %(logistics_scenario)s ADD COLUMN upstream_transport_emissions_cropres double precision; \
		UPDATE %(logistics_scenario)s SET upstream_transport_emissions_cropres = CASE WHEN cropres > 0 THEN upstream_crop_km_road*%(road_ef)s*cropres + upstream_crop_km_rail*%(rail_ef)s*cropres  ELSE 0 END  """ % {'logistics_scenario': scenario+"_supply_chain",'road_ef': 0.13, 'rail_ef': 0.02}
		connection.execute(SQLcommand);

		SQLcommand = """ALTER TABLE %(logistics_scenario)s ADD COLUMN upstream_transport_emissions_woody double precision; \
		UPDATE %(logistics_scenario)s SET upstream_transport_emissions_woody =  CASE WHEN forestres > 0 OR scrapwood > 0 THEN upstream_wood_km_road*%(road_ef)s*(forestres + scrapwood) + upstream_wood_km_rail*%(rail_ef)s*(forestres + scrapwood) ELSE 0 END  """ % {'logistics_scenario': scenario+"_supply_chain",'road_ef': 0.13, 'rail_ef': 0.02}
		connection.execute(SQLcommand);



		# Update capital... hard-coded for now.
		SQLcommand = """ALTER TABLE %(logistics_scenario)s ADD COLUMN capital_emissions double precision; \
		UPDATE %(logistics_scenario)s SET capital_emissions = 0; """ % {'logistics_scenario': scenario+"_supply_chain"}
		connection.execute(SQLcommand);



		# Update processing... hard-coded for now.
		SQLcommand = """ALTER TABLE %(logistics_scenario)s ADD COLUMN processing_emissions double precision; \
		UPDATE %(logistics_scenario)s SET processing_emissions = m2g*%(m2g_ef)s + ft*%(ft_ef)s + pg*%(pg_ef)s + pd*%(pd_ef)s""" % {'logistics_scenario': scenario+"_supply_chain",'m2g_ef': -700, 'ft_ef': -265, 'pg_ef': 792, 'pd_ef': 722}
		connection.execute(SQLcommand);

		SQLcommand = """ALTER TABLE %(logistics_scenario)s ADD COLUMN processing_emissions_m2g double precision; \
		UPDATE %(logistics_scenario)s SET processing_emissions_m2g = m2g*%(m2g_ef)s """ % {'logistics_scenario': scenario+"_supply_chain",'m2g_ef': -700, 'ft_ef': -265, 'pg_ef': 792, 'pd_ef': 722}
		connection.execute(SQLcommand);

		SQLcommand = """ALTER TABLE %(logistics_scenario)s ADD COLUMN processing_emissions_ft double precision; \
		UPDATE %(logistics_scenario)s SET processing_emissions_ft = ft*%(ft_ef)s """ % {'logistics_scenario': scenario+"_supply_chain",'m2g_ef': -700, 'ft_ef': -265, 'pg_ef': 792, 'pd_ef': 722}
		connection.execute(SQLcommand);

		SQLcommand = """ALTER TABLE %(logistics_scenario)s ADD COLUMN processing_emissions_pg double precision; \
		UPDATE %(logistics_scenario)s SET processing_emissions_pg =  pg*%(pg_ef)s """ % {'logistics_scenario': scenario+"_supply_chain",'m2g_ef': -700, 'ft_ef': -265, 'pg_ef': 792, 'pd_ef': 722}
		connection.execute(SQLcommand);

		SQLcommand = """ALTER TABLE %(logistics_scenario)s ADD COLUMN processing_emissions_pd double precision; \
		UPDATE %(logistics_scenario)s SET processing_emissions_pd =  pd*%(pd_ef)s""" % {'logistics_scenario': scenario+"_supply_chain",'m2g_ef': -700, 'ft_ef': -265, 'pg_ef': 792, 'pd_ef': 722}
		connection.execute(SQLcommand);



		# Update downstream logistics... hard-coded for now.
		SQLcommand = """ALTER TABLE %(logistics_scenario)s ADD COLUMN downstream_transport_emissions double precision; \
		UPDATE %(logistics_scenario)s SET downstream_transport_emissions = downstream_km_road*%(road_ef)s*(mt_gas_to_terminal + mt_diesel_to_terminal) + downstream_km_rail*%(rail_ef)s*(mt_gas_to_terminal + mt_diesel_to_terminal) + downstream_km_pipleline*%(pipe_ef)s*(mt_gas_to_terminal + mt_diesel_to_terminal) """ % {'logistics_scenario': scenario+"_supply_chain",'road_ef': 0.13, 'rail_ef': 0.02, 'pipe_ef': 0.0084}
		connection.execute(SQLcommand);

		SQLcommand = """ALTER TABLE %(logistics_scenario)s ADD COLUMN downstream_transport_emissions_gas double precision; \
		UPDATE %(logistics_scenario)s SET downstream_transport_emissions_gas = downstream_km_road*%(road_ef)s*(mt_gas_to_terminal) + downstream_km_rail*%(rail_ef)s*(mt_gas_to_terminal) + downstream_km_pipleline*%(pipe_ef)s*(mt_gas_to_terminal) """ % {'logistics_scenario': scenario+"_supply_chain",'road_ef': 0.13, 'rail_ef': 0.02, 'pipe_ef': 0.0084}
		connection.execute(SQLcommand);

		SQLcommand = """ALTER TABLE %(logistics_scenario)s ADD COLUMN downstream_transport_emissions_diesel double precision; \
		UPDATE %(logistics_scenario)s SET downstream_transport_emissions_diesel = downstream_km_road*%(road_ef)s*(mt_diesel_to_terminal) + downstream_km_rail*%(rail_ef)s*(mt_diesel_to_terminal) + downstream_km_pipleline*%(pipe_ef)s*(mt_diesel_to_terminal) """ % {'logistics_scenario': scenario+"_supply_chain",'road_ef': 0.13, 'rail_ef': 0.02, 'pipe_ef': 0.0084}
		connection.execute(SQLcommand);



		# Update total.
		SQLcommand = """ALTER TABLE %(logistics_scenario)s ADD COLUMN total_emissions double precision; \
		UPDATE %(logistics_scenario)s SET total_emissions = handling_emissions + upstream_transport_emissions + capital_emissions +  processing_emissions + downstream_transport_emissions; """ % {'logistics_scenario': scenario+"_supply_chain"}
		connection.execute(SQLcommand);


		# Close connection
		connection.close();



	



	