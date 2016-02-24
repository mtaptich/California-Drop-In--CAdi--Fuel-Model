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
