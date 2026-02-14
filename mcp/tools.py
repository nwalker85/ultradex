"""MCP tool definitions for Hrafngrima"""

from typing import Any, Dict, List

# Tool definitions that describe what MCP tools are available
TOOLS: List[Dict[str, Any]] = [
    {
        "name": "hrafngrima/sync_contacts",
        "description": "Sync all contacts from Dex to the local database. This fetches the latest contact data from your Dex account and updates the local cache.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "hrafngrima/analyze_contacts",
        "description": "Run AI analysis on contacts to identify high-value relationships and neglected contacts. Claude analyzes each contact's value (0-100 score) and generates personalized outreach strategies.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of contacts to analyze. If not specified, analyzes all that need analysis.",
                    "minimum": 1
                }
            },
            "required": []
        }
    },
    {
        "name": "hrafngrima/get_contacts",
        "description": "Get all cached contacts from the database. Returns all contacts with their current status and AI analysis results.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "hrafngrima/get_contact",
        "description": "Get a specific contact by ID. Returns detailed information including AI analysis, last contact date, and AI-generated outreach strategy.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "contact_id": {
                    "type": "string",
                    "description": "The Dex contact ID"
                }
            },
            "required": ["contact_id"]
        }
    },
    {
        "name": "hrafngrima/get_neglected_contacts",
        "description": "Get all neglected high-value contacts. Returns contacts that have a value score ≥60 and haven't been contacted in ≥30 days.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "hrafngrima/write_note",
        "description": "Write a note to a contact in Dex. This adds a note to the contact's timeline in Dex, keeping it as the single source of truth.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "contact_id": {
                    "type": "string",
                    "description": "The Dex contact ID"
                },
                "note": {
                    "type": "string",
                    "description": "The note content to write to the contact"
                }
            },
            "required": ["contact_id", "note"]
        }
    },
    {
        "name": "hrafngrima/get_analysis_stats",
        "description": "Get aggregate statistics about contact analysis. Returns total runs, contacts analyzed, neglected contacts found, and cost tracking.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "hrafngrima/get_analysis_history",
        "description": "Get recent analysis runs. Returns a history of when analysis was performed, how many contacts were analyzed, and the results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of runs to return. Defaults to 10.",
                    "minimum": 1,
                    "default": 10
                }
            },
            "required": []
        }
    }
]
