import itertools
import os
import random
from typing import Any, Callable, Optional

import click
import sexpdata

# Constants
ACTION_NAME_INDEX = 1
GOAL_CONDITION_INDEX = 1
ACTION_EFFECT_INDEX = 7

INJECTION_PREFIX = "injected"
FILLER = "-"
SELECT_CORE_EFFECT = 0.5
SELECT_MINOR_EFFECT = 0.45


def activate_with_probability(probability: float) -> bool:
    return random.random() < probability


def eager_shallow_search(expression: list, criteria: Callable[[list], bool]) -> Optional[list]:
    for sub_expression in expression:
        if criteria(sub_expression):
            return sub_expression

    return None


def full_shallow_search(expression: list, criteria: Callable[[Any], bool]) -> list[Any]:
    return list(filter(criteria, expression))


def inject_predicates(domain: list, count: int) -> Optional[list[sexpdata.Symbol]]:
    domain_expressions = sexpdata.cdr(domain)

    match eager_shallow_search(
        domain_expressions, lambda s_expression: sexpdata.car(s_expression) == sexpdata.Symbol(":predicates")
    ):
        case None:
            # By the PDDL specification this should be impossible
            return None
        case expression:
            # This must be the predicate-list expression
            predicates = expression
            new_predicate_names = []

            # TODO: Handle error case
            longest_predicate = max(
                [len(sexpdata.car(predicate).value()) for predicate in predicates[1:]],
            )

            for new_predicate_index in range(count):
                # Create a new, provably different predicate name to use
                predicate_name = sexpdata.Symbol(
                    INJECTION_PREFIX
                    + FILLER * max(1, longest_predicate - len(INJECTION_PREFIX))
                    + str(new_predicate_index)
                )

                new_predicate_names.append(predicate_name)
                predicates.append([predicate_name])

            return new_predicate_names


def injected_predicate_powerset(
    predicates: list[sexpdata.Symbol],
) -> list[list[sexpdata.Symbol]]:
    subsets = [[]]

    for predicate in predicates:
        subsets += [subset + [predicate] for subset in subsets]

    return subsets


def predicate_subset_as_effect(
    subset: list[sexpdata.Symbol],
) -> list[sexpdata.Symbol | list[sexpdata.Symbol] | list[sexpdata.Symbol | list[sexpdata.Symbol]]]:
    return [sexpdata.Symbol("and")] + [[predicate] for predicate in subset]


Action = list


def generate_possible_effects(predicates: list[sexpdata.Symbol]) -> list[sexpdata.Symbol | list[sexpdata.Symbol]]:
    return list(itertools.chain(*[[(predicate,), (sexpdata.Symbol("not"), (predicate,))] for predicate in predicates]))


Effect = list


def assign_probabilities(core_effect: Effect, minor_effects: set[list[sexpdata.Symbol]]) -> list[float | Effect]:
    if minor_effects:
        minor_effect_values = [random.random() for _ in range(len(minor_effects))]

        total = sum(minor_effect_values)
        scale_factor = SELECT_MINOR_EFFECT / total

        return [SELECT_CORE_EFFECT, core_effect] + list(
            itertools.chain(
                *[
                    [
                        probability * scale_factor,
                        effect,
                    ]
                    for probability, effect in zip(minor_effect_values, minor_effects)
                ]
            )
        )
    else:
        return [SELECT_CORE_EFFECT, core_effect]


def uncertainate_domain(domain: list, injection_count: int) -> Optional[list[sexpdata.Symbol]]:
    match inject_predicates(domain, injection_count):
        case None:
            return None
        case new_predicates:
            actions = full_shallow_search(domain, lambda part: sexpdata.car(part) == sexpdata.Symbol(":action"))
            minor_effects = generate_possible_effects(
                new_predicates,
            )

            for action in actions:
                core_effect = action[ACTION_EFFECT_INDEX]
                probability_distribution = assign_probabilities(core_effect, minor_effects)
                action[ACTION_EFFECT_INDEX] = [sexpdata.Symbol("probabilistic")] + probability_distribution

            return new_predicates


def uncertainate_problem(problem: list, predicates: list[sexpdata.Symbol]) -> bool:
    predicate_powerset = injected_predicate_powerset(predicates)
    predicate_powerset.remove([])

    effect = predicate_subset_as_effect(random.choice(predicate_powerset))
    initialization_subset = random.choice(predicate_powerset)

    match eager_shallow_search(problem[1:], lambda expression: sexpdata.car(expression) == sexpdata.Symbol(":goal")):
        case None:
            return False
        case goal:
            if goal[GOAL_CONDITION_INDEX][0] == sexpdata.Symbol("and"):
                goal[GOAL_CONDITION_INDEX] += effect[1:]
            elif all([type(part) is not list for part in goal[GOAL_CONDITION_INDEX]]):
                goal[GOAL_CONDITION_INDEX] = [sexpdata.Symbol("and"), goal[GOAL_CONDITION_INDEX]] + effect[1:]
            else:
                goal[GOAL_CONDITION_INDEX] = [sexpdata.Symbol("and"), goal[GOAL_CONDITION_INDEX], effect]

    match eager_shallow_search(problem[1:], lambda expression: sexpdata.car(expression) == sexpdata.Symbol(":init")):
        case None:
            return False
        case initialization:
            for predicate in predicates:
                if predicate in initialization_subset:
                    initialization.append([predicate])

            return True


