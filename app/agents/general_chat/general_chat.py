# from app.utils.orchestrator import Orchestrator
import redis
from app.utils.response_processing import clean_response
from app.utils.prompt_selector import prompt_selector
from app.models.chat_models import UserQuery, ChatResponse
import json


# orchestrator = Orchestrator()
from app.utils.llm_integration import llm_query_handler

redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)


class General_Chat:
    
    def __init__(self):
        # self.orchestrator = Orchestrator()
        self.redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)
    def general_chat(self, query : UserQuery)  -> str: 

                session_id = query.session_id
                history_key = f"conversation:{session_id}"
                conversation_history = redis_client.get(history_key)
                system_prompt = prompt_selector("general")



                # Parse history or initialize empty list
                if conversation_history:
                    conversation_history = json.loads(conversation_history)
                else:
                    conversation_history = [{'role':'system', 'content': f'{system_prompt}'}]
                    
                conversation_history.append({"role": "user", "content": query.text})
                model_input = "\n".join(
                    [f"{msg['role']}: {msg['content']}" for msg in conversation_history]
                ) 
                

                
                print('model input is : \n', model_input)
                print(type(model_input))
                # Append the current user query to the history
                # Pass conversation history to the orchestrator for better context
                                # response = orchestrator.handle_query(model_input, system_prompt)
                response = llm_query_handler(conversation_history)
                
                
                # Append the model's response to the history
                conversation_history.append({"role": "assistant", "content": response})

                # Save updated history back to Redis
                redis_client.set(history_key, json.dumps(conversation_history))
                

                # Return the cleaned response

                # cleaned_response = clean_response(response, query.text,)

                
                return response



    #
    # def general_chat(self, query : UserQuery)  -> str: 

    #         session_id = query.session_id
    #         history_key = f"conversation:{session_id}"
    #         conversation_history = redis_client.get(history_key)


    #         # Parse history or initialize empty list
    #         if conversation_history:
    #             conversation_history = json.loads(conversation_history)
    #         else:
    #             conversation_history = []
                

    #         # Append the current user query to the history
    #         conversation_history.append({"role": "user", "content": query.text})
    #         # Pass conversation history to the orchestrator for better context
    #         model_input = "\n".join(
    #             [f"{msg['role']}: {msg['content']}" for msg in conversation_history]
    #         )
    #         system_prompt = prompt_selector("general")
    #         print("system_prompt: ", system_prompt)

    #         # response = orchestrator.handle_query(model_input, system_prompt)
    #         response = llm_query_handler( model_input, system_prompt)

    #         # Append the model's response to the history
    #         conversation_history.append({"role": "assistant", "content": response})

    #         # Save updated history back to Redis
    #         redis_client.set(history_key, json.dumps(conversation_history))
            

    #         # Return the cleaned response

    #         cleaned_response = clean_response(response, query.text,)

            
    #         return cleaned_response



    # def general_chat_2(self, query : UserQuery)  -> str: 

    #         session_id = query.session_id
    #         history_key = f"conversation:{session_id}"
    #         conversation_history = redis_client.get(history_key)
    #         system_prompt = prompt_selector('general_2')

    #         # Parse history or initialize empty list
    #         if conversation_history:
    #             conversation_history = json.loads(conversation_history)
    #         else:
    #             conversation_history = [ {"role": "System", "content": system_prompt}]
                

    #         # Append the current user query to the history
    #         conversation_history.append({"role": "user", "content": query.text})
    #         # Pass conversation history to the orchestrator for better context
    #         model_input = "\n".join(
    #             [f"{msg['role']}: {msg['content']}" for msg in conversation_history]
    #         )
    #         print('The Query to the model is', model_input)

    #         # response = orchestrator.general_handle_query(model_input)
    #         response = llm_query_handler()

    #         # Append the model's response to the history
    #         conversation_history.append({"role": "assistant", "content": response})

    #         # Save updated history back to Redis
    #         redis_client.set(history_key, json.dumps(conversation_history))
            
    #         print("The Received Response is ------- \n", response)
    #         # Return the cleaned response

    #         cleaned_response = clean_response(response, query.text,)

            
    #         return response
