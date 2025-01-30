from 
import redis
from app.utils import response_processing, prompt_selector


orchestrator = Orchestrator()


redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)


def general_chat(query: str): -> str
        session_id = query.session_id
        history_key = f"conversation:{session_id}"
        conversation_history = redis_client.get(history_key)

        # Parse history or initialize empty list
        if conversation_history:
            conversation_history = json.loads(conversation_history)
        else:
            conversation_history = []

        # Append the current user query to the history
        conversation_history.append({"role": "user", "content": query.text})

        # Pass conversation history to the orchestrator for better context
        model_input = "\n".join(
            [f"{msg['role']}: {msg['content']}" for msg in conversation_history]
        )

        prompt = prompt_selector('general')
        response = orchestrator.handle_query(model_input)

        # Append the model's response to the history
        conversation_history.append({"role": "assistant", "content": response})

        # Save updated history back to Redis
        redis_client.set(history_key, json.dumps(conversation_history))
        

        # Return the cleaned response
        cleaned_response = response_processing.clean_response(response, query.text,)
        return cleaned_response