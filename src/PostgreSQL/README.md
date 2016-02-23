<h2> (OPTIONAL) Install PostgreSQL</h2>
<h4> Windows</h4>
<p>1. Use <a href='http://www.postgresql.org/download/windows/'>the official installer</a> to download PostgreSQL with pgAdminIII. </p>

<p>2. Install dependencies for PostGIS:
	<ul>
		<li><a href='https://pypi.python.org/pypi/Shapely#downloads'>Shapely</a></li>
		<li><a href='https://pypi.python.org/pypi/Fiona'>Fiona</a></li>
		<li><a href='https://www.qgis.org/en/site/forusers/download.html#'>Gdal and QGIS (64-bit)</a></li>
		<li><a href='https://github.com/proj4js/proj4js/releases'>PROJ.4</a></li>
	</ul>
</p>

<p>3. Set the PostgreSQL path: 
	<ol>
		<li>Open Environment Variable GUI located on your PC: <br> <em>Properties > Advanced Systems Settings > Environment Variable</em></li>
		<li>Click "Edit" under path</li>
		<li>Add to end of "Variable value" (Make sure to update version number): <br> <em>;C:\Program Files\PostgreSQL\{{VERSION NUMBER}}\bin</em></li>
	</ol>
</p>

<p>4. Set PostgreSQL username and password:
	<ol>
		<li>Edit <em>pg_hba.conf</em> to allow trust authorization temporarily (see, C:\Program Files\PostgreSQL\{{VERSION NUMBER}}\data)</li>
		<li>Modify these two lines, and change "md5" to "trust": <br>
			<pre><code>host    all             all             127.0.0.1/32            md5
host    all             all             ::1/128                 md5</code></pre>
		</li>
	</ol>
</p>

<p>5. Open the <em>Command Prompt</em> and update your user password: <br>
	<ol>
		<li><pre><code>psql -U postgres</code></pre></li>
		<li>Once you are in an active postgreSQL terminal: <br>
			<pre><code>CREATE USER "{{YOUR USERNAME}}" WITH PASSWORD '{{PASSWORD}}'; </code></pre> 
			<pre><code>ALTER USER "{{YOUR USERNAME}}" WITH SUPERUSER; </code></pre>
		</li>
	</ol>
</p>

<p>6. (Optional, recommended for security reasons) Change the postgres user's password: <br>
	<ol>
		<li><pre><code>\password postgres</code></pre></li>
		<li><pre><code>{{NEW PASSWORD}} </code></pre> </li>
	</ol>

</p>

<p>7. Change "trust" back to "md5" in the <em>pg_hba.conf</em> file. </p>


<p>8. Create a database named test_database: <br>
	<pre><code>createdb test_database
psql test_database -c "create extension postgis"</code></pre>
(If you logged in, created the extensions, and quit correctly, you have a working database!)
</p>

<p>9. For routing capabilities, install <a href='http://pgrouting.org/docs/1.x/install.html'>PgRouting</a> and add the extension to your database. </p>

