<h1>California Drop-In (CAdi) Fuel Model</h1>
<p>California Drop-In (CAdi) fuel model calculates the environmental impacts associated with large-scale deployment of second-generation transportation fuels in California.</p>

<h2>Usage</h2>
<p><pre><code><b>FacilityLocationOptimizer</b>(<em>scenario='EMISSIONS', r_cap=6800, m_units=180, config_path=None</em>)</code></pre></p>

<p>Optimize the sourcing, siting, and distribution processes under various objectives and scenarios. </p>

<p><u>Parameters</u>:</p>
<p>
	<ul>
		<li><b>scenario</b> : <em>Default: EMISSIONS</em><br>EMISSIONS sets the objective to minimize emissions; GASOLINE sets the objective to maximize the output of gasoline; DIESEL sets the objective to maximize diesel; and, FUEL sets the objective to maximize fuel.</li>
		<li><b>r_cap</b> : <em>Default: 6800</em><br>r_cap sets the maximum feedstock input (mt/yr) per unit refinery process. 6800 mt/yr is roughly equivalent to 0.5 MMg/yr fuel output.</li>
		<li><b>m_units</b> : <em>Default: 180</em><br>m_units sets the maximum number of refinery units. 180 * 6800 mt/yr is roughly equivalent to 90 MMg/yr fuel output.</li>
		<li><b>config_path</b> : <em>Default: None</em><br>config_path containts a set of base assumptions and file paths used in the scenario.</li>
	</ul>
</p>

<h2>Model Dependencies</h2>
<h3> Install dependencies </h3>
<p>The core of the CAdi model is written in Python 2.7 and links either directly or through third-party packages to optimization and geospatial tools. The model solves for a set of process-based and supply chain policies for meeting energy and greenhouse gas management objectives. Such policies include where to source material feedstocks, locate refineries, select fuel conversion pathways, and sell to markets. The model includes a number of base scenarios modelled by our researcg group at UC Berkeley. The core model is required to run these scenarios. Additional extentions to the model allow for original scenarios to be buil; this portion requires an object-relational database management system called PostgreSQL. <p>

<p>Below are the dependencies for the core model:</p>
<p>
	<ul>
		<li><a href='https://www.python.org/download/releases/2.7/'>Python 2.7</a> (Windows Only)</li>
		<li><a href='http://www.gnu.org/software/glpk/glpk.html'>GLPK (GNU Linear Programming Kit)</a></li>
		<li><a href='http://docs.scipy.org/doc/numpy-1.10.1/user/install.html'>Numpy</a></li>
		<li><a href='http://pandas.pydata.org/pandas-docs/stable/install.html'>Pandas</a></li>
		<li><a href='http://cvxopt.org/download/'>cvxopt</a> <em>(BUILD_GLPK: set this variable to 1 to enable support for the linear programming solver GLPK.)</em></li>
		<li><a href='http://www.sqlalchemy.org/download.html'>sqlalchemy</a></li>
	</ul>
</p>


<h3> (OPTIONAL) Install PostgreSQL</h3>
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



