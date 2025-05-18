#!/usr/local/bin/python3.5
# , redirect, url_for, send_from_directory
# from .crossdomain import crossdomain

import datetime as dt
import json
import logging
import os
import sys
import traceback
from pprint import pprint
from typing import Dict, List, Optional, Tuple

import colorlog
import humanize
import jsonschema
import numpy as np
from flask import Flask, jsonify, render_template, request
from flask_compress import Compress
from flask_sse import sse
from numpy._typing import NDArray

from kernel.data import (
    condition_class,
    puzzle_class,
    reaction_mechanism_class,
    solution_class,
)
from kernel.engine import plotter

np.seterr(all="warn")

from pathlib import Path


def all_files_in(mypath, end=""):
    return [
        p.stem
        for p in Path(mypath).iterdir()
        if p.is_file() and not p.name.startswith(".") and p.name.endswith(end)
    ]


# For Server-Sent-Event support:


class ListStream:
    """One ListStream corresponds to one unique computation job.
    c.f.: http://stackoverflow.com/questions/21341096/redirect-print-to-string-list"""

    def __init__(self, jobID):
        self.jobID = jobID

    def write(self, *args):
        s = ""
        for arg in args:
            s += " " + str(arg)
        with app.app_context():
            try:
                sse.publish({"data": s}, channel=self.jobID)
            except AttributeError:
                sys.__stdout__.write(" * Orphaned Message: " + s)

    def flush(self):
        pass


# Initialize logger:
rootLogger = logging.getLogger()  # access the root logger
rootLogger.removeHandler(logging.getLogger().handlers[0])
# create a handler for printing messages onto the console
handler = colorlog.StreamHandler()
handler.setFormatter(
    colorlog.ColoredFormatter(
        "%(log_color)s%(levelname)s%(reset)s:%(bold)s%(name)s%(reset)s:%(message)s"
    )
)
# attach the to-console handler to the root logger
rootLogger.addHandler(handler)


AUTH_CODE = "123"
# ongoingJobs = []

app = Flask(__name__)
# Flask-compress is a Flask extension that provides gzip compression for the web app.
# It is used to reduce the size of the response data sent from the server to the client,
# which is helpful for us, because we are going to send tons of SVGs per job.
# https://github.com/colour-science/flask-compress
Compress(app)

# redis configuation, for SSE support:
# 'os.environ.get("REDIS_URL")' is for Heroku and "redis://localhost" is meant for localhost.
app.config["REDIS_URL"] = os.environ.get("REDIS_URL") or "redis://localhost"
app.register_blueprint(sse, url_prefix="/stream")

# load JSON schema for Puz file for validation:
with open("puzzles/schema.js") as f:
    schema = f.read()
schema = json.loads(schema)


@app.route("/plot", methods=["POST", "OPTIONS"])
def handle_plot_request():
    start_time = dt.datetime.now()  # start timer
    data = request.get_json()  # receive JSON data
    # initialize logger for this particular job:
    # create a log_handler that streams messages to the web UI specifically for this job.
    logging_handler = logging.StreamHandler(stream=ListStream(data["jobID"]))
    job_logger = logging.getLogger(data["jobID"])
    job_logger.addHandler(logging_handler)  # redirect the logs since NOW
    # All functions should have their own logger that is a child of the job_logger.
    logger = job_logger.getChild("handle_plot_request")
    # now the serious part:
    try:
        temperature = data["temperature"]  # just a shorthand

        with open(f"puzzles/{data['puzzle']}.puz") as json_file:
            puzzle_definition = json.load(json_file)
            logger.info("    (0) Successfully loaded Puzzle Data from file!")
        plot_combined, plot_individual = simulate_experiments_and_plot(
            data,
            puzzle_definition,
            temperature,
        )
        logger.info(
            f"Executed for {humanize.precisedelta(dt.datetime.now() - start_time)}."
        )
        return jsonify(
            jobID=data["jobID"],
            status="success",
            plot_individual=plot_individual,
            plot_combined=plot_combined,
            temperature=temperature,
        )  # serving result figure files via "return", so as to save server calls
    except Exception as error:
        # print out last words:
        logger.error(traceback.format_exc())
        logger.info(
            f"Executed for {humanize.precisedelta(dt.datetime.now() - start_time)}."
        )
        return jsonify(jobID=data["jobID"], status="error")


