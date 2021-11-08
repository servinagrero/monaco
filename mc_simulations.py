#!/usr/bin/env python3

import argparse
import json
import random
from datetime import datetime
from pathlib import Path
from string import Template
from subprocess import DEVNULL, run
from threading import Thread
from typing import Callable, Dict, Union, List

__version__ = "0.1.0"
__author__ = "Sergio Vinagrero <servinagrero@gmail.com>"
__license__ = "MIT License"
__url__ = "https://github.com/servinagrero/Monaco-cadence"

help_msg = """
Generate MC or parametric simulations for Cadence.

The configuration, called `props` in the source code, is stored in a JSON file.

To execute a given project, the following values are mandatory:
- project: Path to the project to find the necesary files.
- iterations: Number of iterations to execute.

Any other values added to the props can be later used in the callback function.

The parameters are read from a file with extension `.params`.
The parameters are defined in the file as follows

# This is a comment
name function arg1 arg2 ... argN
temp uniform 20 30

The name of the functions have to be the same as the ones found in the random module.

After every simulation, a custom callback function can be executed.
The signature of the fuction is `callback_fn(props, *args, **kwargs)`.
"""


def find_file_ext(name: str, files: List[str]) -> Union[str, None]:
    """Find a file with a given extension.

    The file is looked for by using `endswith()` on every path and with `lower()` to be case insesitive.

    Args:
      name: Extionsion of the file to be found.

      files: List of files to search.

    Throws:
      None

    Returns:
      Path to the file or None if the file is not present
    """
    return next(filter(lambda f: f.name.lower().endswith(name), files), None)


def generate_parameters(params_def: Dict) -> Dict:
    """Generate the random parameters.

    Args:
      params_file: Path to the parameter definition file.

    Throws:
      OSError: The parameters file cannot be opened.
      AttributeError: The name of the function is not found.

    Returns:
      Names and values of the parameters.
    """
    params = {}

    for param, info in params_def.items():
        if info["function"] == "span%":
            fn = lambda mu, span: random.uniform(mu - (mu * span), mu + (mu * span))
        else:
            fn = getattr(random, info["function"])
        params[param] = fn(*info["values"])

    return params


def parse_parameters(params_file: Path) -> Dict:
    """Extract parameter definitions from a file.

    The parameters are read from the file in the following way:

    ```
    # This is a comment
    name function arg1 arg2 ... argN
    temp uniform 20 30
    ```

    The name of the parameter has to be the same one than in the template files but without the $.
    The function has to be the same than the ones from the random python library. The names are: 'uniform', 'normalvariate', 'gammavariate', 'betavariate'.
    The argumens are given in a list separated by spaces.

    Args:
      params_file: Path to the parameter definition file.

    Throws:
      OSError: The parameters file cannot be opened.
      AttributeError: The name of the function is not found.

    Returns:
      Names and values of the parameters.
    """
    data = {}

    content = open(params_file, "r+").readlines()
    content = map(lambda l: l.strip(), content)
    content = filter(lambda l: not l.startswith("#"), content)

    for line in content:
        param, function, *vals = line.split(" ")
        vals = [float(v) for v in vals]
        data[param] = {"function": function, "values": vals}

    return data


def execute_template(in_file: Path, out_file: Path, *args: List[Dict]) -> None:
    """Execute a template and write to a file.

    The template is executed with safe_substitute to allow to pass more
    parameters than necesary whithout throwing an error.

    Args:
      in_file: Path to the template file.

      out_file: Path to save the executed template.

      args: List of dictionaries with the names and values to be substituted.

    Throws:
      OSError: The template file could not be found

    Returns:
      None
    """
    params = {}
    for arg in args:
        params.update(arg)

    with open(in_file, "r") as template_path, open(out_file, "w+") as result:
        template = Template(template_path.read())
        substituted = template.safe_substitute(params)
        result.write(substituted)


