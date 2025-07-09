FROM python:3.11-slim

# Install system packages and pipx
RUN apt-get update && apt-get install -y \
    curl build-essential python3-pip pipx \
 && pipx ensurepath

# Install uv using pipx
RUN pipx install uv

# Set PATH to include pipx-installed binaries
ENV PATH="/root/.local/bin:$PATH"

# Copy project files
COPY . .

# Install dependencies using requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose Gradio and FastAPI ports
EXPOSE 7860
EXPOSE 8080

# Run both components with uv
CMD ["sh", "-c", "uv run server.py & uv run app.py && wait"]