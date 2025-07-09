# Demo Platform:

## Setup

1.  **Clone the repository (if applicable):**
    ```bash
    git clone <repository-url>
    cd demo-platform
    ```

2.  **Install dependencies via "uv" packet manager (recommended):**
    
    This project's package management is handled via uv package manager. Please install it first if you don't have it. [Installation guide](https://docs.astral.sh/uv/getting-started/installation/).
    ```bash
    uv install
    ```
    To add new package please add it via:
    ```bash
    uv add <package_name>
    ```

3.  **Set up environment variables:**
    
    Create a `.env` file in the root of the project (`../demo-platform/.env`) and add your API keys and endpoints:
    ```env
    TAVILY_API_KEY="your_tavily_api_key"
    AZURE_OPENAI_API_KEY="your_azure_openai_api_key"
    AZURE_OPENAI_ENDPOINT="your_azure_openai_endpoint"
    # Optional: Override default MCP server target for the Gradio app
    # GRADIO_MCP_SERVER_TARGET="http://127.0.0.1:8080/sse"
    ```
    Replace placeholder values with your actual credentials.

## Running the Application

You need to run two components: the MCP server and the Gradio application.

1.  **Start the MCP Server:**
    Open a terminal, navigate to the project directory, and run:
    ```bash
    uv run server.py
    ```
    The server will start, typically on `http://127.0.0.1:8080`.

2.  **Start the Gradio Application:**
    Open another terminal, navigate to the project directory, and run:
    ```bash
    uv run app.py
    ```
    The Gradio interface will launch, and you can open it in your web browser (usually at `http://127.0.0.1:7860` or a similar address provided in the terminal output).

Now you can interact with the chat interface. Your queries will be processed by the LLM, which will decide whether to use the Tavily search tool via the MCP server.

## Project Structure

*   `app.py`: Gradio UI and client-side logic for interacting with the LLM and MCP server.
*   `server.py`: FastMCP server hosting the tools (e.g., Tavily search).
*   `tools/`: Directory for tool implementations.
    *   `tavily_search_tool.py`: Implements the Tavily web search tool.
*   `pyproject.toml`: Project metadata and dependencies for Poetry.
*   `.env`: Stores API keys and other secrets.
