<h1 align='center'>MONACO CADENCE</h1>

<h3 align='center'>Python aided Monte Carlo and Parametric simulations in Cadence
</h3>

# Introduction

This script provides functionaly to perform MC and Parametric simulations using Cadence.

This script was created to bypass the limitations of cadence and to allow for more flexibility when performing MC simulations.

# Dependencies

Python 3.X is required to run the script. It works entirely with the standard library so there is no need to install any more dependencies.

# Usage

The simulations are configured in a JSON file, which in the code is referred as `props`. Multiple projects can be defined in the same props file.

For every project, there needs to be at least two parameters:

- `project`: Path to the project containing the files.

- `iterations`: Number of simulations to be executed.

```json
{ "project": "/path/to/project", "iterations": 10 }
```

Other values can be added to the props for later use, such as follows:

```json
{
  "project": "/path/to/project",
  "iterations": 10,
  "cadence_project": "/path/to/cadence/project",
  "results": "results.csv",
  "counter_file": "counter.csv"
}
```

The parameters to be generated for each iteration are read from `<project>/name.params`. The name of the file is not important but the suffix is. The parameters file should have the following

```text
# This is a comment
# param name arg1 arg2 ... argN

temp uniform 25 30
width normalvariate 50 3
```

> The name of the functions has to be the same as the functions contained in the random module.

The files used as template are executed using python's `string.Template.safe_execute()`.

If the file `<project>/name.ocn` exists, ocean is used to run the simulation. This file is also executed as a template and written to `<project>/simulation.ocn`. If the file is not found,  the file `cmdsimulation` (case insensitive) is read and it's contents are used to execute each simulation.

This functions allow the use of a user defined callback that is executed after every simulation.
The callback has the following signature:

```python
callback_fn(props: Dict, *args, **kwargs) -> None
```

This props dictionary is the original one with two new fields:

- parameters: Dictionary containing the names and values of the parameters generated for that iteration.
- options: Dictionary containing other configurations used for ocean.

## License

MIT License

Copyright © 2021 Sergio Vinagrero

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the “Software”), to deal in the Software without restriction, including without limitation the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
