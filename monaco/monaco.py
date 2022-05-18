#!/usr/bin/env python3

import random
import shlex
import json
from itertools import product
from pathlib import Path
from string import Template
from subprocess import DEVNULL, run
from typing import (
    Callable,
    Dict,
    Generator,
    List,
    Tuple,
    Union,
    Any,
    Optional,
    TypedDict,
)

import numpy as np

__version__ = "0.1.0"
__author__ = "Sergio Vinagrero <servinagrero@gmail.com>"
__license__ = "MIT License"
__url__ = "https://github.com/servinagrero/Monaco-cadence"

"""
Generate MC or parametric simulations for Cadence.
"""


class FunctionDef(TypedDict):
    function: str
    values: List[Union[int, float, str]]


PathStr = str | Path
ParameterDef = Dict[str, FunctionDef]
Parameter = Dict[str, Union[float, str]]


def files_find_ext(ext: str, files: PathStr | List[Path]) -> List[Path]:
    """List files in a directory with that match a extension.

    Args:
        ext: Extension of the file to be found.
        dir: Directory to look for files.

    Returns:
        List of files in the directory.
    """
    if isinstance(files, list):
        return [f for f in files if f.suffix == r"." + ext]
    else:
        return list(Path(files).resolve().glob(r"*." + ext))


def files_list(dir: PathStr, *args, **kwargs) -> List[Path]:
    """List all regular files in a directory.

    Args:
        dir: Directory to look for files.

    Returns:
        List of files in the directory.
    """
    return [p for p in Path(dir).iterdir(*args, **kwargs) if p.is_file()]


def params_generate(
    params_def: ParameterDef, custom_fns: Optional[Dict[str, Callable]] = None
) -> Parameter:
    """Generate the random params.

    The function is chosen with a list in the following order:
    [custom_fns, random, numpy.random]

    Args:
        params_def: Definition of the parameters.

    Raises:
        OSError: The parameters file cannot be opened.

    Returns:
        Parameter: Names and values of the parameters.
    """
    functions: Dict[str, Callable] = custom_fns if custom_fns else {}
    params: Parameter = {}

    modules = [np.random, random]

    for param, info in params_def.items():
        fns: List[Optional[Callable]] = []
        fns.append(functions.get(info["function"], None))
        fns.extend([getattr(mod, info["function"], None) for mod in modules])

        if not any(fns):
            raise ValueError(f"Function {info['function']} does not exist")

        fn = next(fn for fn in fns if fn is not None)
        params[param] = fn(*info["values"])

    return params


def params_parse(params_def: PathStr) -> Optional[ParameterDef]:
    """Extract parameter definitions from a file or read the directly.

    The parameters are defined in the following way:

       # This is a comment
       name function arg1 arg2 ... argN
       temp uniform 20 30

    Empty lines and lines with comments are removed.
    The name of the parameter has to be the same one than in the
    template files but without the $.
    The argumens are given in a list separated by spaces.

    Args:
        params_def: Path to the parameter definition file or the definition itself.

    Raises:
        OSError: The parameters file cannot be opened.

    Returns:
        ParameterDef: Names and values of the parameters.
    """
    content: List[str] = []

    if Path(params_def).exists():
        with open(params_def, "r+") as params_fd:
            content = [l.strip() for l in params_fd.readlines()]
    elif isinstance(params_def, str):
        content = params_def.split("\n")

    def cast_value(value: str) -> Union[int, float, str]:
        """Try to cast a value to different types.
        By order, the types are int, float and str.

        Args:
            The value to cast.

        Returns:
            The casted value or the default value in case it fails
        """
        try:
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value

    data: Dict[str, FunctionDef] = {}
    valid_lines = filter(lambda l: l and not l.startswith("#"), content)
    for line in valid_lines:
        param, function, *vals = line.split(" ")
        values = [cast_value(v) for v in vals]
        data[param] = {"function": function, "values": values}

    return data


