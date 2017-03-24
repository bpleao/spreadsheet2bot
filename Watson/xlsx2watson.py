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
# Debug:
#for row_idx in [1,10,23]:
    row = s_entities.row(row_idx)
    if row[0].value.lower() == "":
        break
    # setting all values to lower case since watson is case insensitive
    synList = [c.value.lower() for c in row[1:]]
    synStr = "".join(synList)
    
#    print(synStr)

    isComposite = (synStr.find(u"@") >= 0)
    if isComposite:
        composite_name = row[0].value.lower()
        nonCompositeSyns = [syn for syn in synList if (len(syn) > 0) and (syn.find(u"@") == -1)]

#        print(nonCompositeSyns)

        if len(nonCompositeSyns) > 0:
            name = u"composite"
            value = nonCompositeSyns[0]
            composite_conditions_dict[composite_name].append([":".join([name,value])])
    else:
        name = row[0].value.lower()
        value = row[1].value.lower()
    # value needs also to be added as synonym
    for cell in row[1:]:
        synonym = cell.value.lower()
        if synonym == "":
            break
        if synonym.find(u"@") == -1:
            if synonym in syn2entity_dict.keys():
                print("Warning: duplicate value %s found in synonym values. Skipping..."%synonym)
            else:
                syn2entity_dict.update({synonym:":".join([name,value])})
                entity_dict[name][value].append(synonym)
        else: # composite
            conditions = sorted(synonym.replace(u"@","").split())
            if conditions not in composite_conditions_dict[composite_name]:
                composite_conditions_dict[composite_name].append(conditions)
            
# prepare json structure for entities
for name in entity_dict:
    entity_jsonDict = {"description":None,"entity":name,"source":None,"open_list":False,"values":[],"type":None}
    entityValues_list = entity_jsonDict["values"]
    nameDict = entity_dict[name]
    for value in nameDict:
        entityValue_dict = {"metadata":None,"value":value,"synonyms":nameDict[value]}
        entityValues_list.append(entityValue_dict)    
    jsonDict["entities"].append(entity_jsonDict)

json.dump(jsonDict,open(output_file, "w"), indent=2)

#%% generating intents structures

s_intents = wb.sheet_by_name(u"Intenções")
intent_list = [cell.value.lower() for cell in s_intents.col(0)[1:]]

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
        term = term[1:-1].lower() # eliminating [ and ]
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
    tuple_list = [tuple(sorted(l)) for l in lists_list]
    unique_tuple_list = list(set(tuple_list))
    return [list(t) for t in unique_tuple_list]
    
# intent_example_dict: intent -> list of examples
intent_example_dict = defaultdict(list)
intent_nodes_dict = defaultdict(lambda: defaultdict())
s_qa = wb.sheet_by_name("Perguntas e Respostas")
for row_idx in range(1,s_qa.nrows):
    row_num = row_idx + 1
    row = s_qa.row(row_idx)
    q = row[0].value
    q_num = re.findall("^(.+?). ", q)[0]
    a = row[1].value #TODO: eliminate numbers from answer
    qa = " ".join([q,a])
    intent = row[2].value.lower()
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
    intent_nodes_dict[intent][q_num] = (conditions_list, qa)

print "%d Q&A rows processed successfully!"%row_idx

#%% ordering conditions (separately for each intent)
condition2questions_dict = defaultdict(lambda: defaultdict(list))
for intent in intent_nodes_dict:
    for num in intent_nodes_dict[intent]:
        q_data = list(intent_nodes_dict[intent][num])
        conditions = q_data[0]
        for condition in conditions:
            condition2questions_dict[intent][tuple(condition)].append(num)

orderedConditions_dict = dict()
for intent in condition2questions_dict:
    all_conditions = condition2questions_dict[intent].keys()
    orderedConditions_dict[intent] = sorted(all_conditions, key=lambda c: len(c), reverse=True)
        

#%% build json
# create dialog nodes corresponding to each intent

question_count = defaultdict(int)

def build_examples_json(examples):
    examples_json = []
    for example in examples:
        examples_json.append({"text":example})
    return examples_json

def build_node_name(questions, increment_flag=True):
    count_list = [str(question_count[q]) if question_count[q] > 0  else "" for q in questions]
    if increment_flag:
        for q in questions:
            question_count[q] += 1
    count_question_list = ["_".join(t) for t in zip(questions, count_list)]
    return "Pergunta "+" ".join(count_question_list)
    
previous_intent = None
intents_json = []
dialog_nodes_json = []
for intent in intent_list:
    intents_json.append({
      "description": None, 
      "intent": intent, 
      "examples": build_examples_json(intent_example_dict[intent])
    })
    
    first_condition = orderedConditions_dict[intent][0]
    questions = condition2questions_dict[intent][first_condition]
    first_node_name = build_node_name(questions, False) 
    
    dialog_nodes_json.append({
      "description": None, 
      "parent": None, 
      "dialog_node": intent, 
      "previous_sibling": previous_intent, 
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
        "dialog_node": first_node_name, 
        "return": None, 
        "selector": "condition"
      }
    })
    previous_intent = intent
    
    previous_node_name = None
    for condition in orderedConditions_dict[intent]:
        questions = condition2questions_dict[intent][condition]
        node_name = build_node_name(questions)
        dialog_nodes_json.append({
          "description": None, 
          "parent": intent, 
          "dialog_node": node_name, 
          "previous_sibling": previous_node_name, 
          "context": None, 
          "output": {
            "text": {
              "values": [list(intent_nodes_dict[intent][q])[1] for q in questions], 
              "selection_policy": "random"
            }
          }, 
          "metadata": None, 
          "conditions": " && ".join([u"@"+c for c in condition]), 
          "go_to": None
        })
        previous_node_name = node_name
    
    # adding default action for intent
    dialog_nodes_json.append({
      "description": None, 
      "parent": intent, 
      "dialog_node": "True_"+intent, 
      "previous_sibling": node_name, 
      "context": None, 
      "output": {
        "text": {
          "values": [
            "Não entendi. Por favor faça uma pergunta a respeito do conteúdo do Livro dos Espíritos."
          ], 
          "selection_policy": "sequential"
        }
      }, 
      "metadata": None, 
      "conditions": "True", 
      "go_to": None
    })

jsonDict["intents"] = intents_json
jsonDict["dialog_nodes"] = dialog_nodes_json

json.dump(jsonDict,open(output_file, "w"), indent=2)

print "json file %s created successfully!"%output_file


