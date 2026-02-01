# Prometheus

A Python project template with a clean, professional structure.

## MCP Server Setup (Claude Code)

The project includes MCP servers that can be used with Claude Code on the terminal.

### Prerequisites

```bash
pip install -e .
```

#### Set up AWS credentials

```
export AWS_ACCESS_KEY_ID="your-access-key-id"
export AWS_SECRET_ACCESS_KEY="your-secret-access-key"
export AWS_DEFAULT_REGION="us-west-2"  # Optional: set default region
```

### Configuration

A `.mcp.json` file in the project root registers the servers with Claude Code:

```json
{
  "mcpServers": {
    "prometheus-analysis": {
      "command": "prometheus",
      "args": ["analysis"]
    }
  }
}
```

Start a Claude Code session from the project directory and the servers will be loaded automatically.

### Available Servers

| Server | Command | Description |
|--------|---------|-------------|
| `prometheus-analysis` | `prometheus analysis` | Financial text analysis tools for investment research |
| `prometheus-research` | `prometheus research` | Research tools for financial queries |

### Verify

```bash
# Confirm the server starts
prometheus analysis

# Check server is registered in Claude Code
claude mcp list
```
