# -*- coding: utf-8 -*-
"""

Created on Mon Feb 27 16:21:35 2017

@author: Bruno
"""

from xlrd import open_workbook
import os
from collections import defaultdict
import json
import io
import re
import sys
import pickle
import itertools

wb = open_workbook(u"../Dados para Chatbot do Livro dos Espíritos.xlsx")
output_file = u"workspace-livro-dos-espiritos.json"
reAllLettersAndSpace = u"[A-Za-záàãâçéêíóôúü\s]"

def eliminateNonAscii(word):
    d = {u"á":u"a",u"à":u"a",u"ã":u"a",u"â":u"a",u"ç":u"c",u"é":u"e",u"ê":u"e",u"í":u"i",u"ó":u"o",u"ô":u"o",u"ú":u"u",u"ü":u"u"}
    for letter in word:
        if letter in d.keys():
            word = word.replace(letter,d[letter])
    return word

#debug
#teste = u"há câmera colchão aço é cítrico cócoras ungüento"
#eliminateNonAscii(teste)

#%% create agent .json
jsonDict = {"intents":[],"name":"livro-dos-espiritos","language":"pt-br",
            "description":"Este agente responde perguntas de acordo com o conteúdo do Livro dos Espíritos de Allan Kardec.",
            "entities":[],"counterexamples":[],"dialog_nodes":[],"metadata":None}


#%% generating entities structure
s_entities = wb.sheet_by_name("Entidades")
# entity_dict: name -> value -> synonym list
entity_dict = defaultdict(lambda: defaultdict(list))
# composite_conditions_dict: composite_entity_name -> list of conditions
composite_conditions_dict = defaultdict(list)
syn2entity_dict = dict()
for row_idx in range(1,s_entities.nrows):
    row = s_entities.row(row_idx)
    name = row[0].value
    if name == "":
        continue
    value = row[1].value
    if value == "":
        continue
    # value needs also to be added as synonym
    for cell in row[1:]:
        synonym = cell.value
        if synonym == "":
            break
        entity_dict[name][value].append(synonym)
        if synonym.find("@") == -1:
            if synonym in syn2entity_dict.keys():
                sys.exit("Error: duplicate value %s found in synonym values. Stopping..."%synonym)
            syn2entity_dict.update({synonym:":".join([name,value])})
    # if is a composite entity adds conditions to composite_conditions_dict
    synStr = "".join(entity_dict[name][value])
    isComposite = (synStr.find("@") >= 0)
    if isComposite:
        for term in entity_dict[name][value]:
            # if non-composite synonym of composite entity
            if term.find("@") == -1:
                conditions = [u"composite"]
            else:
                conditions = sorted(term.replace("@","").split())
            if conditions not in composite_conditions_dict[name]:
                composite_conditions_dict[name].append(conditions)
                    
# prepare json structure for entities
# an entity named "composite" is created to store non-composite synonyms of composite entities
composite_jsonDict = {"description":None,"entity":"composite","source":None,"open_list":False,"values":[],"type":None}
compositeValues_list = composite_jsonDict["values"]
for name in entity_dict:
    nameDict = entity_dict[name]
    valueList = nameDict.keys()
    isComposite = False
    if len(valueList) == 1:
        value = valueList[0]
        synStr = "".join(nameDict[value])
        isComposite = (synStr.find(u"@") >= 0)
    # composite values doesn't require any further entity creation, unless they
    # have synonyms which are not composite
    if isComposite:
        nonCompositeSyns = [syn for syn in nameDict[value] if syn.find(u"@") == -1]
        if len(nonCompositeSyns) > 0:
            # if there are non-composite synonyms they are stored in entity named "composite"
            compositeValues_list.append({"metadata":None,"value":nonCompositeSyns[0],"synonyms":nonCompositeSyns[1:]})
        continue
    entity_jsonDict = {"description":None,"entity":name,"source":None,"open_list":False,"values":[],"type":None}
    entityValues_list = entity_jsonDict["values"]
    for value in nameDict:
        entityValue_dict = {"metadata":None,"value":value,"synonyms":nameDict[value]}
        entityValues_list.append(entityValue_dict)    
    jsonDict["entities"].append(entity_jsonDict)
if len(compositeValues_list) > 0:    
    jsonDict["entities"].append(composite_jsonDict)

json.dump(jsonDict,open(output_file, "w"), indent=2)

#%% generating intents and dialog_nodes json structures

