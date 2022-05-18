<div align='center'>
<img src="./assets/logo.svg" width="300px">
<h3>Python aided Monte Carlo and Parametric simulations in Cadence
</h3>
</div>


# Introduction

This script provides functionaly to perform MC and Parametric simulations using Cadence.

This script was created to bypass the limitations of cadence and to allow for more flexibility when performing MC simulations.

# Dependencies

Python 3.X is required to run the script. It works entirely with the standard library so there is no need to install any more dependencies.

Sphinx is needed to build the documentation.

# Usage

This project started as a way to ease the process of generating parametrics simulations to overcome the limitations of Cadence, mainly the generation of Monte Carlo simulations with great number of parameters while also lacking the statistics model files.

The main pipeline of the framework is the following:

Netlist -> Subs(Netlist, [Ocean], Parameters, Sweeps, Props) -> Simulator(Output) -> Results


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
- `Ocean script`: /path/to/project/project.ocn

`Simulation file` accepts a file or a string with the command to execute

## Parameters and sweeps

As explained before, the parameters and sweeps are read from files. The syntax to define parameters is the following:

```text
# param name arg1 arg2 ... argN
# This is a comment

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

### WIP

Generation of sweeps

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
# Parametric: True
# Has sweeps: False

sim.with_parametric() # We select parametric analysis
sim.with_sweeps() # And also sweep generation

params, sweeps = sim.run_single()
results = pd.read_csv(results_path / 'freq.csv')
# We can do what we want with the results

# Since `SimBuilder.run_iterations` retuns an iterator, we can advace the iterations when we want:
simulations = sim.run_iterations(10)
params, sweeps = next(simulations)

# Or with a for loop
for params, sweeps in simulations:
    print("Iteration finished")

# For advance usage, we can rely on Ocean to launch our simulations
# Cadence_project points to the directory inside Cadence where the files are stored
sim.with_ocean(cadence_project)
```

## License

MIT License

Copyright © 2021 Sergio Vinagrero

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
