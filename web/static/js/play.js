//JS fixes START
$.urlParam = function(name) {
    var results = new RegExp('[\?&]' + name + '=([^&#]*)').exec(window.location.href);
    if (!results) {
        return '';
    }
    return results[1] || '';
}
if (typeof(String.prototype.trim) === "undefined") {
    String.prototype.trim = function() {
        return String(this).replace(/^\s+|\s+$/g, '');
    };
}
if (!Object.keys) Object.keys = function(o) {
    if (o !== Object(o)) throw new TypeError('Object.keys called on non-object');
    var ret = [],
        p;
    for (p in o)
        if (Object.prototype.hasOwnProperty.call(o, p)) ret.push(p);
    return ret;
}

dict_reverse = function (obj) {
  var new_obj = {};
  for (var prop in obj) {
    if(obj.hasOwnProperty(prop)) {
      new_obj[obj[prop]] = prop;
    }
  }
  return new_obj;
};
//JS fixes END
print = function(content) {
    $('#console').append('<p>' + content + '</p>');
}
var emptyElementaryReaction = $(`
                    <tr class="elementaryReaction" draggable="true">
                        <td>
                            <select class="form-control">
                                <option value=""></option>
                            </select>
                        </td>
                        <td>
                            +
                        </td>
                        <td>
                            <select class="form-control">
                                <option value=""></option>
                            </select>
                        </td>
                        <td>
                            =
                        </td>
                        <td>
                            <select class="form-control">
                                <option value=""></option>
                            </select>
                        </td>
                        <td>
                            +
                        </td>
                        <td>
                            <select class="form-control">
                                <option value=""></option>
                            </select>
                        </td>
                        <td>
                            <!--<div class="checkbox">
                                <label>
                                    <input type="checkbox"> Disable
                                </label>
                            </div>-->
                            <button type="submit" class="btn btn-danger btn-sm removeReaction">
                                Remove
                            </button>
                        </td>
                    </tr>
`);
var puzzleData;
var hasEmptyElementaryReaction = true;
//functions for checking mass balances of elementary reactions:
checkOverallBalance = function() {
    if ($('#elementaryReactionsTbody>tr.bg-danger').length == 0 && $('#elementaryReactionsTbody > tr.bg-success').length > 0) {
        $('#plotButton').removeClass('disabled').prop('disabled', false);
    } else {
        $('#plotButton').addClass('disabled').prop('disabled', true);
    }
}
checkBalance = function(thisRow) {
    cells = $('td>select', thisRow).toArray();
    atomsArray = {};
    for (var i in cells) {
        //console.log(i,cells[i]);
        species = cells[i].value;
        if (species == '') continue; //skip empty species.
        atoms = species.match(/([A-Z][a-z]?)(\d*)/g);
        for (var j in atoms) {
            atom = atoms[j];
            number = parseInt(atom.replace(/[^\d]/g, ''), 10) || 1;
            element = atom.replace(/\d*/g, '');
            if (i < 2) { //reactant
                atomsArray[element] = (atomsArray[element] || 0) + number;
            } else { //product
                atomsArray[element] = (atomsArray[element] || 0) - number;
            };
        };
    }
    if ($.isEmptyObject(atomsArray)) { //user emptied the reaction
        thisRow.removeClass('bg-danger');
        thisRow.removeClass('bg-success');
    } else {
        var ifBalanced = true;
        for (var i in atomsArray) {
            if (atomsArray[i] != 0) {
                ifBalanced = false;
                break;
            }
        }
        if (ifBalanced) {
            thisRow.removeClass('bg-danger');
            thisRow.addClass('bg-success');
        } else {
            thisRow.addClass('bg-danger');
            thisRow.removeClass('bg-success');
        }
        //console.log(ifBalanced, atomsArray);
        return ifBalanced;
    }
};
//Behavior of the rows of elementary reactions:
onSelectChange = function(e) {
    //console.log(this.value);
    var thisRow = $($(this).parent().parent().get(0));
    //Check mass balance
    checkBalance(thisRow);
    checkOverallBalance();
};
removeElementaryReaction = function(e) {
    $(this).parent().parent().remove();
    checkOverallBalance();
}
addElementaryReaction = function() {
        thisElementaryReaction = emptyElementaryReaction.clone();
        $('#elementaryReactionsTbody').append(thisElementaryReaction);
        cells = thisElementaryReaction.children('td'); //just a short-hand.
        cells.children('button.removeReaction').click(removeElementaryReaction);
        cells.children('select').change(onSelectChange);
        $('td>select',thisElementaryReaction).on('dragover', function (ev) {
            ev.originalEvent.preventDefault();
        });
        $('td>select',thisElementaryReaction).on('drop', function (ev) {
            ev.originalEvent.preventDefault();
            var data = ev.originalEvent.dataTransfer.getData("species");
            if (data!=undefined && data!='') {
                $(this).val(data);
                $(this).change();
            };
        });
}
    //Behavior of the rows of elementary reactions -- END
