<h1>California Drop-In (CAdi) Fuel Model</h1>
<p>California Drop-In (CAdi) fuel model calculates the environmental impacts associated with large-scale deployment of second-generation transportation fuels in California.</p>

<h2>Usage</h2>
```python
from src.model import FacilityLocationOptimizer
s = FacilityLocationOptimizer(scenario='EMISSIONS', r_cap=6800, m_units=180, config_path=None)
```

<p><em>Initiates the class that optimizes the sourcing, siting, and distribution processes under various objectives and scenarios.</em></p>

<p>
	<ul>
		<li><b>scenario</b> : <em>Default: EMISSIONS</em><br>EMISSIONS sets the objective to minimize emissions; GASOLINE sets the objective to maximize the output of gasoline; DIESEL sets the objective to maximize diesel; and, FUEL sets the objective to maximize fuel.</li>
		<li><b>r_cap</b> : <em>Default: 6800</em><br>r_cap sets the maximum feedstock input (mt/yr) per unit refinery process. 6800 mt/yr is roughly equivalent to 0.5 MMg/yr fuel output.</li>
		<li><b>m_units</b> : <em>Default: 180</em><br>m_units sets the maximum number of refinery units. 180 * 6800 mt/yr is roughly equivalent to 90 MMg/yr fuel output.</li>
		<li><b>config_path</b> : <em>Default: None</em><br>config_path containts a set of base assumptions and file paths used in the scenario.</li>
	</ul>
</p>

<br>
```python 
s.predict(method='MILP')
```

<p><em>Runs the optimization of the upstream, midstream, and downstream supply-chain.</em></p>

<p>
	<ul>
		<li><b>method</b> : <em>Default: MILP</em><br>MILP sets the solver to a mixed-integer linear programming solution; IP sets the solver to an integer linear programming solution; otherwise, the solver is set to solve the relaxation of the problem.</li>
	</ul>
</p>

<br>
```python
from src import save
save.supply_network(s)
```

<p><em>Saves the solution of the model and preforms post-processing on the data.</em></p>



<h2>Model Dependencies</h2>
<h3> Install core dependencies </h3>
<p>The core of the CAdi model is written in Python 2.7 and links either directly or through third-party packages to optimization and geospatial tools. The model solves for a set of process-based and supply chain policies for meeting energy and greenhouse gas management objectives. Such policies include where to source material feedstocks, locate refineries, select fuel conversion pathways, and sell to markets. The model includes a number of base scenarios modelled by our researcg group at UC Berkeley. The core model is required to run these scenarios. Additional extentions to the model allow for original scenarios to be buil; this portion requires an object-relational database management system called PostgreSQL (<a href='src/PostgreSQL'>See more</a>). <p>

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