def simulate_experiments_and_plot(
    data: Dict,
    puzzle_definition: Dict,
    temperature: float,
) -> Tuple[str, str]:
    """
    Simulate the puzzle and draw plots.
    """
    logger = logging.getLogger(data["jobID"]).getChild("simulate_experiments_and_plot")
    # Now start preparing the instances of custom classes for further actual use in Engine.Driver:
    #    (1) Instance of the Puzzle class:
    #           (1.1) general data:
    elementary_reactions = np.array(puzzle_definition["coefficient_array"], dtype=float)
    energy_dict = puzzle_definition["energy_dict"]
    # `coefficient_dict` maps species names to their indices in the coefficient array.
    species_list = sorted(
        puzzle_definition["coefficient_dict"],
        key=puzzle_definition["coefficient_dict"].get,
    )
    num_rxn = len(puzzle_definition["coefficient_array"])
    num_mol = len(species_list)
    logger.info(
        "        %i species are involved. They are: %s", num_mol, " ".join(species_list)
    )
    #           (1.2) data about the reagents, used in pre-equilibrium computations:
    #         - - - - - - - - - - - - - - -
    this_puzzle = puzzle_class.puzzle(
        num_rxn,
        num_mol,
        species_list,
        elementary_reactions,
        energy_dict,
        reagent_dictionary=[
            # Note: We use a list here because we want to keep the order of the reagents as they are defined in the puzzle file.
            # TODO: Why would it matter? The `.puz` files, when loaded into the Python realm as `dict`s, will not be ordered.
            (
                reagent,
                make_reaction_mechanism_for_reagent(
                    PERsToggles,
                    data["jobID"],
                    energy_dict,
                    puzzle_definition,
                    reagent,
                    species_list,
                ),
            )
            for reagent, PERsToggles in puzzle_definition["reagentPERs"].items()
        ],
        Ea=puzzle_definition["transition_state_energies"],
    )
    #                                 num_rxn, num_mol, species_list, elementary_reactions, energy_dict -> fed to class "reaction_mechanism"
    #                                                                                                        reagents_dict, Ea -> fed to class puzzle
    logger.info("    (1) Puzzle Instance successfully created.")
    #    (2) Instance of the Condition class:
    # rxn_temp = temperature
    # Each entry in data['conditions'] is of the form:
    #     [name of the reactant, amount, its fridge temperature]
    r_names = [reactant["name"] for reactant in data["conditions"]]
    r_concs = [reactant["amount"] for reactant in data["conditions"]]
    r_temps = [reactant["temperature"] for reactant in data["conditions"]]
    m_concs = [0.0] * num_mol
    #         - - - - - - - - - - - - - - -
    this_condition: condition_class.Condition = condition_class.Condition(
        temperature, species_list, r_names, r_temps, r_concs, m_concs
    )
    logger.info("    (2) Condition Instance successfully created.")
    #    (3) Instance of the Solution class:
    coefficient_array_proposed = []
    for each_rxn_proposed in data["reactions"]:
        coefficient_line_proposed = [0] * num_mol
        for each_slot in each_rxn_proposed:
            if each_slot != "":
                coefficient_line_proposed[species_list.index(each_slot)] += 1
        coefficient_array_proposed.append(coefficient_line_proposed)
    num_rxn_proposed = len(coefficient_array_proposed)
    #         - - - - - - - - - - - - - - -
    this_solution = solution_class.solution(
        num_rxn_proposed,
        num_mol,
        species_list,
        coefficient_array_proposed,
        energy_dict,
    )
    logger.info("    (3) Solution Instance successfully created.")
    # Finally, drive the engine with these data:
    logger.info("    (4) Simulating...")

    logger.info("         (a) True Model first:")

    logger.info("             simulating...")
    true_data: np.ndarray = run_true_experiment(
        data["jobID"], this_puzzle, this_condition
    )
    logger.info("         (b) User Model then:")

    logger.info("             simulating...")
    # if we are simulating the true_model then solution argument is none
    user_data: Optional[np.ndarray] = run_proposed_experiment(
        data["jobID"], this_condition, this_solution, true_data
    )
    if user_data is None:
        logger.error("             The model you proposed failed.")

    logger.info("    (5) Drawing plots... ")
    (plot_individual, plot_combined) = plotter.sub_plots(
        plottingDict=puzzle_definition["coefficient_dict"],
        true_data=true_data,
        user_data=user_data,
    )
    return plot_combined, plot_individual


