#!/usr/local/bin/python3.5
# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, jsonify, send_file#, redirect, url_for, send_from_directory
from flask_sse import sse
from flask.ext.compress import Compress
#from .crossdomain import crossdomain
from pprint import pprint
##relative import fix. according to this: http://stackoverflow.com/a/12869607/1147061
#import sys
#sys.path.append('..')
from kernel.engine import driver, fileIO
driver.temp_diag = False
driver.system_output = pprint
from kernel.data import puzzle_class, condition_class, solution_class, reaction_mechanism_class
import numpy as np
import os, sys, time, mimetypes, _thread, jsonschema, json, hashlib, warnings
#suppress warnings.. they disturb me.
warnings.filterwarnings("ignore")

#one-liners:
all_files_in = lambda mypath, end='': [os.path.splitext(os.path.basename(f))[0] for f in os.listdir(mypath) if os.path.isfile(os.path.join(mypath, f)) and not f.startswith('.') and f.endswith(end)]

class ListStream:
    '''One ListStream corresponds to one unique computation job.
    c.f.: http://stackoverflow.com/questions/21341096/redirect-print-to-string-list'''
    def __init__(self, jobID):
        self.jobID = jobID
    def write(self, *args, end="\n"):
        s = ''
        for arg in args:
            s += ' ' + str(arg)
        with app.app_context():
            try:
                sse.publish({"data": s+end}, channel=self.jobID)
            except AttributeError:
                sys.__stdout__.write(' * Orphaned Message: ' + s)
    def flush(self):
        pass
    def __enter__(self):
        sys.stdout = self
        return self
    def __exit__(self, ext_type, exc_value, traceback):
        sys.stdout = sys.__stdout__  

#Global variables, and also initializing the webapp using Flask framework:
path_root = 'results/'
if_runningOnline = ('DYNO' in os.environ)   # detect whether on Heroku
if_useCache =  if_runningOnline       # use cache only when in production mode; in other words, don't use cache on local machine
AUTH_CODE = '123'
#ongoingJobs = []

app = Flask(__name__)
Compress(app) # https://github.com/libwilliam/flask-compress

#redis configuation, for SSE support:
app.config["REDIS_URL"] = os.environ.get("REDIS_URL") or "redis://localhost"  #'os.environ.get("REDIS_URL")' is for Heroku and "redis://localhost" is meant for localhost.
app.register_blueprint(sse, url_prefix='/stream')

#load JSON schema for Puz file for validation:
with open("puzzles/schema.js", 'r') as f:
    schema = f.read()
schema = json.loads(schema)