def run_simulation(props: Dict) -> None:
    """Run a simulation with the given configuration.

    Args:
      props: Dictionary containing all the necesary information to run a simulation, plus the values added by the user, if any.

    Throws:
      OSError:

    Returns:
      Parameters generated for the run and other configuration options.
    """
    project_name = Path(props["project"]).name
    base_path = Path(props["project"])
    files = list(base_path.glob("*"))

    # Results file generation
    results_dir = base_path / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    # Netlist generation
    netlist_in = find_file_ext(".netlist", files)
    if not netlist_in:
        raise ValueError("Netlist template file does not exist.")

    ocean_file = find_file_ext(".ocn", files)

    if ocean_file:
        # TODO: Allow for the customization of netlist_out. Maybe force the user to write the file in the config.json
        netlist_out = Path(
            props["cadence_project"], "spectre/schematic/netlist/netlist"
        ).resolve()

        exec_file = Path("/tmp", f"simulation_{project_name}.ocn").resolve()
        execute_template(ocean_file, exec_file, props, props["params"])

        cmd = f"ocean -nograph < {exec_file}"
    else:
        netlist_out = base_path / "netlist"
        cmd = find_file_ext("cmdSimulation", files)
        if not cmd:
            raise ValueError("cmdSimulation file does not exist.")

        cmd = open(cmd, "r").readlines()
        cmd = Template(" ".join(map(lambda l: l.strip(), cmd)))
        cmd = cmd.safe_substitute(props)

    execute_template(netlist_in, netlist_out, props["params"])

    if props.get("verbose", False):
        run(cmd, shell=True, check=True)
    else:
        run(cmd, shell=True, check=True, stdout=DEVNULL, stderr=DEVNULL)


def mc_simulations(
    props: Dict, callback_fn=Callable[[list, Dict], None], *args, **kwargs
) -> None:
    """Generate and run the MC simulations.

    Args:
      props: Dictionary containing the configuration for a project.

      callback_fn: User defined function to be executed after every simulation.
        Before calling this function. props is updated with two more keys: `parameters` with the names and values of the parameters generated for that iteration and `options`, for any other configuration done during the generation of the simulation. Options is mainly used when using ocean.

    Throws:
      OSError: The project path does not exist.

    Returns:
      None
    """
    base_path = Path(props["project"])
    if not base_path.exists():
        raise ValueError("Project does not exist")

    files = list(base_path.glob("*"))

    params_file = find_file_ext(".params", files)
    if not params_file:
        raise ValueError("Parameters template file does not exist.")

    # TODO: Check if there is parametric simulations
    params_def = parse_parameters(params_file)

    for epoch in range(1, props["iterations"] + 1):
        timestamp = datetime.now().strftime("%d-%m-%Y %H:%M:%S")
        print(f"[{timestamp}] {base_path.name} - Running simulation ", end="")
        print(f'[{epoch}/{props["iterations"]}]')

        props["epoch"] = epoch
        props["params"] = generate_parameters(params_def)

        run_simulation(props)
        if callback_fn:
            callback_fn(props, *args, **kwargs)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=help_msg, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument(
        "-c", "--config", required=True, help="Path to the JSON configuration file."
    )
    parser.add_argument(
        "-v",
        "--verbose",
        default=False,
        action="store_true",
        help="Whether to show the output of each simulation.",
    )
    parser.add_argument(
        "-p",
        "--parallel",
        default=False,
        action="store_true",
        help="Whether to execute multiple simulations in parallel.",
    )
    args = vars(parser.parse_args())

    config_path = Path(args["config"]).resolve()
    config = json.load(open(config_path, "r"))
    if not isinstance(config, list):
        config = [config]

    threads = []
    for props in config:
        props["verbose"] = args["verbose"]
        if args["parallel"]:
            t = Thread(target=mc_simulations, args=(props,))
            threads.append(t)

            for t in threads:
                t.start()
                t.join()
        else:
            mc_simulations(props)
