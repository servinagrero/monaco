#!/usr/bin/env python3

import re
import random
import shlex
import json
from collections.abc import Iterator
from itertools import product
from pathlib import Path
from string import Template
from subprocess import DEVNULL, run
from .parser import Parser
from typing import (
    Union,
    Callable,
    Dict,
    Generator,
    List,
    Tuple,
    Any,
    Optional,
)

__version__ = "0.1.0"
__author__ = "Sergio Vinagrero <servinagrero@gmail.com>"
__license__ = "MIT License"
__url__ = "https://github.com/servinagrero/monaco"


# Type definitions
ParameterVal = Union[int, float, str]
FunctionDef = dict
PathStr = Union[str, Path]
ParameterDef = Dict[str, FunctionDef]
Parameter = Dict[str, ParameterVal]


def files_find_ext(ext: str, files: Union[PathStr, List[Path]]) -> List[Path]:
    """List files in a directory that match a extension.

    Args:
        ext: Extension of the file to be found.
        dir: Directory to look for files or list of files.

    Returns:
        List of files in the directory.
    """
    if isinstance(files, list):
        return [f for f in files if f.suffix == r"." + ext]
    else:
        return list(Path(files).glob(r"*." + ext))


def files_list(dir: PathStr) -> List[Path]:
    """List all regular files in a directory.

    Args:
        dir: Directory to look for files.

    Returns:
        List of files in the directory.
    """
    return [p for p in Path(dir).iterdir() if p.is_file()]


def params_generate(
    params_def: ParameterDef, custom_fns: Optional[Dict[str, Callable]] = None
) -> Parameter:
    """Generate a set of random parameters.

    The function is chosen with a list in the following order:
    [custom_fns, random, other modules]

    Args:
        params_def: Definition of the parameters.

    Raises:
        OSError: The parameters file cannot be opened.

    Returns:
        Parameter: Names and values of the parameters.
    """
    functions: Dict[str, Callable] = custom_fns if custom_fns else {}
    params: Parameter = {}

    modules: List[module] = [random]
    try:
        import numpy as np

        modules.append(np.random)
    except ImportError:
        pass

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

    def cast_value(value: str) -> ParameterVal:
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

    range_re = re.compile(r"^(\w+){(\d+:\d+)}.*")
    data: Dict[str, FunctionDef] = {}
    valid_lines = filter(lambda l: l and not l.startswith("#"), content)
    for line in valid_lines:
        param, function, *vals = line.split(" ")
        values = [cast_value(v) for v in vals]
        if "{" in param and "}" in param:
            name, range_str = range_re.search(param).groups()
            start, end = [int(n) for n in range_str.split(":")]
            for i in range(start, end + 1):
                data[f"{name}{i}"] = {"function": function, "values": values}
        else:
            data[param] = {"function": function, "values": values}

    return data


