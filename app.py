import gradio as gr
import os
import json
from dotenv import load_dotenv
from fastmcp import Client
from fastmcp.tools import Tool
from fastmcp.client.transports import SSETransport
from openai import AzureOpenAI

# --- Configuration ---
load_dotenv()

openai_client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version="2025-01-01-preview",
)

GRADIO_MCP_SERVER_TARGET = "http://127.0.0.1:8080/sse"
MCP_CLIENT_TRANSPORT = SSETransport(GRADIO_MCP_SERVER_TARGET)


# --- OpenAI LLM Helper ---
def ask_openai(system_prompt: str, user_prompt: str, model: str = "gpt-4.1-mini"):
    """Asynchronously asks OpenAI for a completion."""
    try:
        completion = openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": [{"type": "text", "text": system_prompt}]},
                {"role": "user", "content": [{"type": "text", "text": user_prompt}]},
            ],
            temperature=0.2, # Lower temperature for more deterministic tool use
        )
        print(completion)
        return completion.choices[0].message.content
    except Exception as e:
        print(f"OpenAI API error: {e}")
        return f"Error: Could not contact OpenAI - {e}"

# --- FastMCP Client Helpers ---
async def list_mcp_tools_with_schema(mcp_client: Client) -> list[dict]:
    """Lists tools from MCP server with their parameter schemas."""
    tools_data = []
    try:
        # client.list_tools() returns a list of mcp.types.Tool objects
        # The Tool type hint should ideally be from mcp.types but fastmcp.tools.Tool might be an alias or wrapper.
        # Let's assume it's compatible with mcp.types.Tool for now.
        raw_tools: list[Tool] = await mcp_client.list_tools() 
        
        print(f"DEBUG: Number of tools found: {len(raw_tools)}")
        if not raw_tools:
            print("DEBUG: No tools returned by client.list_tools()")
            return []

        for i, tool_obj in enumerate(raw_tools): # Renamed to tool_obj to avoid confusion
            print(f"\n--- Processing Tool {i+1} ---")
            print(f"Tool Name: {tool_obj.name}")
            print(f"Tool Description: {tool_obj.description}")
            
            parameter_schema_for_llm = {} # Default to empty schema

            # The mcp.types.Tool object should have an 'inputSchema' attribute (camelCase)
            # which directly contains the JSON schema for its parameters.
            if hasattr(tool_obj, 'inputSchema') and tool_obj.inputSchema is not None:
                if isinstance(tool_obj.inputSchema, dict):
                    parameter_schema_for_llm = tool_obj.inputSchema
                    print(f"DEBUG: Using tool_obj.inputSchema: {json.dumps(parameter_schema_for_llm, indent=2)}")
                else:
                    print(f"DEBUG: tool_obj.inputSchema is not a dict. Type: {type(tool_obj.inputSchema)}, Value: {tool_obj.inputSchema}")
            elif hasattr(tool_obj, 'parameters'): # As a fallback, check if 'parameters' might be the schema
                # This was the original attempt, less likely for mcp.types.Tool but good to check
                from pydantic import BaseModel
                if isinstance(tool_obj.parameters, type) and issubclass(tool_obj.parameters, BaseModel):
                    print("DEBUG: 'parameters' is a Pydantic class, getting schema.")
                    parameter_schema_for_llm = tool_obj.parameters.model_json_schema()
                elif isinstance(tool_obj.parameters, dict):
                    print("DEBUG: 'parameters' is a dict, using directly.")
                    parameter_schema_for_llm = tool_obj.parameters
                else:
                     print(f"DEBUG: 'inputSchema' not found or is None. 'parameters' attribute is not a Pydantic class or dict. Type: {type(tool_obj.parameters if hasattr(tool_obj, 'parameters') else None)}")
            else:
                print(f"DEBUG: Neither 'inputSchema' nor 'parameters' found or suitable for schema for tool '{tool_obj.name}'.")


            tools_data.append({
                "name": tool_obj.name,
                "description": tool_obj.description,
                "parameters_schema": parameter_schema_for_llm 
            })
        
        print("\n--- End of tool processing ---\n")
        return tools_data
    except Exception as e:
        print(f"Error listing MCP tools: {e}")
        import traceback
        traceback.print_exc()
        return []

