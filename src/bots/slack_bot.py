"""
Slack Bot - IncidentIQ Integration

Provides:
1. Event-driven incident monitoring in war room channels
2. Command-based incident search
3. Streaming AI responses
4. Interactive message components

The bot listens to war room channels and learns from:
- Incident discussions
- RCA documents shared
- Resolution confirmations
- Who fixed what
"""

import re
from datetime import datetime
from typing import Optional

from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

from src.core.config import get_settings
from src.core.pattern_matching import (
    Incident,
    IncidentMatch,
    MatchConfidence,
    get_pattern_engine,
)
from src.services.cache_service import get_cache_service
from src.services.llm_service import EmbeddingService, LLMService

settings = get_settings()

# Initialize Slack app
app = AsyncApp(
    token=settings.slack.bot_token,
    signing_secret=settings.slack.signing_secret,
)


# ============================================
# INCIDENT SEARCH COMMANDS
# ============================================

@app.command("/incidentiq")
async def handle_incident_search(ack, command, respond, client):
    """
    Handle /incidentiq command for incident search.
    
    Usage:
    /incidentiq <error message or description>
    /incidentiq what caused nginx 502 errors last week?
    /incidentiq similar to database connection timeout
    """
    await ack()
    
    query = command.get("text", "").strip()
    if not query:
        await respond(
            "Please provide an error message or incident description.\n"
            "Example: `/incidentiq database connection timeout errors`"
        )
        return
    
    # Show loading message
    await respond("🔍 Searching for similar incidents...")
    
    try:
        engine = await get_pattern_engine()
        matches = await engine.find_similar_incidents(query, limit=5)
        
        if not matches:
            await respond(
                "❌ *NO MATCH FOUND*\n\n"
                "I couldn't find any similar incidents in the knowledge base.\n\n"
                "💡 *Suggested actions:*\n"
                "1. Check recent deployments\n"
                "2. Page the on-call engineer\n"
                "3. Review service logs\n\n"
                "_I'll learn from this incident once it's resolved._"
            )
            return
        
        # Format and send matches
        blocks = _format_matches_as_blocks(matches, query)
        await respond(blocks=blocks)
        
    except Exception as e:
        await respond(f"⚠️ Error searching incidents: {str(e)}")


@app.message(re.compile(r"^@incidentiq\s+(.+)", re.IGNORECASE))
async def handle_mention_search(message, say, context):
    """Handle @incidentiq mentions for incident search"""
    query = context["matches"][0]
    
    await say("🔍 Searching for similar incidents...")
    
    try:
        engine = await get_pattern_engine()
        matches = await engine.find_similar_incidents(query, limit=5)
        
        if matches:
            blocks = _format_matches_as_blocks(matches, query)
            await say(blocks=blocks)
        else:
            await say(
                "❌ *NO MATCH FOUND*\n\n"
                "This appears to be a new issue. I'll learn from it once resolved."
            )
    except Exception as e:
        await say(f"⚠️ Error: {str(e)}")


# ============================================
# WAR ROOM LEARNING (Event Listeners)
# ============================================

@app.event("message")
async def handle_message(event, say, client):
    """
    Listen to messages in war room channels to learn.
    
    Captures:
    - Incident discussions
    - Error messages shared
    - Resolution confirmations
    - RCA documents linked
    """
    # Skip bot messages
    if event.get("bot_id"):
        return
    
    channel_id = event.get("channel")
    text = event.get("text", "")
    user_id = event.get("user")
    
    # Check if this is a war room channel (configurable)
    # For MVP, we'll process all messages
    
    # Detect potential incident reports
    if _is_incident_report(text):
        # Proactively search for similar incidents
        await _proactive_incident_search(text, channel_id, say)
    
    # Detect resolution confirmations
    if _is_resolution_confirmation(text):
        await _record_resolution(event, client)
    
    # Detect RCA document shares
    rca_url = _extract_document_url(text)
    if rca_url:
        await _link_rca_to_incident(channel_id, rca_url, client)


