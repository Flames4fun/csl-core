FROM python:3.12-slim

LABEL maintainer="akarlaraytu"
LABEL description="CSL-Core: Deterministic AI safety policy engine with Z3 formal verification"
LABEL org.opencontainers.image.source="https://github.com/Chimera-Protocol/csl-core"

# Install csl-core with MCP support
RUN pip install --no-cache-dir "csl-core[mcp]"

# Verify installation
RUN python -c "from chimera_core.mcp.server import mcp; print('CSL-Core MCP server ready')"

# MCP servers communicate over STDIO
ENTRYPOINT ["csl-core-mcp"]