# -*- coding: utf-8 -*-
#import json
from watson_developer_cloud import ConversationV1

conversation = ConversationV1(
    username='8fcdf6b6-be15-400b-bb6d-1d5e2c44c2d3',
    password='lieR8OpYbMKV',
    version='2017-02-03')

# replace with your own workspace_id
workspace_id = '87d42987-eec9-4427-a63a-fc1e071b2f2b'

while True:
    user_input = raw_input('Digite sua pergunta ("x" para sair): ')
    if user_input.lower() == 'x':
        break
    if len(user_input) == 0:
        continue
    response = conversation.message(workspace_id=workspace_id, message_input={
    'text': user_input.decode('utf-8')})
#    print(json.dumps(response, indent=2))
    print(response["output"]["text"][0])
    
# When you send multiple requests for the same conversation, include the
# context object from the previous response.
# response = conversation.message(workspace_id=workspace_id, message_input={
# 'text': 'turn the wipers on'},
#                                context=response['context'])
# print(json.dumps(response, indent=2))