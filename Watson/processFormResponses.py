# -*- coding: utf-8 -*-
#import json
from watson_developer_cloud import ConversationV1
from openpyxl import load_workbook
import re

#%% reading existing examples
reAllLettersAndSpace = u"[A-Za-záàãâçéêíóôúü\s]"
filename = u"../Dados para Chatbot do Livro dos Espíritos.xlsx"

def get_q_number(q_text):
    return re.findall("^(.+?). ", q_text)[0]

def process_example(q_marked):
    text = q_marked
#    print(text)
    terms = re.findall("\["+reAllLettersAndSpace+"+\s?@?\w*\]",text)
    for term in terms:
        term_text = term[1:-1]
        term_text = re.split("\s+@", term_text)[0]
        text = text.replace(term,term_text,1)
    return text

wb = load_workbook(filename)
s_qa = wb.get_sheet_by_name("Perguntas e Respostas")
example_dict = dict()
qa_row_dict = dict()
for row_num in range(2,s_qa.max_row+1):
    row = s_qa[row_num]
    q = row[0].value
    if q is None:
        break
    q_num = get_q_number(q)
    qa_row_dict[q_num] = row_num
    # pending: remove tagging
    example_dict[q_num] = [process_example(cell.value) for cell in row[3:] if cell.value is not None]

#%% reading and processing new data from form resposes
s_form = wb.get_sheet_by_name("Respostas Form")
new_example_dict = dict()

# initializing watson parameters
conversation = ConversationV1(
    username='8fcdf6b6-be15-400b-bb6d-1d5e2c44c2d3',
    password='lieR8OpYbMKV',
    version='2017-02-03')

workspace_id = '87d42987-eec9-4427-a63a-fc1e071b2f2b'

for row in s_form.rows:
    processed = (row[4].value is not None)
    if processed:
        continue
    q_num = "%d"%row[1].value
    text = row[2].value
    if text in example_dict[q_num]:
        continue
#    response = conversation.message(workspace_id=workspace_id, message_input={
#    'text': text})
##    print(json.dumps(response, indent=2))
##    print(response["output"]["text"][0])
#    r_num = get_q_number(response)
#    if r_num == q_num: # watson has correctly identified the question
#        continue
    # inserting new example to spreadsheet
    qa_row_num = qa_row_dict[q_num]
    qa_row = s_qa[qa_row_num]
    example_idx = len(example_dict[q_num]) + 3
    qa_row[example_idx].value = text
    example_dict[q_num].append(text)
    row[4].value = "Sim"
    wb.save(filename)

        
        
        
        
        
        
        
        
        
        
        
        
        
        
        