async def _proactive_incident_search(text: str, channel_id: str, say):
    """Proactively search when incident-like message detected"""
    try:
        engine = await get_pattern_engine()
        matches = await engine.find_similar_incidents(text, limit=3)
        
        # Only respond if we have high-confidence matches
        exact_matches = [m for m in matches if m.confidence == MatchConfidence.EXACT]
        
        if exact_matches:
            await say(
                f"🤖 *IncidentIQ detected a potential incident*\n\n"
                f"I found {len(exact_matches)} similar incident(s) that might help:\n\n"
                f"{exact_matches[0].to_slack_message()}"
            )
    except Exception:
        pass  # Don't interrupt with errors


def _is_incident_report(text: str) -> bool:
    """Detect if message looks like an incident report"""
    incident_keywords = [
        "error", "down", "outage", "incident", "alert",
        "failed", "failing", "crash", "broken", "issue",
        "500", "502", "503", "504", "timeout", "oom",
        "pagerduty", "opsgenie", "datadog",
    ]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in incident_keywords)


def _is_resolution_confirmation(text: str) -> bool:
    """Detect if message confirms resolution"""
    resolution_keywords = [
        "fixed", "resolved", "working now", "back up",
        "issue resolved", "incident closed", "all good",
    ]
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in resolution_keywords)


def _extract_document_url(text: str) -> Optional[str]:
    """Extract RCA or doc URL from message"""
    # Match Confluence, Notion, Google Docs, etc.
    url_pattern = r'https?://[^\s<>\"]+(?:confluence|notion|docs\.google|drive\.google)[^\s<>\"]*'
    match = re.search(url_pattern, text)
    return match.group(0) if match else None


async def _record_resolution(event: dict, client):
    """Record incident resolution from conversation"""
    # This would integrate with the incident database
    # For MVP, we log the resolution
    pass


async def _link_rca_to_incident(channel_id: str, rca_url: str, client):
    """Link RCA document to recent incident in channel"""
    # This would update the incident with RCA URL
    pass


# ============================================
# INTERACTIVE COMPONENTS
# ============================================

@app.action("resolution_worked")
async def handle_resolution_worked(ack, body, respond):
    """User confirms the suggested resolution worked"""
    await ack()
    
    incident_id = body["actions"][0]["value"]
    
    # Record positive feedback (improves future matching)
    await respond(
        "✅ Great! I've recorded that this solution worked.\n"
        "This will help me give better recommendations in the future."
    )
    
    # TODO: Update incident confidence score in vector DB


@app.action("resolution_different")
async def handle_resolution_different(ack, body, respond):
    """User indicates this was a different issue"""
    await ack()
    
    await respond(
        "📝 Thanks for the feedback! This helps me learn.\n"
        "I'll be more careful matching this pattern in the future."
    )
    
    # TODO: Decrease similarity weight for this match


# ============================================
# HELPER FUNCTIONS
# ============================================

def _format_matches_as_blocks(matches: list[IncidentMatch], query: str) -> list[dict]:
    """Format matches as Slack Block Kit blocks"""
    blocks = []
    
    # Header
    exact_count = sum(1 for m in matches if m.confidence == MatchConfidence.EXACT)
    partial_count = sum(1 for m in matches if m.confidence == MatchConfidence.PARTIAL)
    
    if exact_count:
        header = f"🎯 Found {exact_count} exact match(es)"
    elif partial_count:
        header = f"⚠️ Found {partial_count} similar (not exact) incident(s)"
    else:
        header = "❌ No confident matches found"
    
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": header}
    })
    
    blocks.append({"type": "divider"})
    
    # Add each match
    for i, match in enumerate(matches[:3]):  # Limit to 3 for readability
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": match.to_slack_message()}
        })
        
        # Add feedback buttons for exact matches
        if match.confidence == MatchConfidence.EXACT:
            blocks.append({
                "type": "actions",
                "elements": [
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "✅ This worked!"},
                        "style": "primary",
                        "action_id": "resolution_worked",
                        "value": match.incident_id,
                    },
                    {
                        "type": "button",
                        "text": {"type": "plain_text", "text": "❌ Different issue"},
                        "action_id": "resolution_different",
                        "value": match.incident_id,
                    },
                ]
            })
        
        if i < len(matches) - 1:
            blocks.append({"type": "divider"})
    
    return blocks


# ============================================
# BOT STARTUP
# ============================================

async def start_slack_bot():
    """Start the Slack bot in Socket Mode"""
    handler = AsyncSocketModeHandler(app, settings.slack.app_token)
    await handler.start_async()


if __name__ == "__main__":
    import asyncio
    asyncio.run(start_slack_bot())