def sweeps_generate(
    sweeps_def: ParameterDef, custom_fns: Dict[str, Callable], n_repeats: int = 0
) -> Generator:
    """Extract sweeps definitions from a file or read them directly.

    The sweeps are defined in the same way the parameters are defined.
    For that, see `params_generate`.

    Args:
        sweeps_def: Path to the sweeps definition file or the definition itself.
        n_repeats: Number of times to repeat each sweep.

    Raises:
        OSError: The sweeps file cannot be opened.
        StopIteration: When all sweeps have been exhausted.

    Returns:
        Generator: Names and values of the sweeps.
    """
    fn_lut = {"list": lambda *args: list(args), "range": lambda *args: range(*args)}
    functions: Dict[str, Callable] = custom_fns if custom_fns else {}
    sweeps: Parameter = {}

    for sweep, info in sweeps_def.items():
        fns = []
        fns.append(functions.get(info["function"], None))
        fns.append(fn_lut.get(info["function"], None))
        fns.append(getattr(np, info["function"], None))
        if not any(fns):
            raise ValueError(f"Function {info['function']} does not exist")

        fn = next(fn for fn in fns if fn is not None)
        sweeps[sweep] = fn(*info["values"])

    keys, values = zip(*sweeps.items())
    for bundle in product(*values):
        yield from [dict(zip(keys, bundle))] * (n_repeats + 1)


def template_subs(raw: Union[Template, str], subs: Parameter) -> str:
    """Substitute a template with a list of arguments.

    If the argument is a string it gets converted into a Template.

    Args:
        raw: Text to be substituted. Converted automatically to Template if needed.
        *args: List of parameter definitions.

    Returns:
        The template substituted.
    """
    if isinstance(raw, str):
        return Template(raw).safe_substitute(subs)
    else:
        return raw.safe_substitute(subs)


def template_exec(input_txt: PathStr, out_file: PathStr, subs: Parameter) -> None:
    """Read a template from a file, execute it and write the result to a file.

    The template is executed using `template_subs`.

    Args:
        input_txt: Path to the template file or the template itself.
        out_file: Path to save the executed template.
        *args: List of dictionaries with the names and values to be substituted.

    Raises:
      OSError: The template file could not be found.

    Returns:
        None
    """
    with open(out_file, "w+") as result:
        if isinstance(input_txt, Path):
            substituted = template_subs(input_txt.read_text(), subs)
        else:
            substituted = template_subs(input_txt, subs)
        result.write(substituted)


def command_run(cmd: PathStr, is_verbose: bool = False) -> None:
    """Execute a given command using subprocess.run

    Args:
        cmd: Shell command to execute.
        is_verbose: Whether to show the output of the command.

    Returns:
        None
    """
    command: str = cmd.read_text() if isinstance(cmd, Path) else cmd

    if is_verbose:
        run(shlex.split(command), check=True)
    else:
        run(shlex.split(command), check=True, stdout=DEVNULL, stderr=DEVNULL)


################################################################################