def make_reaction_mechanism_for_reagent(
    is_each_involved: List[bool],
    job_id: str,
    energy_dict: Dict,
    puzzle_definition: Dict,
    reagent: str,
    species_list: List[str],
):
    logger = logging.getLogger(job_id).getChild("make_reaction_mechanism_for_reagent")
    reagent_id = puzzle_definition["coefficient_dict"][reagent]
    # Filter for pre-equilibration reactions:
    pre_equl_elem_rxns = [
        # `is_involved` = "is this elementary reaction involved in the pre-equilibration of this reagent?"
        rxn
        for rxn, is_involved in zip(
            puzzle_definition["coefficient_array"], is_each_involved
        )
        if is_involved
    ]
    if not pre_equl_elem_rxns:
        logger.info(
            f'        For the reagent #{reagent_id} "{reagent}", no pre-equilibration is needed.'
        )
        pre_equl_elem_rxns = np.array([[0.0]], dtype=float)
        reagent_species_list = [reagent]
    else:
        # convert it into a numpy dict
        pre_equl_elem_rxns = np.array(pre_equl_elem_rxns, dtype=float)
        # a boolean array of whether each species specified in the puzzle file is present in this set of ElemRxns for preEqul.
        if_uninvolvedSpecies: NDArray[np.bool_] = np.all(
            pre_equl_elem_rxns == False, axis=0
        )
        # now, remove unused species to simplify the rxn. set used for pre-equilibration of this particular reagent:
        pre_equl_elem_rxns = np.delete(
            pre_equl_elem_rxns, np.where(if_uninvolvedSpecies), axis=1
        )
        logger.info(f"            species_list         : {species_list}")
        logger.info(f"            if_uninvolvedSpecies: {if_uninvolvedSpecies}")
        reagent_species_list = [
            s
            for s, uninvolved in zip(species_list, if_uninvolvedSpecies)
            if not uninvolved
        ]
    reagent_num_rxn = len(pre_equl_elem_rxns)
    reagent_num_mol = len(reagent_species_list)
    logger.info("            About pre-equilibration:")
    logger.info(
        f"                Elem. Rxn.s used for pre-equilibration (a total of {reagent_num_rxn}): \n"
        + f"                    {pre_equl_elem_rxns}"
    )
    logger.info(
        f"                which involves {reagent_num_mol} species: {reagent_species_list}"
    )
    reaction_mechanism = reaction_mechanism_class.reaction_mechanism(
        reagent_num_rxn,
        reagent_num_mol,
        reagent_species_list,
        pre_equl_elem_rxns,
        energy_dict,
    )
    return reaction_mechanism


from kernel.engine.driver import run_proposed_experiment, run_true_experiment


@app.route("/save", methods=["POST", "OPTIONS"])
def save():
    data = request.get_json()  # receive JSON data
    print("Data received:")
    pprint(data)
    if not request.remote_addr == "127.0.0.1":
        if not data["auth_code"] == AUTH_CODE:
            return jsonify(
                status="danger", message="Authentication failed. Check your password."
            )
    # Else, validate with jsonschema:
    existing_puzzles = all_files_in("puzzles")
    if data["puzzleName"] in existing_puzzles:
        return jsonify(
            status="danger", message="Puzzle already exists. Try another name."
        )
    try:
        jsonschema.validate(data, schema)
    except jsonschema.exceptions.ValidationError as e:
        return jsonify(status="danger", message=e.message)
    else:
        # now convert:
        species_name_to_id = {
            species: i for i, species in enumerate(data["speciesNames"])
        }
        coefficient_array = convert_reactions_to_coefficients(
            data["reactions"], species_name_to_id
        )
        coefficient_dict = {
            # TODO: This is AI-generated. Check this.
            species: i
            for i, species in enumerate(data["speciesNames"])
        }
        energies = dict(zip(data["speciesNames"], data["speciesEnergies"]))
        data_to_write = {
            "coefficient_dict": coefficient_dict,
            "energy_dict": energies,
            "coefficient_array": coefficient_array,
            "reagents": list(data["reagentPERs"].keys()),
            "reagentPERs": data["reagentPERs"],
        }
        print("Data prepared:")
        pprint(data_to_write)
        with open("puzzles/" + data["puzzleName"] + ".puz", "w") as f:
            try:
                json.dump(data_to_write, f, indent=4)
            except Exception as e:
                print(e)
                return jsonify(status="danger", message="Error occured. Can't save.")
            else:
                return jsonify(status="success", message="Puzzle successfully saved.")


def convert_reactions_to_coefficients(reactions, species_name_to_id: Dict[str, int]):
    num_species = len(species_name_to_id)
    matrix = []
    for reaction in reactions:
        coefficients = [0.0] * num_species
        for i, speciesName in enumerate(reaction):
            if speciesName:
                speciesID = species_name_to_id[speciesName]
                coefficients[speciesID] += 1 if i > 1 else -1
        matrix.append(coefficients)
    return matrix


@app.route("/create")
def serve_page_create():
    return render_template(
        "main.html", mode="create", ip=request.remote_addr.replace(".", "_")
    )


@app.route("/play/<puzzleName>")
def serve_page_play(puzzleName):
    with open("puzzles/" + puzzleName + ".puz") as json_file:
        puzzleData = json_file.read()
    return render_template(
        "main.html",
        mode="play",
        puzzleName=puzzleName,
        puzzleData=puzzleData,
        ip=request.remote_addr.replace(".", "_"),
    )


@app.route("/")
def serve_page_index():
    puzzleList = all_files_in("puzzles", end=".puz")
    return render_template("index.html", puzzleList=puzzleList)
