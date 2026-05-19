# MCP Behavioral Prompts Server

A specialized MCP server providing behavioral prompts for AI assistant modification.

## Available Prompts

All prompts accept arguments via the standard MCP `prompts/get` call.

| Name                            | Arguments                                                              | Notes                                |
|---------------------------------|------------------------------------------------------------------------|--------------------------------------|
| `project_analyst_prompt`        | `version: int = 1`                                                     | Iterative project definition (IT).   |
| `socratic_consultant_prompt`    | `topic: str = ""`                                                      | Critical Socratic questioning (IT).  |
| `critical_code_reviewer_prompt` | `context: prototype\|development\|production`, `language: str = ""`    | Critical code review (EN).           |
| `software_architect_prompt`     | `context: prototype\|development\|production`                          | Structured planning and design (EN). |

Prompt bodies live as Markdown templates under
`src/mcp_prompts_server/prompts/templates/` — edit them without touching code.

## Installation

```bash
poetry install
```

## Usage

```bash
poetry run python -m mcp_prompts_server.server
```

## Testing

```bash
poetry run pytest
```

## Features

- Production-ready with health check endpoint
- Graceful shutdown handling
- Structured logging with file rotation
- Environment-based configuration
- File-based prompt templates with `$var` substitution (curly-brace
  placeholders such as `{file_name}` are preserved for the model)
