from dotenv import load_dotenv
from groq import AsyncGroq
from groq import Groq


load_dotenv()
client = Groq()



def llm_query_handler(history) -> str:
    
    # client = AsyncGroq()
 
        # Ensure model & input are on the same device
        
    print('The history received at the model is', history)
        
    chat_completion = client.chat.completions.create(
        #
        # Required parameters
        #
        messages=history,

        # The language model which will generate the completion.
        # model="llama-3.3-70b-versatile",
        model = "qwen-2.5-32b",
        #
        # Optional parameters
        #

        # Controls randomness: lowering results in less random completions.
        # As the temperature approaches zero, the model will become deterministic
        # and repetitive.
        temperature=0.5,

        # The maximum number of tokens to generate. Requests can use up to
        # 2048 tokens shared between prompt and completion.
        max_completion_tokens=512,

        # Controls diversity via nucleus sampling: 0.5 means half of all
        # likelihood-weighted options are considered.
        top_p=1,

        # A stop sequence is a predefined or user-specified text string that
        # signals an AI to stop generating content, ensuring its responses
        # remain focused and concise. Examples include punctuation marks and
        # markers like "[end]".
        stop=None,

        # If set, partial message deltas will be sent.
        stream=False,
    )

        # Print the incremental deltas returned by the LLM.
        #for chunk in stream:
         #   output = chunk.choices[0].delta.content
            
    output = chat_completion.choices[0].message.content
    print('#'*100)
    print('The output to the chat is', output) 
                
    print('#'*100)
        
    return output
    # async for chunk in chat_completion:
    #     return chunk.choices[0].delta.content