@app.route('/plot', methods=['POST', 'OPTIONS'])
def plot():
    data = request.get_json()               #receive JSON data
    stream = ListStream(data['jobID'])      #change the output stream.
    driver.stream = stream
    driver.plotter.stream = stream
    startTime = time.time()                 #start timer
    # prepare directories:
    path_puzzle    = path_root+data['puzzle']+'/'
    path_condition = path_puzzle+'condition_'+data['conditionID']+'/'
    path_solution  = path_condition+'solution_'+data['solutionID']+'/'
    # prepare figure file_names:
    plot_name = path_solution+'/'+str(data['temperature'])
    plot_individual_filename = plot_name + "_individual.svg"
    plot_combined_filename   = plot_name + "_combined.svg"
    # try whether result already generated:
    if os.path.isfile(plot_individual_filename) and os.path.isfile(plot_combined_filename) and if_useCache:
        stream.write("Figures already generated before. Skipped.")
        with open(plot_individual_filename, 'r') as content_file:
            plot_individual = content_file.read()
        with open(plot_combined_filename, 'r') as content_file:
            plot_combined = content_file.read()
    #elif data['jobID'] in ongoingJobs: # not a job already done! let's see if anyone has been doing it...?
    #    stream.write('Someone already submitted identical plotting job.')
    #    return # TODO: proper handle the conflict!
    else: # we have to plot it ourselves! orz...
        temperature = data['temperature']       #just a short hand
        stream.write('================== RECEIVED PLOTTING JOB ==================')
        if not os.path.isdir(path_solution): #we check the deepest folder, which implies all parent-grandparent folders exist.
            os.makedirs(path_solution)
        #Now start preparing the instances of custom classes for further actual use in Engine.Driver:
        #    (0) First of all, load the Puzzle Data into backend:
        with open("puzzles/"+data['puzzle']+".puz") as json_file:
            puzzleData = json.load(json_file)
            stream.write('    (0) Successfully loaded Puzzle Data from file!')
        #    (1) Instance of the Puzzle class:
        #           (1.1) general data:
        elemRxns    = np.array(puzzleData['coefficient_array'], dtype = float)
        energy_dict = puzzleData['energy_dict']
        Ea          = None #puzzleData['transition_state_energies']
        speciesList = sorted(puzzleData['coefficient_dict'], key=puzzleData['coefficient_dict'].get) #stream.write('        SpeciesList involved are:',' '.join(speciesList))
        num_rxn     = len(puzzleData['coefficient_array'])
        num_mol     = len(speciesList)
        #           (1.2) data about the reagents, used in pre-equilibrium computations:
        reagentsDict = []
        for reagent, PERsToggles in puzzleData['reagentPERs'].items():
            reagentID = puzzleData['coefficient_dict'][reagent]
            preEqulElemRxns = [puzzleData['coefficient_array'][i] for i in range(num_rxn) if PERsToggles[i]]
            if preEqulElemRxns == []:
                stream.write('        For the reagent #'+str(reagentID)+' "'+reagent+'", no pre-equilibration needed.')
                preEqulElemRxns = np.array([[0.0]], dtype = float) 
                reagent_speciesList = [reagent]
            else:
                preEqulElemRxns = np.array(preEqulElemRxns, dtype = float) # convert it into a numpy dict
                stream.write('        For the reagent #'+str(reagentID)+' "'+reagent+'", the following reactions present: //omitted//')#\n',preEqulElemRxns)
                if_uninvolvedSpecies = np.all(preEqulElemRxns == False, axis = 0) # a boolean array of whether each species specified in the puzzle file is present in this set of ElemRxns for preEqul.
                # now, remove unused species to simplify the rxn. set used for pre-equilibration of this particular reagent:
                displacement = 0
                for speciesID in range(num_mol): # mask and remove columns of those unused species
                    if if_uninvolvedSpecies[speciesID]: # if this species is not used:
                        preEqulElemRxns = np.delete(preEqulElemRxns, speciesID-displacement, 1) # http://stackoverflow.com/questions/1642730/how-to-delete-columns-in-numpy-array
                        displacement += 1
                stream.write('            speciesList         : '+str(speciesList))
                stream.write('            if_uninvolvedSpecies: '+str(if_uninvolvedSpecies))
                stream.write('            This should mask the previous matrix into: //omitted//')#\n',preEqulElemRxns)
                reagent_speciesList = [speciesList[i] for i in range(num_mol) if not if_uninvolvedSpecies[i]]
            reagent_num_rxn = len(preEqulElemRxns)
            reagent_num_mol = len(reagent_speciesList)
            stream.write('            reagent_num_rxn: '+str(reagent_num_rxn))
            stream.write('            reagent_num_mol: '+str(reagent_num_mol))
            stream.write('            reagent_speciesList: '+str(reagent_speciesList))
            reagentsDict.append((reagent, reaction_mechanism_class.reaction_mechanism(reagent_num_rxn, reagent_num_mol, reagent_speciesList, preEqulElemRxns, energy_dict)))
        #stream.write('reagentsDict:',reagentsDict)
        #         - - - - - - - - - - - - - - -
        this_puzzle = puzzle_class.puzzle(num_rxn, num_mol, speciesList, elemRxns, energy_dict, reagent_dictionary = reagentsDict, Ea = Ea)
        #                                 num_rxn, num_mol, speciesList, elemRxns, energy_dict -> fed to class "reaction_mechanism"
        #                                                                                                        reagentsDict, Ea -> fed to class puzzle
        stream.write('    (1) Puzzle Instance successfully created.')
        #    (2) Instance of the Condition class:
        #rxn_temp = temperature
        #Each entry in data['conditions'] is of the form:
        #     [name of the reactant, amount, its fridge temperature]
        r_names  = [reactant['name']        for reactant in data['conditions']]
        r_concs  = [reactant['amount']      for reactant in data['conditions']]
        r_temps  = [reactant['temperature'] for reactant in data['conditions']]
        m_concs  = [0.0] * num_mol
        #         - - - - - - - - - - - - - - -
        this_condition = condition_class.condition(temperature, speciesList, r_names, r_temps, r_concs, m_concs)
        stream.write('    (2) Condition Instance successfully created.')
        #    (3) Instance of the Solution class: 
        coefficient_array_proposed = []
        for each_rxn_proposed in data['reactions']:
            coefficient_line_proposed = [0]*num_mol
            for each_slot in each_rxn_proposed:
                if each_slot is not '':
                    coefficient_line_proposed[speciesList.index(each_slot)] += 1
            coefficient_array_proposed.append(coefficient_line_proposed)
        num_rxn_proposed  = len(coefficient_array_proposed)
        #         - - - - - - - - - - - - - - -
        this_solution = solution_class.solution(num_rxn_proposed, num_mol, speciesList, coefficient_array_proposed, energy_dict)
        stream.write('    (3) Solution Instance successfully created.')
        #Finally, drive the engine with these data:
        stream.write('    (4) Simulating...')
        stream.write('         (a) True Model first:', end="")
        trueModel_fileName = path_condition + "plotData_t_" + str(temperature) #anticipate the file name where the true model's data is stored
        if os.path.isfile(trueModel_fileName + '_.dat') and if_useCache:
            stream.write(" cache available. Load from it.")#Mechanism(true)+Condition for this puzzle already simulated before. Take advantage of the cache now...")
            written_true_data = fileIO.load_modelData(trueModel_fileName + '_.dat')
        else:
            stream.write(" simulating...")#Mechanism(true)+Condition for this puzzle not calculated before; do it now...")
            written_true_data = driver.drive_data(puzzle = this_puzzle, 
                              puzzle_path = path_puzzle, #this is merely for backward compatibility. 
                              condition = this_condition, 
                              condition_path = path_condition, 
                              progress_tick = lambda x: stream.write(x))
            stream.write("            The result is a",type(written_true_data))
        stream.write('         (b) User Model then:', end="")
        userModel_fileName = path_solution  + "plotData_t_" + str(temperature) #anticipate the file name where the true model's data is stored
        if (os.path.isfile(userModel_fileName+'_.dat') or os.path.isfile(userModel_fileName+'_Failed')) and if_useCache:
            if os.path.isfile(userModel_fileName+'_.dat'):
                stream.write(" cache available. Load from it.")#Mechanism(solution)+Condition for this puzzle already simulated before. Take advantage of the cache now...")
                written_user_data = fileIO.load_modelData(userModel_fileName + '_.dat')
            elif os.path.isfile(userModel_fileName+'_Failed'):
                stream.write(" UserModel failed as told by flag file.")#Mechanism(solution)+Condition for this puzzle already simulated before. Take advantage of the cache now...")
                written_user_data = False
        else:
            stream.write(" simulating...")#Mechanism(solution)+Condition for this puzzle not calculated before; do it now...")
            written_user_data = driver.drive_data(puzzle = this_puzzle, 
                              puzzle_path = path_puzzle, #this is merely for backward compatibility. 
                              condition = this_condition, 
                              condition_path = path_condition, 
                              progress_tick = lambda x: stream.write(x),
                              solution = this_solution, 
                              solution_path = path_solution,
                              written_true_data = written_true_data)
            stream.write("             Got result:",type(written_user_data))
        stream.write('    (5) Drawing plots... ', end = '')
        (plot_individual, plot_combined) = driver.plotter.sub_plots( Temperature = temperature,
                      plottingDict            = puzzleData['coefficient_dict'],
                      solution_fileName       = path_solution  + '/' + 'plotData_t_' + str(temperature),
                      condition_fileName      = path_condition + '/' + 'plotData_t_' + str(temperature),
                      written_true_data       = written_true_data,
                      written_user_data       = written_user_data)
        #end Timer
        stream.write('    (6) Now that everything is finished, write simulated data to file for caching...')
        _thread.start_new_thread(fileIO.save_modelData, (written_true_data, trueModel_fileName))
        _thread.start_new_thread(fileIO.save_modelData, (written_user_data, userModel_fileName))
        _thread.start_new_thread(fileIO.save_figure, (plot_individual, plot_individual_filename))
        _thread.start_new_thread(fileIO.save_figure, (plot_combined  , plot_combined_filename))
        stream.write('Executed for', time.time() - startTime, 's.')
        #sys.stdout = sys.__stdout__ #reset the stdout streamer so that the client won't be getting debug info from other instances.
        #ongoingJobs.remove(data['jobID'])
    return jsonify(jobID = data['jobID'],
         plot_individual = plot_individual,
           plot_combined = plot_combined,
           temperature = temperature) # serving result figure files via "return", so as to save server calls