dialog_nodes_list = []
s_intents = wb.sheet_by_name(u"Intenções")
intent_list = [cell.value for cell in s_intents.col(0)[1:]]
# create dialog nodes corresponding to each intent
for intent in intent_list:
    dialog_nodes_list.append({
      "description": None, 
      "parent": None, 
      "dialog_node": intent, 
      "previous_sibling": None, 
      "context": None, 
      "output": {
        "text": {
          "values": [], 
          "selection_policy": "sequential"
        }
      }, 
      "metadata": None, 
      "conditions": "#"+intent, 
      "go_to": {
        "dialog_node": "", 
        "return": None, 
        "selector": "condition"
      }
    })

def build_example(q_marked,terms):
    text = q_marked
    for term in terms:
        term_text = term[1:-1]
        term_text = re.split("\s+@", term_text)[0]
        text = text.replace(term,term_text,1)
    return text

def build_conditions(entities, composite_entities):
    conditions = [list(set(entities))]
    for composite_entity in composite_entities:
        composite_conditions = composite_conditions_dict[composite_entity]
        conditions_tuples = list(itertools.product(conditions,composite_conditions))
        # combine tuples, remove duplicates and return list
        conditions = [list(set(list(t)[0]+list(t)[1])) for t in conditions_tuples]
    return conditions

def process_q_marked(q_marked):
    terms = re.findall("\["+reAllLettersAndSpace+"+\s?@?\w*\]",q_marked)
    entities = []
    composite_entities = []
    for term in terms:
        term = term[1:-1] # eliminating [ and ]
        if term.find("@") > 0:
            term, entity = re.split("\s+@", term)
            composite_entities.append(entity)
        else:
            if term not in syn2entity_dict.keys():
                sys.exit("Error: synonym %s not found in synonym list (row %d). Stopping..."%(eliminateNonAscii(term), row_num))
            entity = syn2entity_dict[term]
            entities.append(entity)
    # using only the high level entities for the examples:
    example = build_example(q_marked,terms) 
    conditions = build_conditions(entities, composite_entities)
    return (example, conditions)

def remove_duplicate_lists(lists_list):
    tuple_list = [tuple(l) for l in lists_list]
    unique_tuple_list = list(set([tuple(item) for item in tuple_list]))
    return [list(t) for t in unique_tuple_list]
    
# intent_example_dict: intent -> list of examples
intent_example_dict = defaultdict(list)
intent_nodes_dict = defaultdict(list)
s_qa = wb.sheet_by_name("Perguntas e Respostas")
for row_idx in range(1,s_qa.nrows):
    row_num = row_idx + 1
    row = s_qa.row(row_idx)
    q = row[0].value
    q_num = re.findall("^(.+?). ", q)[0]
    a = row[1].value #TODO: eliminate numbers from answer
    qa = " ".join([q,a])
    intent = row[2].value
    if intent == "":
        break
    if intent not in intent_list:
        sys.exit("Error: intent %s not found in intents list (row %d). Stopping..."%(intent, row_num))
    conditions_list = []
    for cell in row[3:]:
        q_marked = cell.value
        if q_marked == "":
            break
        example, conditions = process_q_marked(q_marked)
        intent_example_dict[intent].append(example)
        conditions_list.extend(conditions)
    # removing duplicates
    conditions_list = remove_duplicate_lists(conditions_list)
    intent_nodes_dict[intent].append((q_num, conditions_list, qa))

print "%d Q&A rows processed successfully!"%row_idx

#%% build json
def build_example_json(example):
    j =[]
    for t in example:
        text,parameter = t
        if parameter == "":
            j.append({"text":text})
        else:
            j.append({"text":text,"alias":parameter,"meta":"@"+parameter,"userDefined":False})
    return j

for name in intent_example_dict:
    jsonDict = {"userSays":[], "name":name, "auto":True, "contexts":[], "responses":[], "priority":500000, "webhookUsed":True, "webhookForSlotFilling":False, "fallbackIntent":False, "events":[]}
    userSays = []
    for example in intent_example_dict[name]:
        userSays.append({"data":build_example_json(example),"isTemplate":False,"count":0})
    jsonDict["userSays"] = userSays
    responses = [{"resetContexts": False, "action":"getSpiritsBookResponse", "affectedContexts":[], "parameters":[], "messages": [
        {
          "type": 0,
          "speech": "Algo deu errado. Por favor tente mais tarde..."
        }
      ]}]
    parameters = []
    for parameter in intent_parameter_dict[name]:
        isComposite = (parameter in composite_entity_list)
        parameters.append({"dataType":"@"+parameter, "name":parameter, "value":"$"+parameter, "isList":(not isComposite)})
    responses[0]["parameters"] = parameters
    jsonDict["responses"] = responses
    jsonData = json.dumps(jsonDict, ensure_ascii=False, indent=2)
    # using io.open since it allows encoding
    with io.open(intents_path+"/"+name+".json", "w", encoding="utf8") as f:
        f.write(unicode(jsonData))      




