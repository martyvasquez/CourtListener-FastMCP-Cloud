# FastMCP Cloud Deployment Guide

## Summary of Changes

Your CourtListener MCP Server has been upgraded for FastMCP 2.0 Cloud deployment. Here are the changes made:

### Files Modified
1. **app/server.py** - Refactored server initialization to use lazy loading pattern
2. **cloud.py** (NEW) - Cloud deployment entrypoint
3. **.env.example** (NEW) - Environment variable documentation

### What Changed

**Before:**
- Server used `asyncio.run(setup())` at module level
- This caused issues with FastMCP tooling and cloud deployment

**After:**
- Server uses lazy initialization via `_ensure_setup()` function
- Sub-servers load automatically when server starts
- Compatible with FastMCP Cloud, local development, and testing tools

## Deploying to FastMCP Cloud

### Step 1: Prepare Your Repository

1. **Commit the changes to your repository:**
   ```bash
   git add app/server.py cloud.py .env.example
   git commit -m "Upgrade to FastMCP 2.0 Cloud compatibility"
   git push origin main
   ```

### Step 2: Deploy to FastMCP Cloud

1. **Visit FastMCP Cloud:**
   - Go to https://fastmcp.cloud
   - Sign in with your GitHub account

2. **Create a New Project:**
   - Click "New Project"
   - Select your repository
   - Configure the following settings:

   **Project Configuration:**
   ```
   Name: court-listener-mcp
   (This will create URL: https://court-listener-mcp.fastmcp.app/mcp)

   Entrypoint: cloud.py:mcp

   Authentication: Disabled (for now)
   (Enable later when ready for production use)
   ```

3. **Add Environment Variables:**
   - In project settings, add:
     ```
     COURT_LISTENER_API_KEY=your_actual_api_key_here
     ```
   - Optional variables (if you want to override defaults):
     ```
     COURTLISTENER_BASE_URL=https://www.courtlistener.com/api/rest/v4/
     COURTLISTENER_TIMEOUT=30
     COURTLISTENER_LOG_LEVEL=INFO
     ```

4. **Deploy:**
   - FastMCP Cloud will automatically:
     - Clone your repository
     - Install dependencies from `pyproject.toml`
     - Build and deploy your server
     - Provide a unique URL for your server

### Step 3: Test Your Deployment

Once deployed, test your server with the FastMCP client:

```python
from fastmcp import Client
import asyncio

async def test_server():
    async with Client("https://court-listener-mcp.fastmcp.app/mcp") as client:
        # Test the status tool
        result = await client.call_tool("status")
        print("Server status:", result)

        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {len(tools)}")
        for tool in tools:
            print(f"  - {tool.name}")

asyncio.run(test_server())
```

### Step 4: Automatic Updates

FastMCP Cloud automatically redeploys when you push to `main`:

```bash
git add .
git commit -m "Update server functionality"
git push origin main
# FastMCP Cloud will automatically redeploy
```

## Local Development

### Running Locally

```bash
# Standard local development
python -m app.server

# Or with FastMCP dev mode
fastmcp dev cloud.py:mcp
```

### Testing Tools

```bash
# Inspect server structure
fastmcp inspect cloud.py:mcp

# Run tests
uv run pytest

# Check types
uv run mypy app/
```

## Advanced Configuration

### Enable Authentication

When ready for production:

1. **In FastMCP Cloud Dashboard:**
   - Go to your project settings
   - Enable "Authentication"
   - Only organization members can access

2. **Or implement custom OAuth/JWT:**
   ```python
   from fastmcp.auth import JWTAuth

   mcp = FastMCP(
       name="CourtListener MCP Server",
       auth=JWTAuth(
           jwks_uri="https://your-idp.com/.well-known/jwks.json",
           issuer="https://your-idp.com",
           audience="court-listener-mcp"
       )
   )
   ```

### Custom Domain

Contact FastMCP Cloud support to configure a custom domain for your server.

### Monitoring

FastMCP Cloud provides:
- Automatic logging
- Request metrics
- Error tracking
- Uptime monitoring

Access these in your project dashboard at https://fastmcp.cloud

## Troubleshooting

### Server Not Starting

1. **Check logs in FastMCP Cloud dashboard**
2. **Verify environment variables are set**
3. **Ensure COURT_LISTENER_API_KEY is valid**

### Tools Not Loading

If tools aren't appearing:
1. Check that sub-servers are importing correctly
2. Verify no syntax errors in tool definitions
3. Check FastMCP Cloud deployment logs

### API Rate Limiting

If you hit CourtListener API rate limits:
1. Implement caching in your tools
2. Add rate limiting middleware
3. Consider upgrading your CourtListener API plan

## Support

- **FastMCP Cloud:** https://fastmcp.cloud
- **FastMCP Docs:** https://gofastmcp.com
- **CourtListener API:** https://www.courtlistener.com/api/rest-info/
- **Issues:** Your repository's GitHub Issues page

## Next Steps

After deployment:

1. ✅ Test all tools via the cloud URL
2. ✅ Set up continuous integration for testing
3. ✅ Configure authentication for production use
4. ✅ Monitor usage and performance
5. ✅ Add custom resources and prompts as needed
6. ✅ Share your server with your team!

---

**Your server is now ready for FastMCP Cloud deployment! 🚀**