# --- Core Logic ---
async def process_user_query(user_query: str, mcp_client: Client):
    """
    1. Gets tools from MCP.
    2. Asks LLM to select a tool and arguments.
    3. Calls the MCP tool.
    4. (Optionally) Asks LLM to summarize the tool result.
    """
    # 1. Get tools from MCP server
    mcp_tools_list = await list_mcp_tools_with_schema(mcp_client)
    if not mcp_tools_list:
        return "Error: Could not retrieve tools from the MCP server."

    tools_json_for_llm = json.dumps(mcp_tools_list, indent=2)

    # 2. Ask LLM to select a tool and arguments
    system_prompt_tool_selection = """
You are an AI assistant that helps select the correct tool and its arguments to answer a user's query.
You will be provided with a list of available tools in JSON format, including their names, descriptions, and JSON schemas for their parameters.
Based on the user's query, you must decide which tool to use and what arguments to pass to it.

Respond ONLY with a JSON object of the following format:
{
  "tool_name": "name_of_the_tool_to_use",
  "arguments": { "param1": "value1", "param2": "value2" ... }
}
If no tool is suitable for the user's query, respond with:
{
  "tool_name": null,
  "arguments": {}
}
Ensure that argument values match the types specified in the tool's parameter schema.
For example, if a parameter is type 'integer', provide an integer, not a string.
If a parameter is an 'object' with properties, provide a nested JSON object for that argument.
If a parameter is an 'array', provide a JSON array.
Do not add any explanations before or after the JSON object.
    """
    user_prompt_tool_selection = f"""
User query: "{user_query}"

Available tools:
{tools_json_for_llm}

Based on the user query and available tools, which tool should be used and with what arguments?
Remember to respond only with the JSON object.
    """

    llm_tool_choice_str = ask_openai(system_prompt_tool_selection, user_prompt_tool_selection)

    try:
        llm_tool_choice = json.loads(llm_tool_choice_str)
        tool_name = llm_tool_choice.get("tool_name")
        tool_arguments = llm_tool_choice.get("arguments", {})
    except json.JSONDecodeError:
        return f"Error: LLM did not provide a valid JSON response for tool selection. LLM response:\n{llm_tool_choice_str}"
    except Exception as e:
        return f"Error parsing LLM tool choice: {e}. LLM response:\n{llm_tool_choice_str}"


    if not tool_name:
        # LLM decided no tool is suitable. We could try a general knowledge answer.
        # For now, just inform the user.
        general_answer_prompt = f"The user asked: '{user_query}'. No specific tool was chosen. Please provide a helpful general response."
        general_response = ask_openai("You are a helpful AI assistant.", general_answer_prompt)
        return f"(No specific tool was used by the LLM for your query)\nLLM: {general_response}"

    # 3. Call the MCP tool
    try:
        print(f"Attempting to call MCP tool: {tool_name} with arguments: {tool_arguments}")
        # Ensure tool_arguments is a dict, which call_tool expects
        if not isinstance(tool_arguments, dict):
            return f"Error: LLM provided arguments in an incorrect format for tool '{tool_name}'. Expected a dictionary, got {type(tool_arguments)}."

        tool_result_list = await mcp_client.call_tool(tool_name, tool_arguments)
        print(f"MCP tool '{tool_name}' raw result: {tool_result_list}")

        # The result from call_tool is a list of content objects.
        # We'll typically be interested in the .text or .data attribute.
        if tool_result_list and hasattr(tool_result_list[0], 'text'):
            tool_output_for_llm = tool_result_list[0].text
        elif tool_result_list and hasattr(tool_result_list[0], 'data'): # For images/binary
             tool_output_for_llm = f"[Binary data received, type: {type(tool_result_list[0].data)}]"
        elif tool_result_list: # If it's a list of dicts, etc.
            tool_output_for_llm = json.dumps([res.__dict__ if hasattr(res, '__dict__') else str(res) for res in tool_result_list])
        else:
            tool_output_for_llm = "Tool executed successfully but returned no content."

    except Exception as e:
        print(f"Error calling MCP tool '{tool_name}': {e}")
        return f"Error executing tool '{tool_name}' on MCP server: {e}"

    # 4. (Optional) Ask LLM to summarize/explain the tool result
    # This makes the output more conversational.
    system_prompt_summarize = "You are an AI assistant. A tool was executed to help answer a user's query. Explain the tool's output to the user in a friendly and concise way."
    user_prompt_summarize = f"""
The user originally asked: "{user_query}"
The tool "{tool_name}" was called with arguments {json.dumps(tool_arguments)}.
The tool returned the following output:
---
{tool_output_for_llm}
---
Please provide a natural language response to the user based on this.
    """
    final_response = ask_openai(system_prompt_summarize, user_prompt_summarize)
    return final_response


