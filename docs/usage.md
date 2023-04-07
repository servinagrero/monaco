# Creating a job

Monaco works by reading jobs from a config file and executing them. The configuration files can be written in [YAML](https://yaml.org/), [TOML](https://toml.io/en/) and [JSON](https://www.json.org/json-en.html) format.

```yaml title="Basic config file"
jobs:
  Hello:
    steps: 
      - echo "hello world"
```

All the jobs defined in a config file are intended to be project specific. To execute a config file, the following command is used.

```bash
$ monaco -c /path/to/config.yaml
```

## Executing commands

Commands can be executed like scripts by using the `commands` key. This accepts a lists of commands that will be executed with ``/bin/sh`. The `|` operator can be used in YAML to treate a block of text as different lines. When multiple jobs are defined, they will be executed in the order they are defined.

Each command gets executed in a different process, so the different commands cannot communicate between them directly.

```yaml
jobs:
  FirstJob:
    steps:
      - echo "This job will be first one"

  SecondJob:
    steps: 
      - |
        echo "This job will be the second one"
        echo "And so on..."

# Would result in the output
# This job will be the first one
# This job will be the second one
# And so on...
```

We can select which job we want to execute by passing the `-n` parameter. In the following example only the job FirstJob will be executed.

```bash
$ monaco -c /path/to/config.yaml -n FirstJob
```


## Iterative commands

A command can be executed multiple times by providing the `iter` variable. This variable can have the following values:

- A list of iterations.
- A map containing the key `to` and the optional key `from`.

When executing multiple iterations, the iteration index can be accesed through the `Iteration` template variable.

```yaml title="Example of an iteration list"
jobs:
  Test:
    iters: [1, 3, 5, 42]
    steps:
      - echo "We are on iteration {{.Iteration}}"

# Would result in the output
# We are on iteration 1
# We are on iteration 3
# We are on iteration 5
# We are on iteration 42
```

```yaml title="Example of an iteration map"
jobs:
  Test:
    iters:
      # from: 0 If from is not specified it defaults to 0
      end: 5
    steps:
      - echo "We are on iteration {{.Iteration}}"

# Would result in the output
# We are on iteration 0
# We are on iteration 1
# We are on iteration 2
# We are on iteration 3
# We are on iteration 4
```

When supplying a list of iterations, we are not limited to numbers. Strings are also supported

```yaml
jobs:
    - name: Test
      iters: ["first", "second"]
      steps: |
        echo "We are on iteration {{.Iteration}}"

# Would result in the output
# We are on iteration first
# We are on iteration second
```

## Properties

Custom properties can be passed to a job with the `props` key. The will be accesible in the templates through the `Props` template variable. The `{{}}` syntax is specific to Go templates. For more information, see below the [templates documentation](#working-with-templates)

```yaml
jobs:
  Test:
    props:
      answer: 42
    steps:
      - echo "The answer is {{.Props.answer}}"
# Would result in the output
# The answer is 42
```

The properties can be defined globally for all jobs if the `props` key is moved to the global scope. However, each job can override them if they are defined in their own scope.

```yaml
props:
  answer: 42

jobs:
  First:
    steps:
      - echo "Here the answer is {{.Props.answer}}
  Second:
    props:
      answer: different
    steps:
      - echo "But here is {{.Props.answer}}"

# Would result in the output
# Here the answer is 42
# But here is different
```

### Loading secrets

Sometimes it's desirable to load up properties that we don't want to share or commit to github. The option `secrets` allows doing that. This file has the same format as the .env file.

```yaml
secrets: "./path/to/secrets"

jobs:
  SecretJob:
    steps:
      - echo "The anwser is {{.Props.TOP_SECRET}}
```

## Job dependencies

We can add dependencies to a job if we need to run job before, even if they are declared after. To do that, add the name of the job dependency to the `depends` list.

```yaml
jobs:
  Second:
    requires: 
      - echo "This will be the first command"
      - {job: First}
    steps:
      -echo "And at last, this job"
  First:
    steps:
      - echo "This will be the second command"

# Would result in the output
# This will be the first command
# This will be the second command
# And at last, this job
```

## Environment variables

Similarly to properties, environment variables for all jobs if the `env` key is moved to the global scope. Each job can override them if they are defined in their own scope.

```yaml
env:
  CUSTOMVAR: 42

jobs:
  First:
    steps:
      - echo "The answer is $CUSTOMVAR"
  Second:
    env:
      CUSTOMVAR: -1
    steps:
      - echo "But here is $CUSTOMVAR"

# Would result in the output
# The answer is 42
# But here is -1
```

## Custom directory

The directory where the command will be executed can be changed with the `dir` variable. The directory can be accessed also with the `Dir` template variable. If it's not specified, it defaults to the directory where the tool is executed. The path to the config file can be accesed also with the `ConfigFile` template variable.

```yaml
jobs:
  First:
    dir: /path/to/dir
    steps:
      - |
      echo "We are on $PWD"
      echo "It's the same as {{.Dir}}"

# Would result in the output
# We are on /path/to/dir
# Its the same as /path/to/dir
```

## Conditional execution

## Working with templates

This tool relies on Go templates. For more information about them, please refer to the [official documentation](https://pkg.go.dev/text/template).

This framework provides some functions that can be accesible from the templates. All the functions from the [sprig library](https://masterminds.github.io/sprig/lists.html) are available.

### loadData

Allows loading data from a source file. It reads data from YAML, TOML, JSON and CSV.


```text title="data.csv"
a,b,c
1,2,3
4,5,6
```

```text
{{ $data := loadData "data.csv" }}

{{ range $column, $values := $data }}
Column: {{$column}}
Values: {{$Values}}
---
{{end}}
```

```text
Column: a
Values: [1, 4]
---
Column: b
Values: [2, 5]
---
Column: c
Values: [3, 6]
---
```
