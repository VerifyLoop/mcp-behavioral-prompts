# MCP Behavioral Prompts Server

A specialized MCP server providing behavioral prompts for AI assistant modification.

## Available Prompts

1. **Complex Project Analyst** - Iterative project definition process
2. **Socratic Strategic Consultant** - Critical questioning for deep reasoning
3. **Critical Code Reviewer** - Production-ready code analysis
4. **AI Software Architect** - Structured software planning and design

## Installation

```bash
poetry install
```

## Usage

```bash
poetry run python -m mcp_prompts_server.server
```

## Features

- Production-ready with health check endpoint
- Graceful shutdown handling
- Structured logging with file rotation
- Environment-based configuration