def sweeps_generate(
    sweeps_def: ParameterDef, custom_fns: Dict[str, Callable], n_repeats: int = 1
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

    modules = []
    try:
        import numpy as np

        modules.append(np)
    except ImportError:
        pass

    for sweep, info in sweeps_def.items():
        fns = []
        fns.append(functions.get(info["function"], None))
        fns.append(fn_lut.get(info["function"], None))
        fns.extend([getattr(mod, info["function"], None) for mod in modules])
        if not any(fns):
            raise ValueError(f"Function {info['function']} does not exist")

        fn = next(fn for fn in fns if fn is not None)
        sweeps[sweep] = fn(*info["values"])

    keys, values = zip(*sweeps.items())
    for bundle in product(*values):
        yield from [dict(zip(keys, bundle))] * n_repeats


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
        substituted = Parser(input_txt, subs).eval()
        result.write(substituted)


def command_run(cmd: PathStr, is_verbose: bool = False) -> None:
    """Execute a given command using subprocess.run

    Args:
        cmd: Shell command to execute.
        is_verbose: Whether to show the output of the command.

    Returns:
        None
    """
    command: str = cmd if isinstance(cmd, str) else cmd.read_text()

    if is_verbose:
        run(shlex.split(command), check=True)
    else:
        run(shlex.split(command), check=True, stdout=DEVNULL, stderr=DEVNULL)


################################################################################


class SimBuilder:
    """Class used to generate complex parametric simulations.

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

        self.__files = {}

        self.__cmd: Optional[str] = None
        self.is_verbose = False

        self.__props: Dict[str, Any] = {}
        self.__sweeps_list: Optional[Generator[Parameter, None, None]] = None
        self.__params: Union[Generator[Parameter, None, None], List[Parameter]] = []
        self.__params_list: List[Parameter] = []

    def __repr__(self) -> str:
        """Pretty print the SimBuiler"""
        txt = (
            f"Project Path: {self.project_path}\n"
            f"Results path: {self.results_path}\n"
            f"Netlist Input: {self.__netlist}\n"
            f"Netlist Output: {self.__netlist_out}"
        )

        if self.is_verbose:
            txt = (
                f"{txt}\n"
                f"Parametric: {self.__is_parametric}\n"
                f"Has sweeps: {self.__is_sweeps}\n"
                f"Command: {self.__cmd}"
            )

            if self.__files:
                txt = f"{txt}\nList of additional files:\n"
                for in_file, out_file in self.__files.items():
                    txt += f"{in_file} -> {out_file}\n"

                return txt[:-1]  # Remove last newline char

        return txt

    def __get_file_input(self, ext: str, file_input: Optional[PathStr]) -> PathStr:
        """Obtain an input from a default file, a supplied file or a string.

        The in put can be provided by a file path or a string. If no argument
        is provided, the input is looked from the default path inside the
        project_path.

        Args:
            ext: Extension for the default path.
            file_input: Path to the file, if provided, or string.

        Raises:
            ValueError: If the default file or the file provided
                do not exist.

        Returns:
            Path to the input file or the string itself.
        """
        if file_input is None:
            files = files_find_ext(ext, self.project_path)
            if not files:
                raise ValueError(f"Template for {ext} not found.")
            return files[0]
        elif Path(file_input).exists():
            return Path(file_input)
        elif isinstance(file_input, str):
            return file_input
        else:
            raise ValueError(f"Please provide {ext} template.")

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

        netlist_file = self.project_path / f"{self.project_name}.netlist"
        files = [
            (self.__cmd, self.project_path / f"{self.project_name}.command"),
            (self.__params_def, self.project_path / f"{self.project_name}.params"),
            (self.__sweeps_def, self.project_path / f"{self.project_name}.sweeps"),
            (self.__netlist, netlist_file),
        ]

        for default, file_path in files:
            if default is None or not Path(file_path).exists():
                # If the file exists, touch does nothing
                Path(file_path).touch(mode=0o666, exist_ok=True)

        self.__netlist = netlist_file
        self.__params_def = {}
        self.__sweeps_def = {}
        self.__sweeps_list = None
        self.__params = []
        self.__params_list = []

    @property
    def props(self) -> Dict:
        return self.__props

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

    def with_command(self, command: Optional[PathStr] = None) -> None:
        """Assign the command to execute.

        Args:
            command: String with the command to execute
                or a path to a file whose contents is the command.
        """
        cmd = self.__get_file_input("command", command)

        if isinstance(cmd, str):
            self.__cmd = cmd
        else:
            self.__cmd = cmd.read_text()

    def load_parameters(self, parameters: Union[List[Parameter], PathStr]) -> None:
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

        self.__is_parametric = True
        self.__params = iter(params)

    def save_parameters(self, params_path: PathStr) -> None:
        """Save the parameters generated to a JSON file.

        Args:
            params_path: Path to the parameters file to be saved.

        Returns:
            None
        """
        with open(params_path, "w+") as fd:
            fd.write(json.dumps(self.__params_list))

    def with_parametric(self, params_path: Optional[PathStr] = None) -> None:
        """Assign the paremeters definitions.

        By default, parameters are read from `project_path/project.params`.
        The sweeps definition can be supplied as a string or as a Path
        pointing to the parameter definitions.

        Args:
            params_path: Path to parameters definition or the definition itself.

        Returns:
            None
        """
        params = self.__get_file_input("params", params_path)

        self.__is_parametric = True
        self.__params_def = params_parse(params)
        self.__params = []
        self.__params_list = []

    def with_sweeps(
        self, sweeps_path: Optional[PathStr] = None, n_repeats: int = 1
    ) -> None:
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
        sweeps = self.__get_file_input("sweeps", sweeps_path)

        self.__is_sweeps = True
        self.__sweeps_def = params_parse(sweeps)
        self.__sweeps_list = sweeps_generate(
            self.__sweeps_def, self.__custom_fns, n_repeats
        )

    def with_files(self, files: dict, reset: bool = True) -> None:
        """Assign a list of files to inject values

        Args:
            files: Dictionary containing the input path and the output path
                of external files to be also substituted.
            reset: Whether to reset the internal list of files when
                calling this function.

        Returns:
            None
        """
        if reset:
            self.__files = files
        else:
            self.__files.update(files)

    def run_iterations(self, iterations: int) -> Generator:
        """Run a number of iterations.

        Args:
            iterations: Number of iterations to run

        Returns:
            Generator: Generator for every single simulation.
        """
        if isinstance(iterations, int):
            for i in range(1, iterations + 1):
                yield self.run_single(i)
        else:
            count = 1
            while True:
                yield from self.run_single(count)
                count += 1

    def run_single(
        self, run_id: Optional[int] = None
    ) -> Tuple[Optional[Parameter], Optional[Parameter]]:
        """Run a single simulation

        Args:
            iteration: Index of the iteration if multiple are to be run.

        Returns:
            Parameters and sweeps for the run
        """
        subs_dict: Parameter = {}
        if self.__is_parametric:
            if isinstance(self.__params, Iterator):
                try:
                    params = next(self.__params)
                    extra_keys = [
                        key for key in params.keys() if key not in self.__params_def
                    ]
                    for key in extra_keys:
                        del params[key]

                    missing_params = {
                        k: v for k, v in self.__params_def.items() if k not in params
                    }
                    if missing_params:
                        remains = params_generate(missing_params, self.__custom_fns)
                        params.update(remains)
                    self.__params_list.append(params)
                except StopIteration as e:
                    raise StopIteration("Can not run any more paremeters") from e
            else:
                params = params_generate(self.__params_def, self.__custom_fns)
                self.__params_list.append(params)

            subs_dict.update(params)
        else:
            params = None

        if self.__is_sweeps:
            try:
                sweeps = next(self.__sweeps_list)
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
        if run_id is not None:
            subs_dict.update({"iteration": run_id})

        for key, value in self.__props.items():
            if key not in subs_dict:
                subs_dict[key] = value

        template_exec(self.__netlist, self.__netlist_out, subs_dict)

        for file_in, file_out in self.__files.items():
            if file_in == "netlist":
                template_exec(self.__netlist, str(file_out), subs_dict)
            else:
                template_exec(str(file_in), str(file_out), subs_dict)

        if self.__cmd:
            command = Parser(self.__cmd, subs_dict).eval()
            command_run(command, self.is_verbose)

        return params, sweeps


if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(
        description="""
    Scaffold a project for simulations.

    If the argument -a is supplied, every template file is created.
    """
    )
    parser.add_argument("-p", "--project", help="Path to project", required=True)
    parser.add_argument(
        "-a", "--all", help="Create all template files", action="store_true"
    )
    args = parser.parse_args()
    if Path(args.project).absolute() == Path(__file__).parent.absolute():
        print("Project path has to be different from current path")
        sys.exit(1)
    SimBuilder(args.project).scaffold(create_all=args.all)
