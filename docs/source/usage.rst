Usage
=====

Scaffolding
-----------

For the configuration of the simulations, we can point the SimBuilder to our files or we can rely on automatic selection, being this:

.. list-table::
    :header-rows: 1

    * - Input File 
      - Default Path
    * - *Netlist*
      - /path/to/project/project.netlist
    * - *Command*
      - /path/to/project/project.command 
    * - *Parameters*
      - /path/to/project/project.params 
    * - *Sweeps*
      - /path/to/project/project.sweeps 

.. code-block:: console

    $ python -m monaco -p /path/to/project -a


Basic Usage
-----------


Substitution is done with the python module Template. Variables need to be written as or ``$variable`` or ``${variable}``.

Here there is an example of an Spice netlist with variables to be injected. We can see that the variables.

.. code-block:: text

    V0 (vdd 0) vsource dc=$vdd type=dc
    I33 (0 net028 net027 vdd) INV vthp=${vthp1} vthn=${vthn1}
    I31 (0 net030 net029 vdd) INV vthp=${vthp2} vthn=${vthn2}
    I34 (0 net027 Output vdd) INV vthp=${vthp3} vthn=${vthn3}


The builder needs the path to the project containing all the files. The rest of the functionality can be configure with 
the proper modules.


.. code-block:: python

    from pathlib import Path
    from monaco import SimBuilder

    project_path = Path("/path/to/project")
    sim = SimBuilder(project_path)

    print(sim)

    # The following will be printed
    # Project Path: /path/to/project
    # Results path: /path/to/project/results
    # Netlist: /path/to/test_project/project.netlist

    # If `sim.is_verbose` is True, it also prints
    # Parametric: False
    # Has sweeps: False
    # Command: Command defined in test_project.command


Parameters
~~~~~~~~~~

Every parameter included in the definition is generated right before the command is executed. If multiple parameters need to be generated with different values they need to be defined mulitple times. For that situation, there is a shorthand syntax.

.. code-block:: text
    
    # This is a comment
    # <parameter> <function> <arg1 arg2 ...> 
    temperature uniform -10 80

    # Generate width_1 to width_10
    width_{1:10} uniform 10 50


.. code-block:: python

    import random
    CUSTOM_FUNCTIONS = {
    "span%": lambda mu, span: random.uniform(mu - (mu * span), mu + (mu * span))
    }

    sim.with_custom_fns(CUSTOM_FUNCTIONS)


.. code-block:: python

    # Rely to default path
    sim.with_parametric()

    # Provide a custom path
    sim.with_parametric("/path/to/parameteres")

    # Or provide the definitions directly
    params = """
    temperature uniform -10 80
    voltage normal 1.0 0.5
    """
    sim.with_parametric(params)

In order to guarantee reproducibility, a set of parameters can be loaded back. The builder also checks that the schema of the parameters loaded match with the definition provided to  :meth:`~monaco.SimBuilder.with_parametric`. If the schema does not match, the builder will raise a ``ValueError``.

To save a list of generated parameters the function :meth:`~monaco.SimBuilder.save_parameters` should be used. The parameters are saved into a JSON file.

.. code-block:: python

    for params, sweeps in sim.run_iterations(10)
        pass

    sim.save_parameters("/path/to/parameters.json")

.. code-block:: python

    # Load parameters from a list of dictionaries
    sim.load_parameters([
        {"temperature": -10, "voltage": 0.5}, 
        {"temperature": -10, "voltage": 1.0}, 
    ]))

    # Path to json file
    sim.load_parameters("/path/to/parameters.json")

    # Or provide a JSON string
    json_str = '''
    [{"temperature": -10, "voltage": 0.5}, {"temperature": -10, "voltage": 1.0}]
    '''
    sim.load_parameters(json_str)

After loading the parameters back, the simulations can be performed again. However, when doing so, the builder will raise a ``StopIteration`` error when all the parameters have been consumed.

.. code-block:: python

    sim.load_parameters("/path/to/parameters.json")

    try:
        for params, sweeps = sim.run_iterations(None)
            pass
    except StopIteration:
        print("All parameters have been consumed")
 
More iterations can be resumed after this by providing again the parameters definition with :meth:`~monaco.SimBuilder.with_parametric`.

Sweeps
~~~~~~

Sweeps definition follow the same syntax as parameters definition, but the functions used to generate them are different.

Sweeps can be generated with the functions ``list`` and ``range`` which behave exactly like in python code.

.. code-block:: python

    # Or provide the definitions directly
    sweeps = """
    temperature range -10 80 10
    voltage list 0.5 1.0 1.5
    """
    sim.with_sweeps(sweeps)

    # Will generate
    # -10, 0.5
    # -10, 1.0
    # -10, 1.5
    # ...

If the argument *n_repeats* is supplied to :meth:`~monaco.SimBuilder.with_sweeps`, each sweeps will be repeated that amount of times

.. code-block:: python

    # Or provide the definitions directly
    sweeps = """
    temperature range -10 80 10
    voltage list 0.5 1.0 1.5
    """
    sim.with_sweeps(sweeps, n_repeats = 3)

    # Will generate
    # -10, 0.5
    # -10, 0.5
    # -10, 0.5
    # -10, 1.0
    # -10, 1.0
    # -10, 1.0
    # ...



Running simulations
~~~~~~~~~~~~~~~~~~~

In order to run a command, it must be provided first to the simulator. This can be done with the method :meth:`~monaco.SimBuilder.with_simulator`.
If no command is provided it will raise an error when trying to run a simulation.

There are two ways of running simulations: single run or multiple iterations.
After every iteration, the builder returns the parameters and sweeps used in that iteration, if any.

.. code-block:: python

    params, sweeps = sim.run_single()

    # An identifier for the run can be provided
    params, sweeps = sim.run_single(1)


In order to run multiple iterations at the same time, the method :meth:`~monaco.SimBuilder.run_iterations` should be used. This method returns an iterator with the simulations to be run. If ``None`` is provided to :meth:`~monaco.SimBuilder.run_iterations`, it will run an infinite loop.

.. code-block:: python

    for params, sweeps in sim.run_iterations(10):
        pass
    
    # This is equivalent to:
    # for i in range(1, 10 + 1):
    #     params, sweeps = sim.run_single(i)

    for params, sweeps in sim.run_iterations(None):
        pass

    # This is equivalent to:
    # count = 1
    # while True:
    #     params, sweeps = sim.run_single(count)
    #     count += 1

Since :meth:`~monaco.SimBuilder.run_iterations` returns an iterator, each individual iteration can be performed at will:

.. code-block:: python

   simulations = sim.run_iterations(10)
   params, sweeps = next(simulations)

.. list-table::
    :header-rows: 1

    * - Variable name
      - Value to be substituted
    * - ``netlist``
      - Absolute path to the resulting netlist.
    * - ``results``
      - Absolute path to the results directory inside the project
    * - ``project_path``
      - Absolute path to the project.
    * - ``project``
      - Name of the project. Equivalent to the last directory of ``project_path``.
    * - ``iteration``
      - Iteration number if running multiple iterations or if run id is provided.

