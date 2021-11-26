#!/usr/local/bin/python3.5
# , redirect, url_for, send_from_directory
# from .crossdomain import crossdomain
from pprint import pprint

from flask import Flask, jsonify, render_template, request, send_file
from flask_compress import Compress
from flask_sse import sse

# relative import fix. according to this: http://stackoverflow.com/a/12869607/1147061
# import sys
# sys.path.append('..')
from kernel.engine import driver, fileIO

driver.temp_diag = False
driver.system_output = pprint
import _thread
import hashlib
import json
import logging
import mimetypes
import os
import sys
import time
import traceback

import colored_traceback.auto
import colorlog
import jsonschema
import numpy as np

from kernel.data import (
    condition_class,
    puzzle_class,
    reaction_mechanism_class,
    solution_class,
)

np.seterr(all="warn")

# one-liners:
all_files_in = lambda mypath, end="": [
    os.path.splitext(os.path.basename(f))[0]
    for f in os.listdir(mypath)
    if os.path.isfile(os.path.join(mypath, f))
    and not f.startswith(".")
    and f.endswith(end)
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
# tell the program to send messages on its own behalf.
logger = logging.getLogger(__name__)


def np_err_handler(message, flag):
    logger.error(
        "NumPy floating-point error: "
        + message
        + "\n"
        + "".join(traceback.format_stack(limit=7)[:-1])
    )


np.seterrcall(np_err_handler)
np.seterr(all="call")

# Global variables, and also initializing the webapp using Flask framework:
path_root = "results/"
if_runningOnline = "DYNO" in os.environ  # detect whether on Heroku
# use cache only when in production mode; in other words, don't use cache on local machine
if_useCache = if_runningOnline
AUTH_CODE = "123"
# ongoingJobs = []

app = Flask(__name__)
Compress(app)  # https://github.com/libwilliam/flask-compress

# redis configuation, for SSE support:
# 'os.environ.get("REDIS_URL")' is for Heroku and "redis://localhost" is meant for localhost.
app.config["REDIS_URL"] = os.environ.get("REDIS_URL") or "redis://localhost"
app.register_blueprint(sse, url_prefix="/stream")

# load JSON schema for Puz file for validation:
with open("puzzles/schema.js") as f:
    schema = f.read()
schema = json.loads(schema)


@app.route("/plot", methods=["POST", "OPTIONS"])
def plot():
    startTime = time.time()  # start timer
    data = request.get_json()  # receive JSON data
    # initialize logger for this particular job:
    # create a log_handler that streams messages to the web UI specificially for this job.
    logging_handler = logging.StreamHandler(stream=ListStream(data["jobID"]))
    rootLogger.addHandler(logging_handler)  # redirect the logs since NOW
    # now the serious part:
    try:
        # prepare directories:
        path_puzzle = path_root + data["puzzle"] + "/"
        path_condition = path_puzzle + "condition_" + data["conditionID"] + "/"
        path_solution = path_condition + "solution_" + data["solutionID"] + "/"
        # prepare figure file_names:
        plot_name = path_solution + "/" + str(data["temperature"])
        plot_individual_filename = plot_name + "_individual.svg"
        plot_combined_filename = plot_name + "_combined.svg"
        # try whether result already generated:
        if (
            os.path.isfile(plot_individual_filename)
            and os.path.isfile(plot_combined_filename)
            and if_useCache
        ):
            logger.info("Figures already generated before. Skipped.")
            with open(plot_individual_filename) as content_file:
                plot_individual = content_file.read()
            with open(plot_combined_filename) as content_file:
                plot_combined = content_file.read()
        # elif data['jobID'] in ongoingJobs: # not a job already done! let's see if anyone has been doing it...?
        #    logger.info('Someone already submitted identical plotting job.')
        #    return # TODO: proper handle the conflict!
        else:  # we have to plot it ourselves! orz...
            temperature = data["temperature"]  # just a short hand
            logger.info("================== RECEIVED PLOTTING JOB ==================")
            # we check the deepest folder, which implies all parent-grandparent folders exist.
            if not os.path.isdir(path_solution):
                os.makedirs(path_solution)
            # Now start preparing the instances of custom classes for further actual use in Engine.Driver:
            #    (0) First of all, load the Puzzle Data into backend:
            with open("puzzles/" + data["puzzle"] + ".puz") as json_file:
                puzzleData = json.load(json_file)
                logger.info("    (0) Successfully loaded Puzzle Data from file!")
            #    (1) Instance of the Puzzle class:
            #           (1.1) general data:
            elemRxns = np.array(puzzleData["coefficient_array"], dtype=float)
            energy_dict = puzzleData["energy_dict"]
            Ea = None  # puzzleData['transition_state_energies']
            # logger.info('        SpeciesList involved are:',' '.join(speciesList))
            speciesList = sorted(
                puzzleData["coefficient_dict"], key=puzzleData["coefficient_dict"].get
            )
            num_rxn = len(puzzleData["coefficient_array"])
            num_mol = len(speciesList)
            #           (1.2) data about the reagents, used in pre-equilibrium computations:
            reagentsDict = []
            for reagent, PERsToggles in puzzleData["reagentPERs"].items():
                reagentID = puzzleData["coefficient_dict"][reagent]
                preEqulElemRxns = [
                    puzzleData["coefficient_array"][i]
                    for i in range(num_rxn)
                    if PERsToggles[i]
                ]
                if preEqulElemRxns == []:
                    logger.info(
                        "        For the reagent #"
                        + str(reagentID)
                        + ' "'
                        + reagent
                        + '", no pre-equilibration needed.'
                    )
                    preEqulElemRxns = np.array([[0.0]], dtype=float)
                    reagent_speciesList = [reagent]
                else:
                    # convert it into a numpy dict
                    preEqulElemRxns = np.array(preEqulElemRxns, dtype=float)
                    logger.info(
                        "        For the reagent #"
                        + str(reagentID)
                        + ' "'
                        + reagent
                        + '", the following reactions present: //omitted//'
                    )  # \n',preEqulElemRxns)
                    # a boolean array of whether each species specified in the puzzle file is present in this set of ElemRxns for preEqul.
                    if_uninvolvedSpecies = np.all(preEqulElemRxns == False, axis=0)
                    # now, remove unused species to simplify the rxn. set used for pre-equilibration of this particular reagent:
                    displacement = 0
                    # mask and remove columns of those unused species
                    for speciesID in range(num_mol):
                        # if this species is not used:
                        if if_uninvolvedSpecies[speciesID]:
                            # http://stackoverflow.com/questions/1642730/how-to-delete-columns-in-numpy-array
                            preEqulElemRxns = np.delete(
                                preEqulElemRxns, speciesID - displacement, 1
                            )
                            displacement += 1
                    logger.info("            speciesList         : " + str(speciesList))
                    logger.info(
                        "            if_uninvolvedSpecies: " + str(if_uninvolvedSpecies)
                    )
                    # \n',preEqulElemRxns)
                    logger.info(
                        "            This should mask the previous matrix into: //omitted//"
                    )
                    reagent_speciesList = [
                        speciesList[i]
                        for i in range(num_mol)
                        if not if_uninvolvedSpecies[i]
                    ]
                reagent_num_rxn = len(preEqulElemRxns)
                reagent_num_mol = len(reagent_speciesList)
                logger.info("            About pre-equilibration:")
                logger.info(
                    "                Elem. Rxn.s used for pre-equilibration (a total of "
                    + str(reagent_num_rxn)
                    + "): \n                    "
                    + str(preEqulElemRxns)
                )
                logger.info(
                    "                which involves "
                    + str(reagent_num_mol)
                    + " species: "
                    + str(reagent_speciesList)
                )
                reagentsDict.append(
                    (
                        reagent,
                        reaction_mechanism_class.reaction_mechanism(
                            reagent_num_rxn,
                            reagent_num_mol,
                            reagent_speciesList,
                            preEqulElemRxns,
                            energy_dict,
                        ),
                    )
                )
            #         - - - - - - - - - - - - - - -
            this_puzzle = puzzle_class.puzzle(
                num_rxn,
                num_mol,
                speciesList,
                elemRxns,
                energy_dict,
                reagent_dictionary=reagentsDict,
                Ea=Ea,
            )
            #                                 num_rxn, num_mol, speciesList, elemRxns, energy_dict -> fed to class "reaction_mechanism"
            #                                                                                                        reagentsDict, Ea -> fed to class puzzle
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
            this_condition = condition_class.condition(
                temperature, speciesList, r_names, r_temps, r_concs, m_concs
            )
            logger.info("    (2) Condition Instance successfully created.")
            #    (3) Instance of the Solution class:
            coefficient_array_proposed = []
            for each_rxn_proposed in data["reactions"]:
                coefficient_line_proposed = [0] * num_mol
                for each_slot in each_rxn_proposed:
                    if each_slot != "":
                        coefficient_line_proposed[speciesList.index(each_slot)] += 1
                coefficient_array_proposed.append(coefficient_line_proposed)
            num_rxn_proposed = len(coefficient_array_proposed)
            #         - - - - - - - - - - - - - - -
            this_solution = solution_class.solution(
                num_rxn_proposed,
                num_mol,
                speciesList,
                coefficient_array_proposed,
                energy_dict,
            )
            logger.info("    (3) Solution Instance successfully created.")
            # Finally, drive the engine with these data:
            logger.info("    (4) Simulating...")
            logger.info("         (a) True Model first:")
            # anticipate the file name where the true model's data is stored
            trueModel_fileName = path_condition + "plotData_t_" + str(temperature)
            if os.path.isfile(trueModel_fileName + "_.dat") and if_useCache:
                # Mechanism(true)+Condition for this puzzle already simulated before. Take advantage of the cache now...")
                logger.info(" cache available. Load from it.")
                written_true_data = fileIO.load_modelData(trueModel_fileName + "_.dat")
            else:
                # Mechanism(true)+Condition for this puzzle not calculated before; do it now...")
                logger.info(" simulating...")
                written_true_data = driver.drive_data(
                    puzzle=this_puzzle,
                    # this is merely for backward compatibility.
                    puzzle_path=path_puzzle,
                    condition=this_condition,
                    condition_path=path_condition,
                    progress_tick=lambda x: 0,
                )
                logger.info(
                    "            Got result in a type of "
                    + str(type(written_true_data))
                    + "."
                )
            logger.info("         (b) User Model then:")
            # anticipate the file name where the true model's data is stored
            userModel_fileName = path_solution + "plotData_t_" + str(temperature)
            if (
                os.path.isfile(userModel_fileName + "_.dat")
                or os.path.isfile(userModel_fileName + "_Failed")
            ) and if_useCache:
                if os.path.isfile(userModel_fileName + "_.dat"):
                    # Mechanism(solution)+Condition for this puzzle already simulated before. Take advantage of the cache now...")
                    logger.info(" cache available. Load from it.")
                    written_user_data = fileIO.load_modelData(
                        userModel_fileName + "_.dat"
                    )
                elif os.path.isfile(userModel_fileName + "_Failed"):
                    # Mechanism(solution)+Condition for this puzzle already simulated before. Take advantage of the cache now...")
                    logger.info(" UserModel failed as told by flag file.")
                    written_user_data = False
            else:
                # Mechanism(solution)+Condition for this puzzle not calculated before; do it now...")
                logger.info(" simulating...")
                written_user_data = driver.drive_data(
                    puzzle=this_puzzle,
                    # this is merely for backward compatibility.
                    puzzle_path=path_puzzle,
                    condition=this_condition,
                    condition_path=path_condition,
                    progress_tick=lambda x: 0,
                    solution=this_solution,
                    solution_path=path_solution,
                    written_true_data=written_true_data,
                )
                logger.info(
                    "             Got result in a type of "
                    + str(type(written_user_data))
                    + "."
                )
            logger.info("    (5) Drawing plots... ")
            (plot_individual, plot_combined) = driver.plotter.sub_plots(
                Temperature=temperature,
                plottingDict=puzzleData["coefficient_dict"],
                solution_fileName=path_solution
                + "/"
                + "plotData_t_"
                + str(temperature),
                condition_fileName=path_condition
                + "/"
                + "plotData_t_"
                + str(temperature),
                written_true_data=written_true_data,
                written_user_data=written_user_data,
            )
            # end Timer
            logger.info(
                "    (6) Now that everything is finished, write simulated data to file for caching..."
            )
            _thread.start_new_thread(
                fileIO.save_modelData, (written_true_data, trueModel_fileName)
            )
            _thread.start_new_thread(
                fileIO.save_modelData, (written_user_data, userModel_fileName)
            )
            _thread.start_new_thread(
                fileIO.save_figure, (plot_individual, plot_individual_filename)
            )
            _thread.start_new_thread(
                fileIO.save_figure, (plot_combined, plot_combined_filename)
            )
            logger.info("Executed for " + str(time.time() - startTime) + "s.")
            # so that the client won't be getting debug info from other instances.
            logger.removeHandler(logging_handler)
            # ongoingJobs.remove(data['jobID'])
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
        logger.info("Executed for " + str(time.time() - startTime) + "s.")
        # now unbind all log-handlers, so that the logger won't waste its time sending messages to this audience in later calls.
        # redirect the logs since NOW
        rootLogger.removeHandler(logging_handler)
        return jsonify(jobID=data["jobID"], status="error")


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
        coefficient_dict = {
            species: i for i, species in enumerate(data["speciesNames"])
        }
        coefficient_array = []
        for row in data["reactions"]:
            coefficient_array.append([0.0] * len(coefficient_dict))
            for i in range(4):
                speciesName = row[i]
                if speciesName == "":
                    continue  # skip empty entries
                else:
                    # use coefficient_dict that we just built to convert speciesList from name strings to numberial ids
                    speciesID = coefficient_dict[speciesName]
                    if i == 0 or i == 1:  # reactant
                        coefficient_array[-1][speciesID] -= 1
                    elif i == 2 or i == 3:  # product
                        coefficient_array[-1][speciesID] += 1
        data_to_write = {
            "coefficient_dict": coefficient_dict,
            "energy_dict": dict(zip(data["speciesNames"], data["speciesEnergies"])),
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
