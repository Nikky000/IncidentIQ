# 🤖 Microsoft Teams Bot Setup Guide

Complete guide to set up IncidentIQ with Microsoft Teams.

---

## 📋 Prerequisites

1. **Azure Account** (Free tier works for testing)
2. **Microsoft Teams** access
3. **Python 3.11+**
4. **Ngrok** (for local development tunneling)

---

## 🚀 Quick Setup (30 Minutes)

### Step 1: Create Azure Bot Resource

1. Go to [Azure Portal](https://portal.azure.com)
2. Click **"Create a resource"** and search for **"Azure Bot"**
3. Click **Create**

**Bot Details:**
- **Bot handle:** `incidentiq-bot` (or your preferred name)
- **Pricing tier:** Free (F0)
- **Type:** Multi-tenant
- Click **Review + Create**

### Step 2: Configure the Bot

1. After creation, go to your Bot resource
2. Click **"Configuration"** in left menu
3. Note down:
   - **Microsoft App ID** (your BOT_ID)
   - **Customer secret** (click to generate, copy it immediately)

### Step 3: Enable Microsoft Teams Channel

1. In your Bot resource, click **"Channels"** in left menu
2. Click **"Microsoft Teams"** icon
3. Click **"Agree"** to Terms of Service
4. Click **"Apply"** to save

### Step 4: Install Required Python Packages

```bash
cd /Users/dileshchouhan/zysecai/LeadTheAI/devops/incidentiq

# Add Microsoft Teams Bot Framework dependencies
pip install botbuilder-core==4.15.0
pip install botbuilder-schema==4.15.0
pip install botbuilder-integration-aiohttp==4.15.0
```

Or update `pyproject.toml`:

```toml
dependencies = [
    # ... existing dependencies ...

    # Microsoft Teams Bot Framework
    "botbuilder-core>=4.15.0",
    "botbuilder-schema>=4.15.0",
    "botbuilder-integration-aiohttp>=4.15.0",
]
```

Then reinstall:

```bash
pip install -e .
```

### Step 5: Configure Environment Variables

Create `.env` file or update existing:

```bash
# Microsoft Teams Bot Configuration
TEAMS_BOT_ID="your-microsoft-app-id-from-azure"
TEAMS_BOT_PASSWORD="your-customer-secret-from-azure"

# App Configuration
APP_BASE_URL="https://your-domain.com"  # Or ngrok URL for testing
```

### Step 6: Run the Bot Locally (with Ngrok)

```bash
# Install ngrok (if not installed)
brew install ngrok  # macOS

# In one terminal, start ngrok tunnel
ngrok http 8000

# Copy the HTTPS URL (e.g., https://abc123.ngrok.io)

# In another terminal, run the Teams bot
python -m src.bots.teams_bot
```

**Note:** Update your Azure Bot configuration:
- Go to **Configuration** → **Messaging endpoint**
- Set to: `https://abc123.ngrok.io/api/messages`
- Replace `abc123.ngrok.io` with your actual ngrok URL

### Step 7: Add Bot to Microsoft Teams

**Option A: Via Teams App Store (for testing)**
1. Open Microsoft Teams
2. Click **Apps** → **Manage your apps**
3. Click **Upload an app**
4. Upload the app manifest (from Azure Bot → Channels → Teams)
5. Add to a team/channel

**Option B: Direct Link (easiest for testing)**
1. In Azure Bot → Channels → Teams
2. Click **"Open in Teams"**
3. This opens Teams with the bot already added

---

## 🧪 Testing the Bot

### Test 1: Basic Commands

In your Teams channel where the bot is added:

```
/incidentiq help
```

Expected: Help message appears

### Test 2: Search (Mock Data First)

Since you don't have indexed incidents yet, let's add a test incident:

```python
# Create a test script: test_teams_bot.py
import asyncio
from src.core.pattern_matching_v2 import get_enhanced_pattern_engine, EnhancedIncident

async def test_search():
    # Initialize engine
    engine = await get_enhanced_pattern_engine()
    await engine.initialize_collections()

    # Create a test incident
    incident = EnhancedIncident(
        id="TEST-001",
        title="PostgreSQL Connection Timeout",
        description="Database connections timing out after 30 seconds",
        error_message="psycopg2.OperationalError: connection timeout",
        error_type="DatabaseError",
        service="api-gateway",
        resolution_summary="Increased max_connections from 100 to 200",
        resolution_commands=["ALTER SYSTEM SET max_connections = 200"],
    )

    # Index it
    await engine.index_incident(incident)
    print("✅ Test incident indexed!")

    # Now search for it
    matches = await engine.find_similar_incidents(
        query="database timeout",
        limit=5,
    )

    print(f"✅ Found {len(matches)} matches!")
    for match in matches:
        print(f"  - {match.title} ({match.similarity_score:.0%})")

if __name__ == "__main__":
    asyncio.run(test_search())
```

Run this:

```bash
python test_teams_bot.py
```

Then in Teams:

```
/incidentiq search database timeout
```

Expected: Bot returns the test incident

---

## 🔧 Configuration Options

### Enable/Disable Features

In `.env`:

```bash
# Enable automatic learning from war room
TEAMS_AUTO_LEARN=true

# Channel to learn from (your war room)
TEAMS_WAR_ROOM_CHANNEL="19:meeting_xyz@thread.tacv2"

# How many messages to look back for learning
TEAMS_LEARNING_LOOKBACK=100
```

---

## 📊 Bot Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `/incidentiq help` | Show help message | `/incidentiq help` |
| `/incidentiq search <query>` | Search similar incidents | `/incidentiq search Postgres timeout` |
| `/incidentiq log` | Log current conversation as incident | `/incidentiq log` |

---

## 🎨 Rich Message Formatting

The bot sends **Adaptive Cards** for better formatting:

- EXACT matches: Green indicator 🎯
- PARTIAL matches: Yellow indicator ⚠️
- Resolution details: Formatted with commands
- Confidence scores: Percentage display
- Match reasons: Why the incident matched

---

## 🚀 Production Deployment

### Option 1: Azure App Service (Recommended for MS Teams)

1. Create Azure App Service
2. Deploy bot as web app
3. Configure custom domain
4. Update bot's messaging endpoint

### Option 2: Container

```dockerfile
# Dockerfile for Teams bot
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install -e .

CMD ["python", "-m", "src.bots.teams_bot"]
```

Build and push to Azure Container Registry.

---

## 🐛 Troubleshooting

### Bot not responding?

1. Check bot is running:
```bash
curl http://localhost:8000/health
```

2. Check ngrok tunnel is active:
```bash
curl https://your-ngrok-url.ngrok.io/health
```

3. Check Azure Bot logs:
   - Go to Azure Portal → Your Bot → Logs

### "Forbidden" error?

- Verify Microsoft App ID and password are correct
- Check messaging endpoint URL is correct
- Ensure bot has permissions for the channel

### Commands not working?

- Ensure command starts with `/`
- Check bot has been added to the team
- Verify bot has message sending permissions

---

## 📝 Advanced: Automatic Learning Setup

To enable automatic learning from war room conversations:

### 1. Grant Microsoft Graph API Permissions

1. Go to Azure Portal → Azure AD → App Registrations
2. Find your bot's app registration
3. Add **Microsoft Graph** permissions:
   - `ChannelMessage.Read.All`
   - `Chat.Read`
   - `Team.ReadBasic.All`
4. Grant admin consent

### 2. Configure in `.env`:

```bash
# Microsoft Graph API
GRAPH_API_CLIENT_ID="your-app-id"
GRAPH_API_CLIENT_SECRET="your-client-secret"
GRAPH_API_TENANT_ID="your-tenant-id"

# Enable automatic learning
TEAMS_AUTO_LEARN=true
TEAMS_WAR_ROOM_CHANNEL="19:meeting_xyz@thread.tacv2"
```

### 3. Bot will automatically:

- Listen to all messages in war room channel
- Detect when incidents are resolved
- Extract structured data (title, error, resolution)
- Index automatically for future searches

---

## 🎓 Resources

- [Microsoft Bot Framework Documentation](https://docs.microsoft.com/en-us/azure/bot-service/)
- [Teams Bot Framework Samples](https://github.com/microsoft/BotBuilder-Samples)
- [Adaptive Cards Designer](https://adaptivecards.io/designer/)
- [Azure Bot Service Pricing](https://azure.microsoft.com/en-us/pricing/details/bot-service/)

---

## ✅ Checklist

Before deploying to production:

- [ ] Bot tested locally with ngrok
- [ ] All commands working
- [ ] Test incident indexed and searchable
- [ ] Error handling tested
- [ ] Logging configured
- [ ] Health check endpoint working
- [ ] Production URL configured
- [ ] SSL/TLS enabled (required for Teams)
- [ ] Rate limiting configured
- [ ] Monitoring/alerts set up

---

**Need help?**
- 📧 support@incidentiq.com
- 💬 [Join our Discord](https://discord.gg/incidentiq)
- 📖 [Full Documentation](https://docs.incidentiq.com)
