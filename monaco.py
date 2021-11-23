from hy.core.language import name
import random
import argparse
import json
from datetime import datetime
from threading import Thread
import itertools
from string import Template
from subprocess import run, DEVNULL
from pathlib import Path
import itertools
CUSTOM_FUNCTIONS = {}


def subs_template(raw, *args):
    """Substitute a template using safe_substitute

If the input is a string, it gets converted into a Template.
The values to be substituted are pased as dictionaries.

Args:
  raw: Raw string or Template to substitute."""
    if isinstance(raw, str):
        template = Template(raw)
        _hy_anon_var_1 = None
    else:
        template = raw
        _hy_anon_var_1 = None
    params = {}
    for arg in args:
        params.update(arg)
    return template.safe_substitute(params)


def subs_template_file(in_file, out_file, *args):
    """Substitue a template read from a file

Internally it uses `subs-template` to subtitute the contents
of the template.

Args:
  in_file:
  out_file:"""
    _hy_anon_var_4 = None
    with open(in_file, 'r') as template_path:
        _hy_anon_var_3 = None
        with open(out_file, 'w+') as result:
            substituted = subs_template(template_path.read(), *args)
            _hy_anon_var_3 = result.write(substituted)
        _hy_anon_var_4 = _hy_anon_var_3
    return _hy_anon_var_4


def parse_params_file(params_file):
    """Parse a paremeters definition file.

Args:
  params-file: Path to the file with the definition."""
    data = {}
    valid_line = lambda l: l or not l.startswith('#')
    content = filter(valid_line, map(lambda l: l.strip(), open(params_file,
        'r+').readlines()))
    for line in content:
        [param, function, *vals] = line.split(' ')
        vals = list(map(float, vals))
        data[param] = {'function': function, 'values': vals}
    return data


def generate_params(params_def):
    """Generate parameters based on a definition.

TODO: Make CUSTOM-FUNCTIONS a parameter"""
    global CUSTOM_FUNCTIONS
    params = {}

    def gen_param(info):
        fn_name = info['function']
        custom_fn = CUSTOM_FUNCTIONS.get(fn_name, None)
        random_fn = getattr(random, fn_name, None)
        if custom_fn:
            _hy_anon_var_8 = custom_fn(*info['values'])
        else:
            if random_fn:
                _hy_anon_var_7 = random_fn(*info['values'])
            else:
                raise ValueError(f'Function {fn_name} could not be found')
                _hy_anon_var_7 = None
            _hy_anon_var_8 = _hy_anon_var_7
        return _hy_anon_var_8
    for param, info in params_def.items():
        params[param] = gen_param(info)
    return params


def filter_files(filter_fn, files):
    return list(filter(filter_fn, files))


def find_file_ext(ext, files):
    return filter_files(lambda f: (f.name() if isinstance(f, Path) else str
        (f)).endswith(ext), files)


def find_file_icase(name, files):
    return filter_files(lambda f: (f.name() if isinstance(f, Path) else str
        (f)) == name, files)


def run_command(cmd, *, is_verbose=False):
    """Execute a given command using subprocess.run

Args:
  cmd: Shell command to execute.

  is_verbose: Whether to show the output of the command.


TODO: Add timeout ?"""
    return run(cmd, shell=True, check=True) if is_verbose else run(cmd,
        shell=True, check=True, stdout=DEVNULL, stderr=DEVNULL)


def parse_config(config_path):
    """Parse the configuration file.

TODO: Add more formats"""
    return json.load(open(config_path, 'r'))

