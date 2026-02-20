"""
Microsoft Teams Bot Server

FastAPI server that handles Teams bot webhooks and forwards to the bot logic.
"""

import sys
import logging
from typing import Dict

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from botbuilder.core import BotFrameworkAdapter, TurnContext
from botbuilder.schema import Activity

# Add src to path
sys.path.insert(0, "/Users/dileshchouhan/zysecai/LeadTheAI/devops/incidentiq")

from src.bots.teams_bot import TeamsBot, create_teams_bot
from src.core.config import get_settings

logger = logging.getLogger(__name__)

# ============================================
# FastAPI App
# ============================================

app = FastAPI(title="IncidentIQ Teams Bot")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# Bot Setup
# ============================================

settings = get_settings()
BOT_ID = getattr(settings, "teams_bot_id", None)
BOT_PASSWORD = getattr(settings, "teams_bot_password", None)

# Create bot instance
bot = create_teams_bot()

# Create Bot Framework Adapter
# This handles authentication and request validation
adapter = BotFrameworkAdapter(BOT_ID or "default-id")

# ============================================
# Routes
# ============================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "incidentiq-teams-bot",
        "version": "2.0.0"
    }


@app.post("/api/messages")
async def messages_endpoint(request: Request):
    """
    Receive messages from Microsoft Teams.

    This is the webhook endpoint configured in Azure Bot.
    """
    # Check if we have bot credentials
    if not BOT_ID or not BOT_PASSWORD:
        logger.warning("Bot credentials not configured. Please set TEAMS_BOT_ID and TEAMS_BOT_PASSWORD in .env")
        return Response(
            content="Bot not configured. Please set environment variables.",
            status_code=500
        )

    # Read request body
    body = await request.json()

    # Create Activity from request
    activity = Activity().deserialize(body)

    # Authenticate request (Microsoft Bot Framework protocol)
    auth_header = request.headers.get("Authorization", "")

    try:
        # Process activity with bot
        response = await adapter.process_activity(activity, auth_header, bot.on_turn)

        if response:
            # Return bot response
            return Response(
                content=response.body,
                status_code=response.status,
                media_type=response.content_type
            )

        # No response (activity was handled asynchronously)
        return Response(status_code=201)

    except Exception as e:
        logger.error(f"Error processing activity: {e}")
        return Response(
            content=f"Error: {str(e)}",
            status_code=500
        )


@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "service": "IncidentIQ Teams Bot",
        "version": "2.0.0",
        "status": "running",
        "endpoints": {
            "health": "/health",
            "messages": "/api/messages",
            "docs": "/docs"
        }
    }


# ============================================
# Main
# ============================================

def main():
    """Run the server"""
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "src.bots.teams_server:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )


if __name__ == "__main__":
    main()