var serverEventListeners = {};
plot = function() {
    //Get reactions
    var reactions = $('#elementaryReactionsTbody>tr.bg-success').map(function() {
        return [$('td>select', this).map(function() {
            return this.value;
        }).toArray()];
    });
    //Get temperature
    var temperature = parseFloat(document.getElementById('reactionTemperature').value, 10);
    //Get conditions
    var conditions = $('#conditionTbody > tr.reactant').map(function() {
        var name = $('td.species', this).text().trim();
        var amount = parseFloat($('td>input.amount', this).val());
        var temperature = parseFloat($('td>input.temperature', this).val());
        return {name, amount, temperature};
    });
    //make jobID. this should better be unique across all users and all calls.
    var d = new Date();
    var reactions = $.makeArray(reactions).sort();
    var conditions = $.makeArray(conditions).sort();
    var solutionID = md5(JSON.stringify(reactions));
    var conditionID = md5(JSON.stringify(conditions));
    var jobID = ip+'_'+conditionID+'_'+temperature.toString()+'_'+solutionID+'_'+d.getTime().toString();//$('#result_nav > li').length + 1;
    if ($('#'+jobID).length>0) {
        $('#'+jobID+'_nav > a').trigger('click');
    } else {
        var $btn = $(this).button('loading');
        parameters = {
                puzzle: puzzleName,
                reactions: reactions,
                temperature: temperature,
                conditions: conditions,
                jobID: jobID,
                solutionID: solutionID,
                conditionID: conditionID
            }
        //console.log(parameters);
        //Placeholder for results:
        var thisResultPanel = $(`<div role="tabpanel" class="tab-pane" id="`+jobID+`">
                                <div class="panel-body tab-content">
                                    <div role="tabpanel" class="tab-pane view_individual">
                                    </div>
                                    <div role="tabpanel" class="tab-pane view_combined">
                                    </div>
                                    <pre role="tabpanel" class="tab-pane view_info language-python"></pre>
                                </div>
                                <div class="panel-footer"></div>
                             </div>`);
        thisResultPanel.appendTo('#result_panels');
        $('#viewControl a.active').tab('show');
        var thisResultNavPage = $(`<li role="presentation" id="`+jobID+`_nav">
                                    <a href="#`+jobID+`" role="tab" data-toggle="tab">Plotting...</a>
                                </li>`);
        thisResultNavPage.appendTo('#result_nav');
        $('a[href=".view_info"]').trigger('click'); //switch to message tab (i call it "view"). Use "click" instead of "tab show" to make sure styling works.
        $('a', thisResultNavPage).trigger('click');//switch to this view now instantly. I didn't implement this at first because there was nothing to show, but now we have debug info to display.
        //Start listening to the server about how it gonna be doing:
        var source = new EventSource("/stream?channel="+jobID);//See: http://flask-sse.readthedocs.io/en/latest/advanced.html#channels
        serverEventListeners[jobID] = source;
        source.jobID = jobID;
        /*source.onopen = function() {
            console.log('EventSource opened:',this);
        };*/
        source.onmessage = function(event) {
            /*console.log(event.data);
            console.log(this);*/
            var data = JSON.parse(event.data);
            var $infoPanel = $('#'+this.jobID+' > .panel-body > .view_info');
            $infoPanel.text($infoPanel.text() + data.data);
            $infoPanel.scrollTop($infoPanel.prop("scrollHeight"));
        };
        //ajax -- post the job:
        $.ajax({
            url: '/plot',
            type: 'POST',
            contentType: 'application/json',
            data: JSON.stringify(parameters),
            dataType: 'json',
            success: function(data) {
                console.log('Responsed:', data);
                if (data.status == 'success') {
                    $('#'+data.jobID+' > .panel-footer').html('Completed at <code>'+Date()+'</code>.');
                    $('#'+data.jobID+' > .panel-body > .view_individual').append(data.plot_individual);
                    $('#'+data.jobID+' > .panel-body > .view_combined').append(data.plot_combined);
                    $('#'+data.jobID+'_nav > a').text('At ' + data.temperature.toString()+'K');
                    serverEventListeners[data.jobID].close();
                    $('a[href=".view_combined"]').trigger('click'); //switch to combined tab (i call it "view"). Use "click" instead of "tab show" to make sure styling works.
                    console.log($('#'+data.jobID+' > .panel-body > .view_info').get())
                    Prism.highlightElement($('#'+data.jobID+' > .panel-body > .view_info').get()[0]);
                    $btn.button('reset');
                } else {
                    $('#'+data.jobID+'_nav > a').text('Failed Job');
                    serverEventListeners[data.jobID].close();
                    console.log($('#'+data.jobID+' > .panel-body > .view_info').get())
                    Prism.highlightElement($('#'+data.jobID+' > .panel-body > .view_info').get()[0]);
                    $btn.button('reset');
                };
            },
            error: function(xhr, ajaxOptions, thrownError) {
                //This should seldomly happen. This is triggered nearly only when the connection fails.
                $btn.button('reset');//On error do this
            }
        });
    };
}
cheat = function () {
    var reversed_coefficient_dict = dict_reverse(puzzleData.coefficient_dict);
    for (var i in puzzleData.coefficient_array) {//for each pre-set reaction:
        var rxn = puzzleData.coefficient_array[i];
        //console.log(rxn);
        var rxn_slots = ["","","",""];
        for (var j in rxn) { //for each cofficient recorded in this particular reaction:
            var if_bad = false;
            var this_species = reversed_coefficient_dict[j];
            //console.log(this_species, rxn[j]);
            if (rxn[j]==1) {
                if (rxn_slots[0]=="") {
                    rxn_slots[0] = this_species;
                } else if (rxn_slots[1]=="") { //first slot for reactant is occupied.
                    rxn_slots[1] = this_species;
                } else {
                    console.log('Too many reactants given.');
                    if_bad = true;
                    break;//prevent even going into the next species/coefficient.
                };
            } else if (rxn[j]==2) {
                if (rxn_slots[0]=="" && rxn_slots[1]=="") {
                rxn_slots[0] = this_species;
                rxn_slots[1] = this_species;
                } else {
                    console.log('Too many reactants given.');
                    if_bad = true;
                    break;//prevent even going into the next species/coefficient.
                };
            } else if (rxn[j]==-1) {
                if (rxn_slots[2]=="") {
                    rxn_slots[2] = this_species;
                } else if (rxn_slots[3]=="") { //first slot for product is occupied.
                    rxn_slots[3] = this_species;
                } else {
                    console.log('Too many products given:', rxn_slots);
                    if_bad = true;
                    break;//prevent even going into the next species/coefficient.
                };
            } else if (rxn[j]==-2) {
                if (rxn_slots[2]=="" && rxn_slots[3]=="") {
                rxn_slots[2] = this_species;
                rxn_slots[3] = this_species;
                } else {
                    console.log('Too many products given.');
                    if_bad = true;
                    break;//prevent even going into the next species/coefficient.
                };
            } else if (rxn[j]!=0) {
                console.log('Bad coefficient recorded.');
                if_bad = true;
                break;//prevent even going into the next species/coefficient.
            };
            //console.log(rxn_slots);
        }
        if (if_bad) {
            console.log('Error happened while parsing a coefficient. Skipping to next pre-recorded reaction.');
            continue;//to next reaction
        } else {//now write this reaction to table
            addElementaryReaction();
            var selects = $('td > select', $('#elementaryReactionsTbody > tr').last());
            for (i=0; i<4; i++) {
                $(selects[i]).val(rxn_slots[i]);
            }
            checkBalance($('#elementaryReactionsTbody > tr').last());
        };
    }
    checkOverallBalance();
}
initializePuzzle = function(data) {
    //Start filling up Selects
    $.each(data.coefficient_dict, function(key, element) {
        emptyElementaryReaction.children('td').children('select').append($('<option>', {
            value: key,
            text: key
        }));
    });
    //Add the first reaction onto the UI:
    addElementaryReaction();
    //fill up the configuration table:
    $.each(data.coefficient_dict, function(key, element) {
        if ($.inArray(key, data.reagents) > -1) { //this species is a reactant
            $('#conditionTbody').prepend(`
                <tr class="reactant" draggable="true">
                    <td class="species" draggable="true">
                        ` + key + `
                    </td>
                    <td>
                        <input class="amount" type="number" value="1" min="0"></input>
                    </td>
                    <td>
                        <input class="temperature" type="number" value="273.15" min="0"></input>
                    </td>
                </tr>`);
        } else { //this species is a product or intermediate
            $('#conditionTbody').append(`
                <tr class="nonReactant" draggable="true">
                    <td class="species" draggable="true">
                        ` + key + `
                    </td>
                    <td>
                        -
                    </td>
                    <td>
                        -
                    </td>
                </tr>`);
        };
    });
    //Start binding drag events:
    $('#conditionTbody>tr>td.species').on('dragstart', function(evt) {
        evt.originalEvent.dataTransfer.setData("species", $(this).text().trim());
    });
}
viewControl = function (viewName) {
    $(this).toggleClass('active');
    $(this).data('target').toggle();
}

var sortableParams = {
    ghostClass: "bg-info",  // Class name for the drop placeholder
    chosenClass: "bg-primary",  // Class name for the chosen item
    animation: 150  // ms, animation speed moving items when sorting, `0` — without animation
}
$(function() {
    //Select Puzzle to load:
    initializePuzzle(puzzleData);
    //bind events:
    $('#addElementaryReaction').click(addElementaryReaction);
    $('#plotButton').click(plot);
    Sortable.create(document.getElementById("elementaryReactionsTbody"),sortableParams);
    Sortable.create(document.getElementById("conditionTbody"),sortableParams);
    Sortable.create(document.getElementById("result_nav"),sortableParams);
    cheet('c h e a t', cheat);
    //for "Display result only in:"
    $('[data-toggle="btns"] .btn').on('click', function(){
        var $this = $(this);
        $this.parent().find('.active').removeClass('active');
        $this.addClass('active');
    });
});