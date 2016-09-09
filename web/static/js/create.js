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
var emptyElementaryReaction = $(`
        <tr class="elementaryReaction" draggable="true">
            <td><input></input></td>
            <td>+</td>
            <td><input></input></td>
            <td>=</td>
            <td><input></input></td>
            <td>+</td>
            <td><input></input></td>
            <td><button class="btn btn-danger btn-sm removeReaction">Remove</button>
                <button class="btn btn-success btn-sm balanceReaction">Balance</button></td>
        </tr>
`);
addElementaryReaction = function() {
        var thisElementaryReaction = emptyElementaryReaction.clone();
        $('#elementaryReactionsTbody').append(thisElementaryReaction);
        cells = thisElementaryReaction.children('td'); //just a short-hand.
        cells.children('button.removeReaction').click(removeElementaryReaction);
        cells.children('button.balanceReaction').click(balanceElementaryReaction);
        cells.children('input').change(onSelectChange);
};
removeElementaryReaction = function(e) {
    var thisRow = $(this).parent().parent();
    thisRow.remove();
    checkOverallBalance();
}
balanceElementaryReaction = function(e) {
    var thisRow = $(this).parent().parent();
    var speciesList = $('input', thisRow).map(function(i, obj) {
        return $(obj).val();
    });
    var atomsArray = {};
    for (var i=0; i<3; i++) {
        species = speciesList[i];
        if (species == '') continue; //skip empty species.
        atomsArray = moleculeToAtoms(species, atomsArray, i<2);
    };
    var guessedSpecies = '';
    for (i in atomsArray) {
        var number = atomsArray[i];
        if (number>0) {
            guessedSpecies+=i;
            if (number>1) {
                guessedSpecies += number;
            }
        }
    }
    $('td:nth-child(7) > input',thisRow).val(guessedSpecies);
    checkBalance(thisRow);
    checkOverallBalance();

}
//Behavior of the rows of elementary reactions:
onSelectChange = function(e) {
    var thisRow = $($(this).parent().parent().get(0));
    //Check mass balance
    checkBalance(thisRow);
    checkOverallBalance();
};
//functions for checking mass balances of elementary reactions:
moleculeToAtoms = function(species, atomsArray, ifReactant) {
    //species is a string matching the form "X2Y3".
    //atomsArray is the array to be updated
    atoms = species.match(/([A-Z][a-z]?)(\d*)/g);
    for (var j in atoms) {
        atom = atoms[j];
        number = parseInt(atom.replace(/[^\d]/g, ''), 10) || 1;
        element = atom.replace(/\d*/g, '');
        if (ifReactant) { //reactant
            atomsArray[element] = (atomsArray[element] || 0) + number;
        } else { //product
            atomsArray[element] = (atomsArray[element] || 0) - number;
        };
    };
    return atomsArray;
}
checkBalance = function(thisRow) {
    cells = $('td>input', thisRow).toArray();
    atomsArray = {};
    for (var i in cells) {
        species = cells[i].value;
        if (species == '') continue; //skip empty species.
        atomsArray = moleculeToAtoms(species, atomsArray, i<2);
    };
    if ($.isEmptyObject(atomsArray)//user emptied the reaction
     || (cells[0].value == cells[2].value && cells[1].value == cells[3].value) // or this elem. reaction is trivial
     || (cells[0].value == cells[3].value && cells[1].value == cells[2].value)) { 
        thisRow.removeClass('bg-danger');
        thisRow.removeClass('bg-success');
        return false;
    } else {
        var ifBalanced = true;
        for (var i in atomsArray) {
            if (atomsArray[i] != 0) {
                ifBalanced = false;
                break;
            }
        };
        //now change visible hints:
        if (ifBalanced) {
            thisRow.removeClass('bg-danger');
            thisRow.addClass('bg-success');
        } else {
            thisRow.addClass('bg-danger');
            thisRow.removeClass('bg-success');
        };
        return ifBalanced;
    }
};
checkOverallBalance = function() {
    //this function sets the usablilty of the main proceed button by check whether the set of elementary reactions is valid.
    if ($('#elementaryReactionsTbody>tr.bg-danger').length == 0 && $('#elementaryReactionsTbody > tr.bg-success').length > 0) {
        console.log('Elementary Reactions valid.');
        $('#proceedButton').removeClass('disabled').prop('disabled', false);
    } else {
        console.log('Elementary Reactions invalid.');
        $('#proceedButton').addClass('disabled').prop('disabled', true);
    }
};
cheat = function () {
    var testRxns = [
        ["NO"   , "NO"  , "N2O2", ""    ],
        ["N2O2"    , "Br2"  , "NOBr"   , "NOBr"  ]
    ];
    for (var i in testRxns) {//for each pre-set reaction:
        var rxn = testRxns[i];
        //console.log(rxn); //should be in the shape of ["","","",""];
        addElementaryReaction();
        var selects = $('td > input', $('#elementaryReactionsTbody > tr').last()); //select this newly added row.
        for (i=0; i<4; i++) {
            $(selects[i]).val(rxn[i]);
        }
        checkBalance($('#elementaryReactionsTbody > tr').last());
    }
    checkOverallBalance();
}
$(function() {
    //bind events:
    $('#addElementaryReaction').click(addElementaryReaction);
    $('#proceedButton').click(proceed);
    $('#saveButton').click(save);
    //enable plugins:
    Sortable.create(document.getElementById("elementaryReactionsTbody"),sortableParams);
    cheet('c h e a t', cheat);
    //create the first elementary reaction row:
    addElementaryReaction();
});
//stage 2:
addSpeciesRow = function(speciesName) {
    if (speciesName!='') {
        var $this = $(`
            <tr draggable="true">
                <td class="speciesName">`+speciesName+`</td>
                <td class="energy">
                    <input type="number" value="`+_.random(0,500)+`"></input>
                </td>
                <td class="input-group">
                    <span class="input-group-addon">
                        <input class="ifReactant" type="checkbox" checked></input>
                    </span>
                    <span class="input-group-btn">
                        <button type="button" class="btn btn-default btn-sm editPERsButton dropdown-toggle" data-toggle="dropdown"><span class="glyphicon glyphicon-cog"></span> <span class="caret"></span></button>
                        <ul class="PERs dropdown-menu">
                        </ul>
                    </span>
                </td>
            </tr>`);
        var options = [];

        $( '.dropdown-menu a', $this ).on( 'click', function( event ) {

           var $target = $( event.currentTarget ),
               val = $target.attr( 'data-value' ),
               $inp = $target.find( 'input' ),
               idx;

           if ( ( idx = options.indexOf( val ) ) > -1 ) {
              options.splice( idx, 1 );
              setTimeout( function() { $inp.prop( 'checked', false ) }, 0);
           } else {
              options.push( val );
              setTimeout( function() { $inp.prop( 'checked', true ) }, 0);
           }

           $( event.target ).blur();
              
           console.log( options );
           return false;
        });
        //above: Bootstrap drop-menu of checkboxes, from <https://codepen.io/bseth99/pen/fboKH>.
        for (i in reactions) {
            var reaction_description = reactions[i][0]+' + '+reactions[i][1]+' -> '+reactions[i][2]+' + '+reactions[i][3];
            if ($.inArray(speciesName, reactions[i]) > -1) {
                $thisCheckbox = $('<li><a href="#" class="small" data-value="option1" tabIndex="-1"><input type="checkbox" checked class="rxn'+i+'"/>'+reaction_description+'</a></li>');
            } else {
                $thisCheckbox = $('<li><a href="#" class="small" data-value="option1" tabIndex="-1"><input type="checkbox" disabled class="rxn'+i+'"/>'+reaction_description+'</a></li>');
            };
            $('.dropdown-menu', $this).append($thisCheckbox);
        }
        $('#speciesTbody').append($this);
        $('.ifReactant', $this).click(function() {
            var $this = $(this).parent().parent();
            //hide or show the PER indicators:
            $(".editPERsButton", $this).toggleClass('disabled');
            //enable or disable the save button because we always need at least ONE reagent:
            $('#saveButton').prop('disabled', ($('#speciesTbody .ifReactant:checked').length == 0));
        });
    } else {
        console.log('Empty speciesName given. Skipped.');
    }
}
var reactions;
var speciesList;
proceed = function() {
    //empty species list that might be populated from last time clicking proceed button
    speciesList = [];
    //Get reactions and species:
    reactions = $.makeArray($('#elementaryReactionsTbody>tr.bg-success').map(function() {
        return [$('td>input', this).map(function() {
            speciesList.push(this.value);
            return this.value;
        }).toArray()];
    })).sort();
    //empty species table that might be populated from last time clicking proceed button:
    $('#speciesTbody').html('');
    //Get species
    speciesList = _.uniq(speciesList, function(item, key, a) {return item;});  //unique-ify (i.e. remove repetitive species)
    //newSpeciesList = _.difference(speciesList, available_molecules);
    //add each species to the species table in stage 2:
    _.each(speciesList, addSpeciesRow);
    //suggest a puzzleName:
    if ($('#puzzleName').val() == 'Untitled Puzzle') {
        $('#puzzleName').val(speciesList.join(' '));
    };
    console.log('speciesList',speciesList,'reactions',reactions);
};
pushAlert = function(status, message) {
    var id_int = new Date().getTime();
    $(`<div id="` + id_int + `" class="alert alert-` + status + ` alert-dismissible" role="alert">
           <button type="button" class="close" data-dismiss="alert" aria-label="Close"><span aria-hidden="true">&times;</span></button>
           ` + message + `
       </div>`).appendTo('#speciesModal .modal-body').fadeTo(3000, 500).slideUp(500, function(){
        $(this).alert('close');
    });
}
save = function() {
    var $btn = $(this).button('loading');
    //get required information:
    var speciesNames = [];
    var speciesIfReactants = [];
    var speciesEnergies = [];
    var reagentPERs = {};
    $('#speciesTbody > tr').map(function() {
        var $this = $(this);
        var name = $('.speciesName', $this).text().trim();
        var ifReactant = $('.ifReactant', $this).is(':checked');
        if (ifReactant) {
            var reagentPER = $('.PERs input', $this).map(function(){return this.checked;}).get();
            reagentPERs[name] = reagentPER;
        };
        var energy = parseFloat($('.energy > input', $this).val());
        speciesNames.push(name);
        speciesIfReactants.push(ifReactant);
        speciesEnergies.push(energy);
        //return [name, ifReactant, energy];
    });
    //form parameter object:
    parameters = {
            auth_code: $('#auth_code').val(),
            puzzleName: $('#puzzleName').val(),
            reactions: reactions,
            speciesNames: speciesNames,
            speciesIfReactants: speciesIfReactants,
            speciesEnergies: speciesEnergies,
            reagentPERs: reagentPERs
        };
    console.log(parameters);
    //ajax -- post the job:
    $.ajax({
        url: '/save',
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(parameters),
        dataType: 'json',
        success: function(data) {
            console.log('Responsed:', data);
            pushAlert(data.status, data.message);
            $btn.button('reset');
        },
        error: function(xhr, ajaxOptions, thrownError) {
            pushAlert('danger', 'Error contacting the server: '+thrownError);
            $btn.button('reset');//On error do this
        }
    });
    //close modal
    
};
//=============================================================


var hasEmptyElementaryReaction = true;
if_a_reactant_exists = function () {
    //check whether a reactant exists -- a chemical reaction without a controllable reactant is pointless, right?
    //this works like "as long as there is one set to true, I say true."
    return $('#conditionTbody input.ifReactant').is(':checked');
}





addSpecies = function() {
    addSpeciesRow('','custom');
}
    //Behavior of the rows of elementary reactions -- END


viewControl = function (viewName) {
    $(this).toggleClass('active');
    $(this).data('target').toggle();
}

var sortableParams = {
    ghostClass: "bg-info",  // Class name for the drop placeholder
    chosenClass: "bg-primary",  // Class name for the chosen item
    animation: 150  // ms, animation speed moving items when sorting, `0` — without animation
}
removeSpecies = function(speciesName) {
    //remove the row of this molecule from the sidebar 
    $('.species#'+speciesName).remove();
}
allSpeciesInvolvedInReactions = function () {
    return _.uniq($('tr.elementaryReaction>td>select').map(function(i,obj) {return $(obj).val()}));
}
allSpeciesInvolvedInSpeciesList = function () {
    return _.uniq($('.species').map(function(i,obj) {return $(obj).text()}));
}
