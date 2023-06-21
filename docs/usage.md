# Usage

When reading a configuration, monaco will make some healthchecks. Among other things, monaco will check for the following requirements in every job:

- The job dependencies exist.
- Template paths are not malformed.
- The iterations file is readable and contains a list of iterations.
- The ranges on the iterations are not malformed.

## Executing commands

Commands are defined as short strings that get executed like shell commands. On windows they are executed with `cmd` while on linux they are executed with `/bin/sh`. The commands will be executed in the order they are defined. Each command gets executed in a different process, so the different commands cannot communicate between them directly.


```yaml title="Basic config file"
jobs:
  - name: Hello
    steps: 
      - echo "hello world"
  - name: Another
    steps:
      - echo "Hello from another"

# Would result in the output
# hello world
# Hello from another
```

We can also executed other jobs instead of shell commands by provididing the job name as map. Moreover, we can temporarely update the props and environment of the job if the `props` and `env` keys are also supplied.

```yaml title="Job calling another job"
jobs:
  - name: First
    steps: 
      - job: Second
  - name: Second
    steps:
      - echo "Hello from Second"

# Would result in the output
# Hello from Second
```

Note that when a job has executed all of its commands, it gets marked as completed and it won't be executed again, even after successive calls, as depicted here.

```yaml title="Job calling another job"
jobs:
  - name: First
    steps: 
      - job: Second
      - job: Second
  - name: Second
    steps:
      - echo "Hello from Second"

# Would result in the output
# Hello from Second
```

Monaco offers a couple of tools to address the number of times a job is able to be executed. The number of times a job is allowed to executed is controlled through the iterations configuration. There is also the when functionality that allows us to determine whether a job should run or not even if there are iterations.


## Iterations

So far we have seen that we can launch jobs and execute commands. The problem is that these commands get executed only once. Monaco allows performing _iterations_ on every job. There are multiple ways to define iterations:

- An absolute path to a JSON file containing an array.
- A boolean value to indicate whether the job will be executed once or in an infinite loop.
- A range of numbers provided with the keys `from`, `to` and an optional step with the key `by`.
- A list of values directly in the configuration file.

As long as the iterations are contained in a list, we are able to utilize not only numbers, but complex objects as iterations, as it will be shown.  When executing multiple iterations, the iteration index can be accesed through the `iter` template variable.

### Infinite loop

```yaml title="Example of an infinite loop"
jobs:
  - name: Test
    iters: true # If false, only once iteration. It is the default behaviour
    steps:
      - echo "Infinite loop"

# Would result in the output
# Infinite loop
# Infinite loop
# ...
```

### Iteration list

```yaml title="Example of an iteration list"
jobs:
  - name: Test
    iters: [1, 3, 5, 42]
    steps:
      - echo "We are on iteration {{iter}}"

# Would result in the output
# We are on iteration 1
# We are on iteration 3
# We are on iteration 5
# We are on iteration 42
```

### Range of values

```yaml title="Example of range iteration"
jobs:
  Test:
    iters:
      # from: 0 If from is not specified it defaults to 0
      end: 5
      # by: 1 The step defaults to 1
    steps:
      - echo "We are on iteration {{iter}}"

# Would result in the output
# We are on iteration 0
# We are on iteration 1
# We are on iteration 2
# We are on iteration 3
# We are on iteration 4
```

### Iterations from JSON file

```json title="iterations.json"
[{"letter": "A", "idx": 1}, {"letter": "B", "idx": 2}]
```

```yaml title="Example on iterations from JSON file"
jobs:
    - name: Test
      iters: "iterations.json"
      steps:
        - echo "Letter {{iter.letter}} and index {{iter.idx}}"

# Would result in the output
# Letter A and index 1
# Letter B and index 2
```

## Variable interpolation

Monaco provides two mechanisms that allow variable interpolation.

- Through the shell environment.
- Through [mustache]() templates.

### Shell environment

```yaml
jobs:
  - name: Test
    env:
      ANSWER: 42
    steps:
      - echo "the answer is $ANSWER"

# Would result in the output
# The answer is 42
```

The environment can be also updated on a global basis if the `env` key is defined in the top level of the configuration. Each job is then free to override the variable if they are defined in their own scope.