class SimBuilder:
    """
    Attributes:
        project_path: Path to the project containing the files
        project_name: Basename of the project_path
        results_path: Path to the directory to store resuts
    """

    def __init__(self, project_path: PathStr):
        self.project_path = Path(project_path).resolve()
        self.project_name = self.project_path.name
        self.results_path = self.project_path / "results"

        self.__netlist: Path = self.project_path / f"{self.project_name}.netlist"
        self.__netlist_out: Path = self.project_path / f"{self.project_name}_net_out"

        self.__custom_fns: Dict[str, Callable] = {}
        self.__is_parametric: bool = False
        self.__is_sweeps: bool = False
        self.__params_def: ParameterDef = {}
        self.__sweeps_def: ParameterDef = {}

        self.__is_ocean = False
        self.__cadence_project: Optional[PathStr] = None
        self.__ocean_script: Optional[PathStr] = None
        self.__ocean_out: Optional[PathStr] = None

        self.__cmd: Optional[str] = None
        self.is_verbose = False

        self.__props: Dict[str, Any] = {}
        self.__sweeps: Optional[Generator[Parameter, None, None]] = None
        self.__params: Optional[Generator[Parameter, None, None]] = None

    def __repr__(self) -> str:
        """Pretty print the SimBuiler"""
        txt = (
            f"Project Path: {self.project_path}\n"
            f"Results path: {self.results_path}\n"
            f"Parametric: {self.__is_parametric}\n"
            f"Has sweeps: {self.__is_sweeps}\n"
            f"Netlist Input: {self.__netlist}\n"
            f"Netlist Output: {self.__netlist_out}"
        )
        if self.__is_ocean:
            txt = (
                f"{txt}\n"
                f"Ocean Input: {self.__ocean_script}\n"
                f"Ocean Output: {self.__ocean_out}"
            )

        if self.is_verbose:
            txt = f"{txt}\n" f"Command: {self.__cmd}"

        return txt

    def scaffold(self, create_all: bool) -> None:
        """Create the project structure.

        Args:
            create_all: If True, create all single files, else
                create only project and results directory

        Returns:
            None
        """
        self.project_path.mkdir(parents=True, exist_ok=True)
        self.results_path.mkdir(parents=True, exist_ok=True)

        if not create_all:
            return

        def default_or_create(file: Optional[PathStr], ext: str) -> Path:
            """Check if the file exists, otherwise create the a default one"""
            if file is not None and Path(file).exists():
                return Path(file)
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
        self.__sweeps = None
        self.__params = None

    def with_props(self, props: Dict[str, Any], reset: bool = True) -> None:
        """Set the internal properties.

        If reset is supplied, the internal properties are substituted by
        the new props, otherwise they get updated.

        Args:
            props: Path to the netlist file.
            reset: Whether to reset the props or update them.
        """
        if reset is True:
            self.__props = props
        else:
            self.__props.update(props)

    def with_netlist(self, netlist_path: Path) -> None:
        """Set the netlist to use.

        If the method `with_simulator` is called first, then the netlist
        points to the previous netlist.

        Args:
            netlist_path: Path to the netlist file.
        """
        if not Path(netlist_path).exists():
            raise ValueError(f"Netlist {netlist_path} does not exist")
        self.__netlist = netlist_path

    def with_custom_fns(
        self, custom_fns: Dict[str, Callable], reset: bool = True
    ) -> None:
        """Assign custom functions to generate sweeps and parameters.

        If reset is supplied the custom_fns get replace by the new ones,
        otherwise they are updated.

        Args:
            custom_fns: Ditionary containing the functions definitions
            reset: Whether to reset the custom_fns or update them.

        Returns:
            Nones
        """
        if reset is True:
            self.__custom_fns = custom_fns
        else:
            self.__custom_fns.update(custom_fns)

    def with_simulator(self, command: PathStr = None) -> None:
        """Assign the simulatior command.

        Args:
            command: String with the command to execute
                or a path to a file whose contents is the command.
        """

        if self.__is_ocean:
            print("Ocean is already defined. It will be used to run simulations")
            return

        if command is None:
            command_files = files_find_ext("command", self.project_path)
            if not command_files:
                raise ValueError(
                    "Please provide a simulator command or a file containing the script."
                )
            if Path(command_files[0]).exists():
                raise ValueError("Simulator file {command_files[0]} does not exist.")
            self.__cmd = command_files[0].read_text().replace("\n", " ")

        elif Path(command).exists():
            with open(command, "r") as cmd_fd:
                lines = [l.strip() for l in cmd_fd.readlines()]
                self.__cmd = " ".join(lines)

        elif isinstance(command, str):
            self.__cmd = command
        else:
            raise ValueError(f"Please provide simulator command.")

    def load_parameters(self, parameters: Union[List[Parameter], str, Path]) -> None:
        """Load parameters that are already created.

        Mainly used to repeat simulations with the same set of parameters.
        The schema of these parameters are checked against the schema
        of the parameters defined with `with_parametric`.

        The parameters can be supplied as a list of dictionaries, a Path pointing
        to a file containing a json dump of the parameters or a string, containing
        also a json dump.

        Args:
            params: Path to the parameters or the definition itself.
        """
        if isinstance(parameters, list):
            params = parameters
        elif Path(parameters).exists():
            params = json.loads(Path(parameters).read_text())
        elif isinstance(parameters, str):
            params = json.loads(parameters)

        if self.__params_def.keys() != params[0].keys():
            raise ValueError(
                "Schema of parameters does not match with defined parameters."
            )

        self.__params = iter(params)

    def with_parametric(self, params_path: Path = None) -> None:
        """Assign the paremeters definitions.

        By default, parameters are read from `project_path/project.params`.
        The sweeps definition can be supplied as a string or as a Path
        pointing to the parameter definitions.

        Args:
            params_path: Path to parameters definition or the definition itself.

        Returns:
            None
        """
        if params_path is None:
            params_files = files_find_ext("params", self.project_path)
            if not params_files:
                raise ValueError("Parameters template file does not exist.")
            if not Path(params_files[0]).exists():
                raise ValueError("Parameters file {params_files[0]} does not exist.")
            params_file = params_files[0]
        elif Path(params_path).exists():
            params_file = params_path
        elif isinstance(params_path, str):
            params_file = params_path
        else:
            raise ValueError(f"Please provide parameters.")

        self.__is_parametric = True
        self.__params_def = params_parse(params_file)
        self.__params = None

    def with_sweeps(self, sweeps_path: Path = None, n_repeats: int = 0) -> None:
        """Assign the sweeps definitions.

        By default, sweeps are read from `project_path/project.sweeps`.
        The sweeps definition can be supplied as a string or as a Path
        pointing to the sweeps definitions.

        Args:
            sweeps_path: Path to sweeps definition or the definition itself.

        Raises:
            ValueError: If `Path(sweeps_path)` or the default sweeps_path does not exist.

        Returns:
            None
        """

        if sweeps_path is None:
            sweeps_files = files_find_ext("sweeps", self.project_path)
            if not sweeps_files:
                raise ValueError("Sweeps template file does not exist.")
            if not Path(sweeps_files[0]).exists():
                raise ValueError("Sweeps file {sweeps_files[0]} does not exist.")
            sweeps_file = sweeps_files[0]
        elif Path(sweeps_path).exists():
            params_file = sweeps_path
        elif isinstance(sweeps_path, str):
            sweeps_file = sweeps_path
        else:
            raise ValueError(f"Please provide sweeps.")

        self.__is_sweeps = True
        self.__sweeps_def = params_parse(sweeps_file)
        self.__sweeps = sweeps_generate(self.__sweeps_def, self.__custom_fns, n_repeats)

    def with_ocean(self, cadence_project: Path, *, ocean_script: Path = None) -> None:
        """
        Args:
            cadence_project: Path to the project inside cadence
            ocean_script: Path to the ocean script to execute

        Returns:
            None
        """
        self.__is_ocean = True

        if not Path(cadence_project).exists():
            raise ValueError(f"{cadence_project} does not exist.")
        self.__cadence_project = cadence_project

        self.__netlist_out = Path(
            self.__cadence_project, "spectre/schematic/netlist/netlist"
        ).resolve()

        if ocean_script is None:
            ocean_files = files_find_ext("ocn", self.project_path)
            if not ocean_files:
                raise ValueError("Ocean script file does not exist.")
            if not Path(ocean_files[0]).exists():
                raise ValueError("Ocean script {ocean_files[0]} does not exist.")
            self.__ocean_script = ocean_files[0]
        elif Path(ocean_script).exists():
            self.__ocean_script = ocean_script
        elif isinstance(ocean_script, str):
            self.__ocean_script = ocean_script
        else:
            raise ValueError(f"Please provide sweeps.")

        self.__ocean_out = Path(self.project_path, f"ocn_{self.project_name}")
        self.__cmd = f"sh -c 'ocean -nograph < {self.__ocean_out}'"

    def run_iterations(self, iterations: int) -> Generator:
        """Run a number of iterations.

        Args:
            iterations: Number of iterations to run

        Returns:
            Generator: Generator for every single simulation.

        TODO: What happends if run_single takes a lot of time? or if there are errors and it throws?
        """
        if self.__cmd is None:
            raise ValueError("Simulation command has not been defined")

        for i in range(1, iterations + 1):
            yield self.run_single(i)

    def run_single(
        self, iteration: Optional[int] = None
    ) -> Tuple[Optional[Parameter], Optional[Parameter]]:
        """Run a single simulation

        Args:
            iteration: Index of the iteration if multiple are to be run.

        Returns:
            Parameters and sweeps for the run
        """
        if self.__cmd is None:
            raise ValueError("Simulation command has not been defined")

        subs_dict: Parameter = {}
        if self.__is_parametric:
            if self.__params:
                try:
                    params = next(self.__params)
                except StopIteration as e:
                    raise StopIteration("Can not run any more paremeters") from e
            else:
                params = params_generate(self.__params_def, self.__custom_fns)
            subs_dict.update(params)
        else:
            params = None

        if self.__is_sweeps:
            try:
                sweeps: Optional[Parameter] = next(self.__sweeps)
                subs_dict.update(sweeps)
            except StopIteration as e:
                raise StopIteration("Can not run any more sweeps") from e
        else:
            sweeps = None

        subs_dict.update(
            {
                "netlist": str(self.__netlist_out),
                "results": str(self.results_path),
                "project": str(self.project_name),
                "project_path": str(self.project_path),
            }
        )
        if iteration is not None:
            subs_dict.update({"iteration": iteration})

        subs_dict.update(self.__props)

        template_exec(self.__netlist, self.__netlist_out, subs_dict)

        if self.__is_ocean and self.__ocean_script and self.__ocean_out:
            template_exec(self.__ocean_script, self.__ocean_out, subs_dict)

        cmd: Template = Template(self.__cmd)
        command: str = cmd.safe_substitute(subs_dict)

        command_run(command, self.is_verbose)

        return params, sweeps


if __name__ == "__main__":
    import argparse
    import sys

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
