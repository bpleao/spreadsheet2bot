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

wb = open_workbook(u"../Dados para Chatbot do Livro dos Espíritos.xlsx")
output_path = u"Livro_dos_Espíritos_Novo"

# define (and create if needed) output folders
if not os.path.exists(output_path):
    os.makedirs(output_path)
entities_path = output_path + "/entities"
if not os.path.exists(entities_path):
    os.makedirs(entities_path)
intents_path = output_path + "/intents"
if not os.path.exists(intents_path):
    os.makedirs(intents_path)

def eliminateNonAscii(word):
    d = {u"á":u"a",u"à":u"a",u"ã":u"a",u"â":u"a",u"ç":u"c",u"é":u"e",u"ê":u"e",u"í":u"i",u"ó":u"o",u"ô":u"o",u"ú":u"u",u"ü":u"u"}
    for letter in word:
        if letter in d.keys():
            word = word.replace(letter,d[letter])
    return word

#debug
#teste = u"há câmera colchão aço é cítrico cócoras ungüento"
#eliminateNonAscii(teste)

#%% TODO: create agent.json


#%% generating entities files
s_entities = wb.sheet_by_name("Entidades")
# entity_dict: name -> value -> synonym list
entity_dict = defaultdict(lambda: defaultdict(list))
for row_idx in range(1,s_entities.nrows):
    row = s_entities.row(row_idx)
    #debug
#    print [item.value for item in row]
    # non ascii chars are not accepted as names or values
    name = eliminateNonAscii(row[0].value)
    if name == "":
        continue
    #debug
#    print "  "+name
    value = eliminateNonAscii(row[1].value)
    if value == "":
        continue
    #debug
#    print "    "+value
    # synonyms accept non ascii. value needs also to be added as synonym
    for cell in row[1:]:
        synonym = cell.value
        if synonym == "":
            break
        # debug
#        print synonym
        entity_dict[name][value].append(synonym)
    #debug
#    print "      "+"_".join(entity_dict[name][value])

# write entity json files and build list with all entities in format name:value
entity_list = []
composite_entity_list = []
for name in entity_dict:
    jsonDict = {"name":name,"isOverridable": True,"entries": [],"isEnum": "","automatedExpansion": False}
    nameDict = entity_dict[name]
    valueList = nameDict.keys()
    #debug
#    print name
#    print valueList
    isComposite = False
    if len(valueList) == 1:
        value = valueList[0]
        synStr = "".join(nameDict[value])
        #debug
#        print(synStr)
        isComposite = (synStr.find(u"@") >= 0)
    entries = []
    if isComposite:
        entity_list.append(name)
        composite_entity_list.append(name)
        jsonDict["isEnum"] = True
        for item in nameDict[value]:
            entries.append({"value":item,"synonyms":[item]})
    else:
        jsonDict["isEnum"] = False
        for value in valueList:
            entity_list.append(":".join([name,value]))
            entries.append({"value":value,"synonyms":nameDict[value]})
    jsonDict["entries"] = entries
    #debug
#    print entries
    jsonData = json.dumps(jsonDict, ensure_ascii=False, indent=2)
    # using io.open since it allows encoding
    with io.open(entities_path+"/"+name+".json", "w", encoding="utf8") as f:
        f.write(unicode(jsonData))  

#%% generating intents files

s_intents = wb.sheet_by_name(u"Intenções")
intent_list = [cell.value for cell in s_intents.col(0)[1:]]

def process_q_tagged(q_tagged):
    tags = re.findall("@\w+:?\w*", q_tagged)
    entities = []
    parameters = []
    for tag in tags:
        entity = tag[1:] # eliminating @
        if entity not in entity_list:
            sys.exit("Error: entity %s not found in entity list (row %d). Stopping..."%(entity, row_num))
        entities.append(entity)
        parameter = re.findall("^\w+",entity)[0] # getting only what is before the collon
        parameters.append(parameter)
    # using only the high level entities for the templates:
    template = re.sub(":\w+","",q_tagged) 
    template = re.sub("@(\w+)","@\g<1>:\g<1>",template)
    return (template, entities, parameters)

# intent_template_dict: intent -> list of templates
intent_template_dict = defaultdict(list)
# intent_parameter_dict: intent -> list of parameters
intent_parameter_dict = defaultdict(list)
# webhook_dict: intent and entities tuple -> qa list
webhook_dict = defaultdict(list)
s_qa = wb.sheet_by_name("Perguntas e Respostas")
for row_idx in range(1,s_qa.nrows):
    row_num = row_idx + 1
    row = s_qa.row(row_idx)
    q = row[0].value
    a = row[1].value #TODO: eliminate numbers from answer
    qa = " ".join([q,a])
    qa = qa.encode("utf-8") # converting for compatibility with heroku webservice
    intent = row[2].value
    if intent == "":
        break
    if intent not in intent_list:
        sys.exit("Error: intent %s not found in intents list (row %d). Stopping..."%(intent, row_num))
    for cell in row[3:]:
        q_tagged = cell.value
        if q_tagged == "":
            break
        template, entities, parameters = process_q_tagged(q_tagged)
        intent_template_dict[intent].append(template)
        webhook_key = [intent]
        webhook_key.extend(sorted(entities))
        t = tuple(webhook_key)        
        if qa not in webhook_dict[t]:
            webhook_dict[t].append(qa)
        intent_parameter_dict[intent].extend(parameters)
# eliminating duplicates in parameter values
# TODO: differentiate required parameters
for intent in intent_parameter_dict:
    intent_parameter_dict[intent] = list(set(intent_parameter_dict[intent]))

print "%d Q&A rows processed successfully!"%row_idx

for name in intent_template_dict:
    jsonDict = {"userSays":[], "name":name, "auto":True, "contexts":[], "responses":[], "priority":500000, "webhookUsed":True, "webhookForSlotFilling":False, "fallbackIntent":False, "events":[]}
    userSays = []
    for template in intent_template_dict[name]:
        userSays.append({"data":[{"text":template}],"isTemplate":True,"count":0})
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

#%% save pickle for webhook
with open("webhook_pickle.p","wb") as p:
    pickle.dump(webhook_dict,p)






