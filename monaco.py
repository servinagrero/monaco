#!/usr/bin/env python3

import shlex
import argparse
import json
import random
import numpy as np
from datetime import datetime
from pathlib import Path
from string import Template
from subprocess import DEVNULL, run
from threading import Thread
from typing import Callable, Dict, Union, List, Generator

__version__ = "0.1.0"
__author__ = "Sergio Vinagrero <servinagrero@gmail.com>"
__license__ = "MIT License"
__url__ = "https://github.com/servinagrero/Monaco-cadence"

"""
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

CUSTOM_FUNCTIONS = {
    "span%": lambda mu, span: random.uniform(mu - (mu * span), mu + (mu * span))
}
"""

Dir = Union[str, Path]
ParamDef = Dict[str, Union[List[float], List[str]]]
Param = Dict[str, Union[float, str]]


def files_find_ext(ext: str, dir: Dir) -> List[Path]:
    """List files in a directory with that match a extension.

    Args:
        ext (str): Extension of the file to be found.
        dir (Dir): Directory to look for files

    Yields:
        List of files in the directory
    """
    return list(Path(dir).resolve().glob(r"*." + ext))


def files_list(dir: Dir, *args, **kwargs) -> List[Path]:
    """List all regular files in a directory

    Args:
        dir (Dir): Directory to look for files

    Returns:
        List[Path]: List of files in the directory
    """
    return [p for p in Path(dir).iterdir(*args, **kwargs) if p.is_file()]


def files_filter_ext(files: List[Path], ext: str) -> List[Path]:
    """Filter files from a list matching a extension

    Args:
        files (List[Path]): List of files
        ext (str): Extension to filter

    Returns:
        List[Path]: List of files that have the extension
    """
    return [f for f in files if f.suffix == ext]


def params_generate(params_def: ParamDef, custom_fns: Dict[str, Callable]) -> Param:
    """Generate the random params.

    Args:
        params_def (ParamDef): Definition of the parameters.

    Returns:
        ParamDef: Names and values of the parameters.s

    Raises:
      OSError: The parameters file cannot be opened.
      AttributeError: The name of the function is not found.
    """
    custom_fns = custom_fns if custom_fns else {}
    params = {}

    for param, info in params_def.items():
        fns = []
        fns.append(custom_fns.get(info["function"], None))
        fns.append(getattr(np.random, info["function"], None))
        fns.append(getattr(random, info["function"], None))
        if not any(fns):
            raise ValueError(f"Function {info['function']} does not exist")

        fn = next(fn for fn in fns if fn is not None)
        params[param] = fn(*info["values"])

    return params


def params_parse(params_file: Path) -> ParamDef:
    """Extract parameter definitions from a file.

    The parameters are read from the file in the following way:

    ```
    \# This is a comment\n
    name function arg1 arg2 ... argN\n
    temp uniform 20 30\n
    ```

    The name of the parameter has to be the same one than in the template files but without the $.
    The function is chosen with a list in the following order: [custom_fns, numpy.random, random]
    The argumens are given in a list separated by spaces.

    Args:
        params_file (Path): Path to the parameter definition file.

    Raises:
      OSError: The parameters file cannot be opened.
      AttributeError: The name of the function is not found.

    Returns:
        ParamDef: Names and values of the parameters.
    """
    data: ParamDef = {}

    def cast_value(value: str):
        "Cast a value to a float. In case it is not possible, return it as string"
        try:
            return float(value)
        except ValueError:
            return value

    with open(params_file, "r+") as params_fd:
        content = params_fd.readlines()
        valid_lines = filter(lambda l: not l.strip().startswith("#"), content)

        for line in valid_lines:
            param, function, *vals = line.split(" ")
            values = [cast_value(v) for v in vals]
            data[param] = {"function": function, "values": values}

    return data


def params_parse(sweeps_file: Path) -> ParamDef:
    raise NotImplementedError


def sweeps_generate(sweeps_def: ParamDef, custom_fns: Dict[str, Callable]) -> Param:
    raise NotImplementedError


def template_subs(raw: Union[Template, str], *args: List[Param]) -> str:
    """Substitute a template with a list of arguments.

    If the argument is a string it gets converted into a Template.

    Args:
        raw (Union[Template, str]): Template to substitute
        args (List[ParamDef]): List of parameter definitions

    Returns:
        str: The template substituted
    """
    if isinstance(raw, str):
        template = Template(raw)
    else:
        template = raw

    params: Dict[str, float] = {}
    for arg in args:
        params.update(arg)
    return template.safe_substitute(params)