def problem_domain(file_path: str) -> Optional[sexpdata.Symbol]:
    try:
        with open(file_path) as file:
            expression = sexpdata.loads(file.read())

        if expression[1][0] == sexpdata.Symbol("problem"):
            return expression[2][1]
        else:
            return None
    except Exception:
        return None


def domain_name(file_path: str) -> Optional[sexpdata.Symbol]:
    try:
        with open(file_path) as file:
            definition = sexpdata.loads(file.read())[1]

        if definition[0] == sexpdata.Symbol("domain"):
            return definition[1]
        else:
            return None
    except Exception:
        return None


@click.group()
@click.version_option("0.2.0")
def cli():
    """Inject probability into PDDL domains and problems."""
    pass


def uncertainate_domain_text(domain_text: str, injection_count: int) -> Optional[tuple[str, list[sexpdata.Symbol]]]:
    domain = sexpdata.loads(domain_text, nil=None, true=None, false=None)
    injections = uncertainate_domain(domain, injection_count)

    match injections:
        case None:
            return None
        case injections:
            return sexpdata.dumps(domain, pretty_print=True).replace("\\", ""), injections


@cli.command("domain")
@click.option("--as-text", default=False)
@click.argument("domain_path", type=click.STRING)
@click.argument("injection_count", type=click.INT)
def uncertainate_domain_command(as_text: bool, domain_path: str, injection_count: int):
    if not as_text:
        with open(domain_path) as domain_file:
            domain = domain_file.read()

    match uncertainate_domain_text(domain, injection_count):
        case None:
            pass
        case (domain, predicates):
            print(domain)
            print(predicates)


def uncertainate_problem_text(problem_text: str, predicates: list[sexpdata.Symbol]) -> Optional[str]:
    problem = sexpdata.loads(problem_text, nil=None, true=None, false=None)

    if uncertainate_problem(problem, predicates):
        return sexpdata.dumps(problem, pretty_print=True).replace("\\", "")

    return None


@cli.command("problem")
@click.option("--as-text", default=False)
@click.argument("problem_path", type=click.STRING)
@click.argument("predicates", nargs=-1)
def uncertainate_problem_command(as_text: bool, problem_path: str, predicates: list[str]):
    if not as_text:
        with open(problem_path) as problem_file:
            problem = problem_file.read()

    uncertainated_problem = uncertainate_problem_text(problem, [sexpdata.Symbol(predicate) for predicate in predicates])

    print(uncertainated_problem)


@cli.command("group")
@click.option("--suffix", default="UNC")
@click.argument("directory", type=click.STRING)
@click.argument("injection_count", type=click.INT)
def uncertainate_group_command(suffix: str, directory: str, injection_count: int):
    parent = os.path.split(os.path.abspath(directory))[0]

    def load_path_to_save_path(directory: str) -> str:
        shared_path = os.path.commonprefix((parent, directory))

        return os.path.join(
            shared_path,
            *[part + suffix for part in directory[len(shared_path) + 1 :].split("/")],
        )

    domain_predicates = {}  # Represents a mapping from domain names to their injected predicates
    problems_to_uncertainate = []

    for current_directory, _, files in os.walk(directory):
        current_directory = os.path.abspath(current_directory)
        save_directory = load_path_to_save_path(current_directory)
        os.mkdir(save_directory)

        for file_base in filter(lambda file_path: os.path.splitext(file_path)[1] == ".pddl", files):
            full_path = os.path.join(current_directory, file_base)
            save_path = os.path.join(save_directory, file_base)

            match domain_name(full_path):
                case None:
                    match problem_domain(full_path):
                        case None:
                            print(f"PDDL file {full_path} is neither a problem definition or a domain definition")
                        case domain:
                            problems_to_uncertainate.append((full_path, save_path, domain))
                case domain:
                    with open(full_path) as file:
                        expression = sexpdata.loads(file.read())

                    match uncertainate_domain(expression, injection_count):
                        case None:
                            raise ValueError("Domain could not be uncertainated")
                        case predicates:
                            with open(save_path, "w") as save_file:
                                save_file.write(sexpdata.dumps(expression, pretty_print=True).replace("\\", ""))

                            domain_predicates[domain] = predicates

    for full_path, save_path, domain_dependency in problems_to_uncertainate:
        with open(full_path) as file:
            expression = sexpdata.loads(file.read())

            if domain_dependency in domain_predicates.keys() and uncertainate_problem(
                expression, domain_predicates[domain_dependency]
            ):
                with open(save_path, "w") as save_file:
                    save_file.write(sexpdata.dumps(expression, pretty_print=True).replace("\\", ""))
            else:
                print(f"Could not uncertainate problem {full_path}")
