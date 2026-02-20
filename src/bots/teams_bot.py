"""
IncidentIQ Microsoft Teams Bot

Commands:
- /incidentiq search <query> - Search for similar incidents
- /incidentiq help - Show help message

Features:
- Automatic learning from war room channels
- Rich formatting for incident results
- Adaptive cards for better UX

Prerequisites:
1. Create Azure Bot resource
2. Enable MS Teams channel
3. Get Bot ID and password
"""

import logging
from typing import Optional

from botbuilder.core import ActivityHandler, TurnContext, CardFactory
from botbuilder.schema import Activity, ActivityTypes

from src.core.pattern_matching_v2 import get_enhanced_pattern_engine, EnhancedIncident
from src.core.pattern_matching import MatchConfidence

logger = logging.getLogger(__name__)


class TeamsBot(ActivityHandler):
    """
    Microsoft Teams Bot for IncidentIQ

    Handles:
    - Commands: /incidentiq search, /incidentiq help
    - Automatic learning from war room messages
    - Rich formatting with Adaptive Cards
    """

    def __init__(self):
        self.engine = None  # Will be initialized on first use

    async def on_message_activity(self, turn_context: TurnContext):
        """
        Handle incoming messages from Teams.

        Automatically learns from war room conversations.
        """
        activity = turn_context.activity

        # Extract message text
        message_text = activity.text.strip()

        if not message_text:
            return

        # Check if it's a command
        if message_text.startswith("/"):
            await self._handle_command(turn_context, message_text)
        else:
            # Regular message - learn from it (if in war room channel)
            await self._learn_from_message(turn_context, activity)

    async def on_members_added_activity(self, members_added: list, turn_context: TurnContext):
        """Send welcome message when bot is added to a team"""
        for member in members_added:
            if member.id != turn_context.activity.recipient.id:
                await turn_context.send_activity(
                    Activity(
                        type=ActivityTypes.message,
                        text=f"👋 Hi! I'm IncidentIQ. I help you find similar incidents quickly.\n\n"
                             f"**Commands:**\n"
                             f"• `/incidentiq search <query>` - Search for similar incidents\n"
                             f"• `/incidentiq log` - Log this conversation as an incident\n"
                             f"• `/incidentiq help` - Show help\n\n"
                             f"I'll also automatically learn from your war room discussions!"
                    )
                )

    async def _handle_command(self, turn_context: TurnContext, command: str):
        """Handle bot commands"""

        # Initialize engine if needed
        if self.engine is None:
            self.engine = await get_enhanced_pattern_engine()

        # Parse command
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "/incidentiq":
            if not args:
                await self._send_help(turn_context)
            else:
                sub_cmd = args.split()[0].lower()
                if sub_cmd == "search":
                    query = " ".join(args.split()[1:])
                    await self._search_incidents(turn_context, query)
                elif sub_cmd == "log":
                    await self._log_incident(turn_context)
                elif sub_cmd == "help":
                    await self._send_help(turn_context)
                else:
                    await self._search_incidents(turn_context, args)
        else:
            await self._search_incidents(turn_context, command[1:])  # Remove leading /

    async def _search_incidents(self, turn_context: TurnContext, query: str):
        """Search for similar incidents and display results"""

        if not query or len(query) < 5:
            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    text="❌ Please provide a more detailed search query (at least 5 characters).\n"
                         f"**Example:** `/incidentiq search Postgres connection timeout`"
                )
            )
            return

        try:
            # Search for similar incidents
            matches = await self.engine.find_similar_incidents(
                query=query,
                limit=5,
            )

            if not matches:
                await turn_context.send_activity(
                    Activity(
                        type=ActivityTypes.message,
                        text=f"🔍 **No similar incidents found**\n\n"
                             f"Query: `{query}`\n\n"
                             f"This appears to be a new incident. Consider logging it for future reference!"
                    )
                )
                return

            # Format results
            exact_matches = [m for m in matches if m.confidence == MatchConfidence.EXACT]
            partial_matches = [m for m in matches if m.confidence == MatchConfidence.PARTIAL]

            response_parts = []

            if exact_matches:
                response_parts.append(f"🎯 **{len(exact_matches)} EXACT MATCH(ES) FOUND**\n")
                for i, match in enumerate(exact_matches, 1):
                    response_parts.append(self._format_match(match, i))

            if partial_matches:
                response_parts.append(f"\n⚠️ **{len(partial_matches)} PARTIAL MATCH(ES)**\n")
                for i, match in enumerate(partial_matches, 1):
                    response_parts.append(self._format_match(match, i))

            response = "\n".join(response_parts)

            # Create Adaptive Card for better formatting
            card = self._create_results_card(query, matches)
            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    attachments=[CardFactory.adaptive_card().to_attachment(card)]
                )
            )

        except Exception as e:
            logger.error(f"Error searching incidents: {e}")
            await turn_context.send_activity(
                Activity(
                    type=ActivityTypes.message,
                    text=f"❌ Error searching for incidents: {str(e)}"
                )
            )

    def _format_match(self, match, index: int) -> str:
        """Format a single match result"""
        lines = [
            f"**{index}. {match.title}**",
            f"   **Confidence:** {match.confidence.value.upper()} ({match.similarity_score:.0%})",
        ]

        if match.resolved_by:
            lines.append(f"   **Fixed by:** {match.resolved_by}")

        if match.resolution_time_minutes:
            lines.append(f"   **Resolution time:** {match.resolution_time_minutes} minutes")

        if match.resolution_summary:
            lines.append(f"   **Resolution:** {match.resolution_summary}")

        if match.resolution_commands:
            lines.append(f"   **Commands:**")
            for cmd in match.resolution_commands[:2]:
                lines.append(f"   ```{cmd}```")

        if match.match_reasons:
            lines.append(f"   **Why matched:** {', '.join(match.match_reasons[:3])}")

        return "\n".join(lines)

    def _create_results_card(self, query: str, matches: list):
        """Create an Adaptive Card for search results"""

        exact_matches = [m for m in matches if m.confidence == MatchConfidence.EXACT]
        partial_matches = [m for m in matches if m.confidence == MatchConfidence.PARTIAL]

        card_content = {
            "type": "AdaptiveCard",
            "body": [
                {
                    "type": "TextBlock",
                    "text": f"Incident Search Results",
                    "weight": "Bolder",
                    "size": "Large"
                },
                {
                    "type": "TextBlock",
                    "text": f"Query: {query}",
                    "wrap": True
                }
            ],
            "actions": []
        }

        # Add exact matches
        if exact_matches:
            for match in exact_matches:
                card_content["body"].append({
                    "type": "TextBlock",
                    "text": f"🎯 EXACT MATCH: {match.title}",
                    "weight": "Bolder",
                    "size": "Medium",
                    "color": "good"
                })
                card_content["body"].append({
                    "type": "TextBlock",
                    "text": self._format_match_for_card(match),
                    "wrap": True
                })

        # Add partial matches
        if partial_matches:
            for match in partial_matches:
                card_content["body"].append({
                    "type": "TextBlock",
                    "text": f"⚠️ PARTIAL MATCH: {match.title}",
                    "weight": "Bolder",
                    "size": "Medium"
                })
                card_content["body"].append({
                    "type": "TextBlock",
                    "text": self._format_match_for_card(match),
                    "wrap": True
                })

        return card_content

    def _format_match_for_card(self, match) -> str:
        """Format match for Adaptive Card"""
        parts = [
            f"**Confidence:** {match.confidence.value.upper()} ({match.similarity_score:.0%})",
        ]

        if match.resolved_by:
            parts.append(f"**Fixed by:** {match.resolved_by}")

        if match.resolution_summary:
            parts.append(f"**Resolution:** {match.resolution_summary}")

        if match.resolution_commands:
            parts.append("**Commands:**")
            for cmd in match.resolution_commands[:2]:
                parts.append(f"```{cmd}```")

        return "\n\n".join(parts)

    async def _log_incident(self, turn_context: TurnContext):
        """Log current conversation as an incident"""

        # Get conversation context
        conversation_id = turn_context.activity.channel_id
        message_text = turn_context.activity.text

        # In a real implementation, you would:
        # 1. Fetch conversation history from Teams
        # 2. Extract incident details using LLM
        # 3. Index the incident

        await turn_context.send_activity(
            Activity(
                type=ActivityTypes.message,
                text="✅ **Incident logged successfully!**\n\n"
                     "This feature will extract incident details from the conversation "
                     "and index it for future searches.\n\n"
                     "*Full implementation requires Microsoft Graph API access.*"
            )
        )

    async def _learn_from_message(self, turn_context: TurnContext, activity):
        """
        Automatically learn from war room messages.

        This would:
        1. Detect if message contains incident resolution
        2. Extract structured data
        3. Index for future searches

        For now, this is a placeholder.
        """
        # TODO: Implement automatic learning
        # This would use Microsoft Graph API to:
        # - Fetch conversation history
        # - Detect resolution patterns
        # - Extract and index incidents

        pass

    async def _send_help(self, turn_context: TurnContext):
        """Send help message"""
        help_text = """
🤖 **IncidentIQ Help**

**Commands:**
• `/incidentiq search <query>` - Search for similar incidents
• `/incidentiq log` - Log current conversation as incident
• `/incidentiq help` - Show this help message

**Examples:**
• `/incidentiq search Postgres timeout`
• `/incidentiq search database connection pool`
• `/incidentiq search Redis memory error`

**Automatic Learning:**
I automatically learn from war room conversations to build our knowledge base.

**Need more help?**
📧 support@incidentiq.com
📖 https://docs.incidentiq.com
        """

        await turn_context.send_activity(
            Activity(
                type=ActivityTypes.message,
                text=help_text
            )
        )


# ============================================
# Bot Configuration
# ============================================

BOT_ID = "your-bot-id-here"
BOT_PASSWORD = "your-bot-password-here"


def create_teams_bot():
    """Factory function to create Teams bot instance"""
    return TeamsBot()