def template_exec(in_file: Path, out_file: Path, *args: List[Param]) -> None:
    """Read a template from a file, execute it and write the result to a file.

    The template is executed using `template_subs`.

    Args:
        in_file (Path): Path to the template file.
        out_file (Path): Path to save the executed template.
        *args (List[Param]): List of dictionaries with the names and values to be substituted.

    Raises:
      OSError: The template file could not be found

    Returns:
        None
    """
    with open(in_file, "r") as template_path, open(out_file, "w+") as result:
        substituted = template_subs(template_path.read(), *args)
        result.write(substituted)


def command_run(cmd: str, is_verbose: bool = False) -> None:
    """Execute a given command using subprocess.run

    Args:
        cmd (str): Shell command to execute.
        is_verbose (bool): Whether to show the output of the command.
    """
    if is_verbose:
        run(shlex.split(cmd), check=True)
    else:
        run(shlex.split(cmd), check=True, stdout=DEVNULL, stderr=DEVNULL)


################################################################################


class SimBuilder:
    """
    Attributes:
        project_path (str): Path to the project containing the files
        project_name (str): Basename of the project_path
        results_path (str): Path to the directory to store resuts
    """

    def __init__(self, project_path: Path = None):
        self.project_path = Path(project_path).resolve()
        self.project_name = self.project_path.name
        self.results_path = self.project_path / "results"

        self.__netlist = None
        self.__netlist_out = self.project_path / f"{self.project_name}_net_out"

        self.__custom_fns = {}
        self.__is_parametric, self.__is_sweeps = False, False
        self.__params_def, self.__sweeps_def = {}, {}

        self.__is_ocean = False
        self.__cadence_project, self.__ocean_script = None, None

        self.__cmd = None
        self.is_verbose = False

    def __repr__(self) -> str:
        """Pretty print the SimBuiler"""
        txt = (
            f"Project Path: {self.project_path}\n"
            f"Results path: {self.results_path}\n"
            f"Netlist: {self.__netlist}\n"
            f"Ocean: {self.__is_ocean}\n"
            f"Parametric: {self.__is_parametric}\n"
            f"Has sweeps: {self.__is_sweeps}"
        )
        return txt

    def scaffold(self, create_all: bool) -> None:
        """Create the project structure

        Args:
            create_all (bool): If True, create all single files, else
                create only project and results directory

        Returns:
            None
        """
        self.project_path.mkdir(parents=True, exist_ok=True)
        self.results_path.mkdir(parents=True, exist_ok=True)

        if not create_all:
            return

        def default_or_create(file: Path, ext: str):
            """Check if the file exists, otherwise create the a default one"""
            if file is not None and file.exists():
                return file
            try:
                return files_find_ext(ext, self.project_path)[0]
            except IndexError:
                return self.project_path / f"{self.project_name}.{ext}"

        netlist_file = default_or_create(self.__netlist, "netlist")
        ocean_file = default_or_create(self.__ocean_script, "ocn")
        files = [netlist_file, ocean_file]

        if not self.__params_def:
            params_file = self.project_path / f"{self.project_name}.params"
            files.append(params_file)

        if not self.__sweeps_def:
            sweeps_file = self.project_path / f"{self.project_name}.sweeps"
            files.append(sweeps_file)

        # If the file exists, touch does nothing
        for file in files:
            file.touch(mode=0o666, exist_ok=True)

        self.__netlist = netlist_file
        self.__ocean_script = ocean_file
        self.__params_def = {}
        self.__sweeps_def = {}

    def with_netlist(self, netlist_path: Path) -> None:
        """Set the netlist to use

        Args:
            netlist_path (Path): Path to the netlist file.

        TODO: If the method `with_simulator` is called first, then the netlist
        points to the previous netlist.
        """
        if not Path(netlist_path).exists():
            raise ValueError(f"Netlist {netlist_path} does not exist")
        self.__netlist = netlist_path

    def with_custom_fns(self, custom_fns: Dict[str, Callable]) -> None:
        """Assign custom functions to generate sweeps and parameters
        Params:
            custom_fns (Dict[str, Callable]): Ditionary containing the functions definitions

        Returns:
            Nones
        """
        self.__custom_fns = custom_fns

    def with_simulator(self, command: Union[Path, str] = None) -> None:
        """Assign the simulatior command

        Special variables are substituted to the command, including:
            {netlist}, {results}, {project}, {project_path}

        Args:
            command (Union[Path, str]): String with the command to execute
                or a path to a file whose contents is the command.
        """

        if self.__is_ocean:
            print("Ocean is already defined. It will be used to run simulations")
            return

        if command is None:
            try:
                cmd = files_find_ext("command", self.project_path)[0]
            except IndexError:
                raise ValueError(
                    "Please provide a simulator command or a file containing the script."
                )
        else:
            if Path(command).exists():
                with open(command, "r") as cmd_fd:
                    lines = [l.strip() for l in cmd_fd.readlines()]
                    cmd = " ".join(lines)
            else:
                cmd = command

        internals = {
            "{netlist}": str(self.__netlist_out),
            "{results}": str(self.results_path),
            "{project}": str(self.project_name),
            "{project_path}": str(self.project_path),
        }
        for key, value in internals.items():
            cmd = cmd.replace(key, value)

        self.__cmd = cmd

    def with_parametric(self, params_path: Path = None) -> None:
        """
        Returns:
            None
        """
        if params_path is None:
            try:
                params_file = files_find_ext("params", self.project_path)[0]
            except IndexError:
                raise ValueError("Parameters template file does not exist.")
        else:
            if Path(params_path).exists():
                params_file = params_path
            else:
                raise ValueError(f"Parameters file {params_path} does not exist")

        self.__is_parametric = True
        self.__params_def = params_parse(params_file)

    def with_sweeps(self, sweeps_path: Path = None):
        """ """
        self.__is_sweeps = True
        if sweeps_paths is None:
            try:
                sweeps_file = files_find_ext("sweeps", self.project_path)[0]
            except IndexError:
                raise ValueError("Sweeps template file does not exist.")
        else:
            params_file = sweeps_path

        self.__sweeps_def = sweeps_parse(sweeps_file)

    def with_ocean(self, cadence_project: Path, *, ocean_script: Path = None):
        """
        To use ocean the netlist has to be copied into the cadence project path.
        We can create a temporary dir, copy the whole project and do it there,
        to allow for parallel simulations.

        TODO: Read .ocn file
        """
        self.__is_ocean = True
        if not Path(cadence_project).exists():
            raise ValueError(f"{cadence_project} does not exist.")

        self.__netlist_out = Path(
            self.__cadence_project, "spectre/schematic/netlist/netlist"
        ).resolve()

        if ocean_script is None:
            try:
                self.__ocean_script = files_find_ext("ocn", self.project_path)[0]
            except IndexError:
                raise ValueError("Ocean script file does not exist.")
        else:
            if Path(ocean_script).exists():
                self.__ocean_script = ocean_script
            else:
                raise ValueError(f"Ocean script {ocean_script} does not exist.")

        self.__ocean_out = Path(self.project_path, f"ocn_{self.project_name}")
        self.__cmd = f"ocean -nograph < {self.__ocean_script}"

    def run_iterations(self, iterations: int) -> Generator:
        """
        Args:
            iterations (int): Number of iterations to run

        Returns:
            Generator: Generator for every single simulation.

        TODO: What happends if run_single takes a lot of time? or if there are errors and it throws?
        """
        if self.__cmd is None:
            raise ValueError("Simulation command has not been defined")

        for i in range(1, iterations + 1):
            yield self.run_single(i)

    def run_single(self, iteration: int = None):
        """Run a single simulation

        Args:
            iteration (int): Index of the iteration if multiple are to be run.

        Returns:
            (dict, dict): Parameters and sweeps for the run
        """
        if self.__cmd is None:
            raise ValueError("Simulation command has not been defined")

        subs_dict = {}
        if self.__is_parametric:
            params = params_generate(self.__params_def, self.__custom_fns)
            subs_dict.update(params)
        else:
            params = None

        if self.__is_sweeps:
            sweeps = sweeps_generate(self.__sweeps_def, self.__custom_fns)
            subs_dict.update(sweeps)
        else:
            sweeps = None

        template_exec(self.__netlist, self.__netlist_out, subs_dict)

        if self.__is_ocean:
            template_exec(
                self.__ocean_script,
                self.__ocean_out,
                subs_dict,
                {"{netlist}": self.__netlist_out, "{iteration}": iteration},
            )

        cmd = self.__cmd

        if iteration is not None:
            cmd = self.__cmd.replace("{iteration}", str(iteration))

        command_run(cmd, self.is_verbose)

        return params, sweeps


if __name__ == "__main__":
    import sys
    import argparse

    parser = argparse.ArgumentParser(
        description="""
    Scaffold a project for simulations
    """
    )
    parser.add_argument("-p", "--project", help="Path to project", required=True)
    parser.add_argument(
        "-a", "--all", help="Create all type of files", action="store_true"
    )
    args = parser.parse_args()
    if Path(args.project).absolute() == Path(__file__).parent.absolute():
        print("Project path has to be different from current path")
        sys.exit(1)
    SimBuilder(args.project).scaffold(create_all=args.all)
