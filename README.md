<div align='center'>
<img src="./docs/source/_static/logo.svg" width="300px">
<h3>Python aided Monte Carlo and parametric simulations
</h3>
</div>


# Introduction

This script provides functionaly to perform Monte Carlo and complex parametric simulations. It is a loosely coupled framework in which the user defines how parameters are injected into a netlist and how it is simulated.

# Dependencies

Python 3.X is required to run the script. It works entirely with the standard library so there is no need to install any dependencies.

Sphinx is needed to build the documentation.

# Motivation

This project started as a way to facitilate the process of performing complex parametric simulations in the Cadence Environment. Some of the electrical parametric simulations are so convoluted that the Cadence environment was unable to perform them. When the number of parameters gets too large of the process of generation is not defined in the environment, the solution was to generate the netlist by hand and simulate it directly.

This framework tries to solve those problems by offering a set of utilities, defined in a clean and minimal syntax, that allow the generation of complex parametric simulations where the user has total control from the start to the end.

# Usage

For a more in detail documentation of the framework, please take a look at the documentation.

To build the documentation:

```shell
$ git clone https://github.com/servinagrero/monaco.git
$ cd monaco/docs
$ make html
```

## Scaffolding

The basic usage of the library is to scaffold a project. The following command with generate the project directory and results directory. If `-a` is supplied, it will generate the template for all types of files.

```shell
python3 -m monaco -p /path/to/project -a
```

For the configuration of the simulations, we can point the SimBuilder to our files or we can rely on automatic selection, being this:

- `Netlist file`: /path/to/project/project.netlist
- `Parameters file`: /path/to/project/project.params
- `Sweeps file`: /path/to/project/project.sweeps
- `Simulation file`: /path/to/project/project.command

`Simulation file` accepts a file or a string with the command to execute

## Parameters and sweeps

As explained before, the parameters and sweeps are read from files. The syntax to define parameters is the following:

```text
# This is a comment
# param name arg1 arg2 ... argN

temp uniform 25 30
width normalvariate 50 3
```

The functions to generate the parameters and sweeps are chosen with a preference list, being `custom_fns`, `numpy.random` and lastly `random`.

Custom functions can be added in the following way:
```python
CUSTOM_FUNCTIONS = {
    "span%": lambda mu, span: random.uniform(mu - (mu * span), mu + (mu * span))
}

sim = SimBuilder(project_path)
sim.with_custom_fns(CUSTOM_FUNCTIONS)
```

# Substitution mechanism

Besides the parameters and the sweeps, there are internal variables that are substituted into every file every time a simulation is going to run, being those:

- `netlist`: Absolute path to the resulting netlist.
- `results`: Absolute path to the results directory inside the project
- `project_path`: Absolute path to the project.
- `project`: Name of the project. Equivalent to the last directory of project_path.
- `iteration`: Number of the iteration if `run_iterations` is used.

More over, we can define custom properties (called `props` internally) to define custom properties that are not generated with the parameters or the sweeps but we still want to be included.

The files used as template are executed using python's `string.Template.safe_substitute()`. This means that parameters that are wrongly typed will not get substituted and will results in errors during the execution of the simulations.

> To use a variable, it has to be written as ${variable}

# Examples

```python
import pandas as pd
from monaco import SimBuilder

project_path = Path("./test_project")
results_path = Path("./test_project/results")
sim = SimBuilder(project_path)

# To create the results directory and all files if they don't exist
sim.scaffold(create_all=True) 

# We can print a SimBuilder instance to get information
print(sim)

# Project Path: /path/to/test_project
# Results path: /path/to/test_project/results
# Netlist: /path/to/test_project/test_project.netlist

# If `sim.is_verbose` is True, it also prints
# Parametric: True
# Has sweeps: False
# Command: Command defined in test_project.command

# Moreover if `sim.is_verbose` is True,
# the output of the simulator will be shown in stdout

# Parameters can be read from default path
sim.with_parametric()

sweeps = '''
temperature list 27 80
'''
sim.with_sweeps(sweeps) # Or provided directly

params, sweeps = sim.run_single()
# The analysis of the results depends on the user
results = pd.read_csv(results_path / 'freq.csv')

# Since `SimBuilder.run_iterations` retuns an iterator, 
# we can advace the iterations when we want:
simulations = sim.run_iterations(10)
params, sweeps = next(simulations)

# Or with a for loop
for params, sweeps in simulations:
    print("Iteration finished")

# If sweeps are enabled, the builder raises an error
# when trying to run more simulations than sweeps available
try:
    params, sweeps = sim.run_single()
except StopIteration:
    print("No more sweeps to run")

# To rerun simulations we have to reset sweeps
# sim.with_sweeps(sweeps)

# The builder can also inject values into other files
# The files are given in a dictionary with the format
# Path to input : Path to output
sim.with_files(
    "/some/other/file": /foo/bar,
    # The input `netlist` points to the netlist path
    "netlist": /path/to/other/copy,
)
```

## License

MIT License

Copyright © 2021 Sergio Vinagrero

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

<div align='center'>
<a href="https://www.buymeacoffee.com/servinagrero"><img src="https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png" width="150px"></a>
</div>