# --- Gradio Interface ---
async def chat_interface_fn(message: str, history: list[list[str]]):
    """Gradio chat function. It's async to allow await for MCP and OpenAI calls."""
    # The FastMCP client needs to be managed within an async context
    # For a long-running Gradio app, you might consider initializing the client once
    # and passing it around, or using a global/class-based approach if Gradio supports it well.
    # For this example, we open/close it per interaction, which is less efficient but simpler.
    try:
        if MCP_CLIENT_TRANSPORT:
            mcp_client_instance = Client(transport=MCP_CLIENT_TRANSPORT)
        else:
            mcp_client_instance = Client(GRADIO_MCP_SERVER_TARGET)

        async with mcp_client_instance as mcp_client:
            bot_response = await process_user_query(message, mcp_client)
    except ConnectionRefusedError:
        bot_response = "Error: Could not connect to the MCP server. Is it running and accessible?"
    except Exception as e:
        bot_response = f"An unexpected error occurred: {e}"
        print(f"Unexpected error in Gradio handler: {e}")

# history.append([message, bot_response]) # Old incorrect way for type='messages'
    # Correct way for type='messages':
    history.append({"role": "user", "content": message})
    history.append({"role": "assistant", "content": bot_response})
    return "", history # Clear textbox, update history


with gr.Blocks() as demo:
    gr.Markdown("# Gradio MCP Client with LLM Tool Selection")
    gr.Markdown(
        f"This interface connects to an MCP server (`{GRADIO_MCP_SERVER_TARGET}`). "
        "It uses an OpenAI LLM to decide which tool on the MCP server to call based on your query!!."
    )

    chatbot = gr.Chatbot(label="Conversation", type='messages')
    msg_textbox = gr.Textbox(label="Your Message", placeholder="Ask something...", lines=2)
    
    with gr.Row():
        submit_btn = gr.Button("Send", variant="primary")
        clear_btn = gr.ClearButton([msg_textbox, chatbot], value="Clear Chat")

    # Define actions
    # For async Gradio functions, ensure your Gradio version supports it (recent versions do)
    msg_textbox.submit(chat_interface_fn, [msg_textbox, chatbot], [msg_textbox, chatbot])
    submit_btn.click(chat_interface_fn, [msg_textbox, chatbot], [msg_textbox, chatbot])


if __name__ == "__main__":
    print(f"Starting Gradio interface, connecting to MCP server: {GRADIO_MCP_SERVER_TARGET}")
    print("Ensure your MCP server (server.py) is running if using HTTP/SSE.")
    print("If using STDIO, this Gradio client will attempt to launch it.")
    demo.launch(server_name="0.0.0.0", server_port=7860)