@app.route('/save', methods=['POST', 'OPTIONS'])
def save():
    data = request.get_json()               #receive JSON data
    print('Data received:')
    pprint(data)
    if not request.remote_addr == '127.0.0.1':
        if not data['auth_code'] == AUTH_CODE:
            return jsonify(status = 'danger', message = 'Authentication failed. Check your password.')
    # Else, validate with jsonschema:
    existing_puzzles = all_files_in('puzzles')
    if data['puzzleName'] in existing_puzzles:
        return jsonify(status = 'danger', message = 'Puzzle already exists. Try another name.')
    try:
        jsonschema.validate(data, schema)
    except jsonschema.exceptions.ValidationError as e:
        return jsonify(status = 'danger', message = e.message)
    else:
        # now convert:
        coefficient_dict = {species:i for i,species in enumerate(data['speciesNames'])}
        coefficient_array = []
        for row in data["reactions"]:
            coefficient_array.append([0.0]*len(coefficient_dict))
            for i in range(4):
                speciesName = row[i]
                if speciesName == '':
                    continue #skip empty entries
                else:
                    speciesID = coefficient_dict[speciesName] #use coefficient_dict that we just built to convert speciesList from name strings to numberial ids
                    if i==0 or i==1: #reactant
                        coefficient_array[-1][speciesID] -= 1
                    elif i==2 or i==3: #product
                        coefficient_array[-1][speciesID] += 1
        data_to_write = {
            'coefficient_dict': coefficient_dict,
            'energy_dict': dict(zip(data["speciesNames"], data["speciesEnergies"])),
            'coefficient_array': coefficient_array,
            'reagents': list(data['reagentPERs'].keys()),
            'reagentPERs': data['reagentPERs']
        }
        print('Data prepared:')
        pprint(data_to_write)
        with open('puzzles/'+data['puzzleName']+'.puz','w') as f:
            try:
                json.dump(data_to_write, f, indent=4)
            except Exception as e:
                print(e)
                return jsonify(status = 'danger', message = 'Error occured. Can\'t save.')
            else:
                return jsonify(status = 'success', message = 'Puzzle successfully saved.')
@app.route('/create')
def serve_page_create():
    return render_template('main.html', mode='create', ip = request.remote_addr.replace('.','_'))
@app.route('/play/<puzzleName>')
def serve_page_play(puzzleName):
    with open("puzzles/"+puzzleName+".puz") as json_file:
        puzzleData = json_file.read()
    return render_template('main.html', mode='play', puzzleName=puzzleName, puzzleData = puzzleData, ip = request.remote_addr.replace('.','_'))
@app.route('/')
def serve_page_index():
    puzzleList = all_files_in('puzzles', end = ".puz")
    return render_template('index.html', puzzleList = puzzleList)
