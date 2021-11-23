#!/usr/bin/env hy

(import random)
(import argparse)
(import json)
(import [datetime [datetime]])
(import [threading [Thread]])
(import itertools)
(import [string [Template]])
(import [subprocess [run DEVNULL]])
(import [pathlib [Path]])
(import itertools)

; Global dict to add custom function to generate params used on `generate-params`
(setv CUSTOM-FUNCTIONS {})

(defn subs-template [raw &rest args]
  "Substitute a template using safe_substitute

If the input is a string, it gets converted into a Template.
The values to be substituted are pased as dictionaries.

Args:
  raw: Raw string or Template to substitute."
  (if (isinstance raw str)
      (setv template (Template raw))
      (setv template raw))
  (setv params {})
  (for [arg args] (params.update arg))
  (template.safe_substitute params))

(defn subs-template-file [in-file out-file &rest args]
  "Substitue a template read from a file

Internally it uses `subs-template` to subtitute the contents
of the template.

Args:
  in_file:
  out_file:"
  (with [template-path (open in-file "r")
         result (open out-file "w+")]
    (setv substituted (subs-template (template-path.read) #* args))
    (result.write substituted)))

(defn parse-params-file [params-file]
  "Parse a paremeters definition file.

Args:
  params-file: Path to the file with the definition."
  (setv data {})
  (setv valid-line (fn [l] (or l (not (l.startswith "#")))))

  (setv content (->> (open params_file "r+")
                  (.readlines)
                  (map (fn [l] (l.strip)))
                  (filter valid-line)))

  (for [line content]
    (setv [param function #* vals] (line.split " "))
    (setv vals (list (map float vals)))
    (assoc data param {"function" function "values" vals}))
  data)

(defn generate-params [params-def]
  "Generate parameters based on a definition.

TODO: Make CUSTOM-FUNCTIONS a parameter"
  (global CUSTOM-FUNCTIONS)
  (setv params {})

  (setv gen-param (fn [info]
    (setv fn-name (get info "function"))
    (setv custom-fn (.get CUSTOM-FUNCTIONS fn-name None))
    (setv random-fn (getattr random fn-name None))
    (if custom-fn (custom-fn #* (get info "values"))
        random-fn (random-fn #* (get info "values"))
        (raise (ValueError f"Function {fn-name} could not be found")))))

  (for [(, param info) (.items params-def)]
    (assoc params param (gen-param info)))
  params)

(defn filter-files [filter-fn files]
  (list (filter filter-fn files)))

(defn find-file-ext [ext files]
  (filter-files
    (fn [f]
      (.endswith (if (isinstance f Path) (f.name) (str f)) ext))
      files))

(defn find-file-icase [name files]
  (filter-files
    (fn [f]
      (= (if (isinstance f Path) (f.name) (str f)) name))
    files))


(defn run-command [cmd &kwonly [verbose? False]]
  "Execute a given command using subprocess.run

Args:
  cmd: Shell command to execute.

  is_verbose: Whether to show the output of the command.


TODO: Add timeout ?"
  (if* verbose?
      (run cmd :shell True :check True)
      (run cmd :shell True :check True :stdout DEVNULL :stderr DEVNULL)))

(defn parse-config [config-path]
  "Parse the configuration file.

TODO: Add more formats"
  (json.load (open config-path "r")))
