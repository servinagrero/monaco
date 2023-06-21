## Installation

Monaco can be built by having [cargo](https://doc.rust-lang.org/cargo/index.html) installed in the system and then running the following commands.

```
$ git clone https://github.com/servinagrero/monaco && cd monaco
$ cargo install
```

The static binary `monaco` will be generated in the directory.

## Using monaco

Monaco is designed to work as a standalone tool that reads a configuration file and spawn the appropiate commands. Nonetheless, it is designed to work also as a rust library, so other users can extend the way jobs can be launched. Monaco directly has support for [YAML](https://yaml.org/), [TOML](https://toml.io/en/) and [JSON](https://www.json.org/json-en.html) formats.

To see all available monaco options, invoke it with the `--help` argument

```sh
$ monaco --help
Execute jobs from a config file

Usage: monaco [OPTIONS] --config <CONFIG>

Options:
  -c, --config <CONFIG>  Path to the config file
  -j, --job <JOB>        Name of the job to execute
      --dry              Run in dry mode (Don't execute steps, just print them)
  -h, --help             Print help
  -V, --version          Print version
```

To invoke monaco and launch the jobs, pass the path to the configuration file through the `-c` argument.
```bash
$ monaco -c /path/to/config.{yml|yaml|json|toml}
```

If the configuration file contains multiple jobs, we can direcly launch one by using the `--job` argument and the name of the job. 

```bash
$ monaco -c /path/to/config.yml -j Job1
```

The section [usage](usage.md) will explain in details the inner workings of monaco and all configuration options available.