```yaml
env:
  foo: bar

jobs:
  - name: First
    steps:
      - echo "Here foo is $foo"
  - name: Second
    env:
      foo: 42
    steps:
      - echo "but here is $foo"

# Would result in the output
# Here foo is bar
# but here is 42
```

In the case that we want to keep some variables secret, we can provide `dotenv: true`. In this case, monaco will read the file `.env` from the configuration directory and put them in the global environment. The `.env` file is a simple text file where each line has the format `KEY=VALUE`. If the option is enabled but the `.env` file is not readable, monaco will print a warning

```text title="Example of .env"
PASS=1234
```

```yaml title="Reading dotenv"
dotenv: true

jobs:
  - name: Test
    steps:
      - echo "The password is $PASS"

# Would result in the output
# The password is 1234
```

The properties can be defined globally for all jobs if the `props` key is moved to the global scope. However, each job can override them if they are defined in their own scope.

```yaml
env:
  foo: bar

jobs:
  - name: First
    steps:
      - echo "Here foo is $foo"
  - name: Second
    env:
      foo: 42
    steps:
      - echo "but here is $foo"

# Would result in the output
# Here foo is bar
# but here is 42
```

### Templates


## Redirecting output

The outpt of all steps in a job can be redirected easily through the `log` variable. There are three possible values:

- If true is provided, the output will be redirected to standard out. This is the default behaviour.
- If fals is provided, no output will be emitted.
- If a string is provided, it will be treated as a template pointing to the path where the output will be apended. This file is recalculated for every iteration.


As with most options, the log output can be set on a global basis and each job can override the value.

```yaml title="Redirecting output"
log: false

jobs:
  - name: First
    dir: /tmp
    log: "{{dir}}/output.log"
    steps:
      - echo "This will be in the file"
  - name: Second
    steps:
      - echo "This won't be seen"
```

```text title="/tmp/output.log"
This will be in the file
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

## Chaning directory

The directory of execution can be changed on a job basis by providing the `dir` key. The current directory can be used with the shell variable or through the template variable `dir`. If no directory is provided, it defaults to the configuration directory. The configuration directory can also be accessed through the template variable `config_dir`.

```yaml title="Changing execution directory"
jobs:
  - name: Test
    dir: /tmp
    steps:
      - echo "We are in $PWD"
      - echo "The same as {{dir}}"
      - echo "The config is on {{config_dir}}"

# Would result in the output
# We are in /tmp
# The same as /tmp
# The config is on /path/to/config_dir
```

## Errors during execution

During the execution of multiple steps of a job, something could go wrong. If one of the commands fail to execute, monaco will not execute the rest of the steps. To ignore errors, provide the `ignore_errors: true` on a job basis. 

```yaml title="Errors during execution"
jobs:
  - name: Test
    steps: 
      - echo "You will see this"
      - false
      - echo "But you won't see this"

# Would result in the output
# You will see this
```

```yaml title="Ignoring errors"
jobs:
  - name: Test
    ignore_errors: true
    steps: 
      - echo "You will see this"
      - false
      - echo "And this too"

# Would result in the output
# You will see this
# And this too
```

## Conditional execution

By default every job will be executed once. Once its execution has finished (either with errors or without errors), it will be marked as completed. In the case where a job has some iterations, all iterations will be executed.

```yaml title="Job is executed once"
jobs:
  - name: Parent
    iters: [1, 2, 3]
    steps: 
      - job: Child
    
  - name: Child
    steps:
      - echo "This is executed only once"

# Would result in the output
# This is executed only once
```

However, we can provide the `when` parameter to a job to check when a job should run. This parameter accepts a list of shell commands that will be executed in order. If all of the commands exit without errors, the job will be run. Since this option has precedence over the completed marker, we can launch the same job as many times as needed.

For example, in order to always launch a job, we can use the `true` command as follows:

```yaml title="Conditional execution"
jobs:
  - name: Parent
    iters: [1, 2, 3]
    steps: 
      - job: Child
    
  - name: Child
    steps:
      - echo "over and over"
    when:
      - true

# Would result in the output
# over and over
# over and over
# over and over
```
