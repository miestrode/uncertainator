# Uncertainator
Uncertainator is a command-line utility for adding uncertainty to PDDL domains and problems, by making some actions have multiple effects with a probability distribution. The resulting files use a format resembling somewhat PPDDL, but really being a format designed to be used with Gal Kaminka's `pddlsim`[^1].

Like Stripper, Uncertainator also has a focus on correctness above all else, and will also output "strange looking predicates", some of the time.

## How does it work?
Uncertainator uses a technique I've dubbed "predicate injection": It injects brand new parameterless predicates into a domain and then uses said predicates as possible effects on actions. Because in general one cannot modify the parameters and regular effects of actions without understanding more about the domain's structure, the technique instead only adds new things.

Then whenever running an action either its primary, regular effect would occur, or an injected effect that only uses injected predicates (which of course can also be thought of as flags). Then, one can simply change the goal of a problem reliant on the domain to be an addition some combination of injected predicates.

This way, replanning may still be needed when solving the domain, and it will still behave probabilistically, but only in a layer "above" the regular domain. Notice however that domains with non-reversible actions could have dead ends appear in them due to this, but otherwise an uncertainated problem should always be beatable.

## Requirements
Because this project exports a format that isn't standard PDDL, a regular parser cannot be used, and instead we use `sexpdata`, a generic S-expression parser, and indeed this project requires `sexpdata` and `click` to function.

## CLI
*For more information, please do use `--help`*

Uncertainator features 3 subcommands. The first allows you to uncertainate a PDDL domain, and it's general format looks like:
```
<INVOCATION> domain [--as-text BOOLEAN] DOMAIN_PATH INJECTION_COUNT
```
where `<INVOCATION>` is some way to invoke the script `__main__.py` using Python. The `INJECTION_COUNT` is just the number of injected predicates to use, and `--as-text` allows you to instead of passing a path, pass the full text of a domain file.

The second subcommand allows you to uncertainate a PDDL problem, and an invocation of it looks like:
```
<INVOCATION> problem [--as-text BOOLEAN] PROBLEM_PATH [PREDICATES]...
```
where `PREDICATES` is the collection of injected predicates used by the domain this problem is dependent on, space separated.

The final subcommand allows you to kind of automate running the command en-masse, and it is of the form:
```
<INVOCATION> group [--suffix TEXT] DIRECTORY INJECTION_COUNT
```
where `--suffix` is the suffix of the new folders created due to this command (by default `UNC`) and depth is the depth to go to whilst traversing the provided directory. Note that as hinted to above, this command creates a new directory-tree similar to the one passed, with alternative names to the passed, containing only the new PDDL files.

# Contributing
This tool currently appears mostly complete, and new features aren't currently planned, as they are not needed by me.

Therefore, I will give priority, and prefer if most PRs and issues will be in relation to bugs, or in relation to switching to a proper backend, specific to PDDL (not an S-expression parser). In addition, bugs with the output format in relation to parsing it by special tools (that are related to `pddlsim`) are also welcome.

## NOTE:
New features are still welcome, just again, they have less priority. This is not a primary project of mine, and I don't plan to actively maintain it beyond using it for conducting research.

[^1]: Also known as [ExecutionSimulation](https://bitbucket.org/galk-opensource/executionsimulation/src/master/).
