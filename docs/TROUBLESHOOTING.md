# Troubleshooting

## Common Issues

### Port Already in Use

**Error:** `OSError: [Errno 48] Address already in use`

**Solution:**
```bash
# Find process using port 8082
lsof -i :8082

# Kill the process
kill -9 <PID>

# Or use the management script
./manage.sh stop
```

### API Key Not Set

**Error:** `500 Internal Server Error - Missing NVIDIA_NIM_API_KEY`

**Solution:**
```bash
# Create .env file from example
cp .env.example .env

# Edit .env and add your key
NV NVIDIA_NIM_API_KEY=nvapi-your-key-here
```

### Service Not Starting

**Error:** Service starts but immediately exits

**Solution:**
```bash
# Check service logs
./manage.sh logs

# Try running in foreground to see errors
./run.sh

# Common issues:
# - Missing dependencies: pip install -e .
# - Invalid .env file: check for extra spaces or special characters
# - Port conflict: see "Port Already in Use" above
```

### Rate Limit Errors

**Error:** `429 Too Many Requests`

**Solution:**
- NVIDIA NIM free tier allows 40 requests/minute
- The bridge automatically handles rate limiting
- Wait 30-60 seconds for the rate window to reset
- Consider upgrading to a paid tier for higher limits

### Model Not Found

**Error:** `404 Model not found`

**Solution:**
```bash
# Check available models
curl -H "Authorization: Bearer $NVIDIA_NIM_API_KEY" \
  https://integrate.api.nvidia.com/v1/models

# Verify MODEL in .env matches an available model
# Default: moonshotai/kimi-k2-thinking
```

### Connection Timeouts

**Error:** `TimeoutError: Connecting to NVIDIA API`

**Solution:**
```bash
# Check internet connectivity
ping integrate.api.nvidia.com

# Check if NVIDIA service is operational
curl https://build.nvidia.com

# If using a proxy, ensure it's configured correctly
export HTTP_PROXY=http://proxy.example.com:8080
export HTTPS_PROXY=http://proxy.example.com:8080
```

### Empty or No Response

**Issue:** Response has no content or just whitespace

**Solution:**
- Some models require a minimum prompt length
- Try adding more detail to your message
- Check if `max_tokens` is too low (minimum: 1)
- Increase `max_tokens` in your request

---

## Debugging

### Enable Debug Logging

```bash
# Set log level in .env
LOG_LEVEL=DEBUG

# Or modify api/app.py directly
logging.basicConfig(level=logging.DEBUG, ...)
```

### Enable Full Payload Logging

```bash
# Add to .env
LOG_FULL_PAYLOADS=true
# This will log full request/response payloads to server_debug.jsonl
```

### Check Service Health

```bash
# Health check endpoint
curl http://localhost:8082/health

# Should return JSON with status "ok"
```

### Verify NVIDIA API Access

```bash
# Test direct access to NVIDIA API (requires your key)
curl -H "Authorization: Bearer $NVIDIA_NIM_API_KEY" \
  https://integrate.api.nvidia.com/v1/models

# Should return JSON with available models
```

---

## Service Management Issues

### Start/Stop Commands Not Working

**Solution:**
```bash
# Check if script has execute permissions
ls -la manage.sh

# Add execute permissions if needed
chmod +x manage.sh run.sh start_service.sh stop_service.sh

# Verify shell is bash/zsh (not sh)
./manage.sh status
```

### Auto-Start Not Working

**macOS (LaunchAgent):**
```bash
# Check if LaunchAgent is loaded
launchctl list | grep claude-nim-bridge

# View LaunchAgent logs
log showpredicate 'process=="claude-nim-bridge"' --last 1h

# Try manual start
launchctl start com.claude-nim-bridge
```

**Linux (systemd):**
```bash
# Check service status
sudo systemctl status claude-nim-bridge

# View logs
sudo journalctl -u claude-nim-bridge -n 100

# Check if service is enabled
sudo systemctl is-enabled claude-nim-bridge
```

---

## Claude Code Integration Issues

### Claude Code Can't Connect

**Solution:**
```bash
# Check if proxy is running
curl http://localhost:8082/health

# Check Claude Code configuration
cat ~/.claude/settings.json

# Should contain:
# {
#   "apiBase": "http://localhost:8082",
#   "apiKey": "ccnim"
# }

# Try with explicit environment variables
ANTHROPIC_AUTH_TOKEN=ccnim \
ANTHROPIC_BASE_URL=http://localhost:8082 \
claude
```

### Response Format Issues

**Issue:** Response doesn't match expected Anthropic format

**Solution:**
- The bridge handles format conversion automatically
- Check you're using the latest version
- Report the issue with example request/response at GitHub Issues

---

## Performance Issues

### Slow Response Times

**Possible causes:**
1. Network latency to NVIDIA servers
2. Large response generation
3. Streaming overhead

**Solutions:**
```bash
# Check network latency
ping integrate.api.nvidia.com

# Reduce max_tokens for faster responses
"max_tokens": 100  # instead of 4096

# Use non-streaming mode for simple requests
"stream": false
```

### High Memory Usage

**Solution:**
```bash
# Check memory usage
ps aux | grep server:app

# Restart service periodically
./manage.sh restart

# Verify client cleanup is working
# (handled automatically by async resource cleanup)
```

---

## Logs

### Log Files

| File | Description |
|------|-------------|
| `service.log` | Main service log |
| `server_debug.jsonl` | Full payload logs (if enabled) |

### Viewing Logs

```bash
# Follow real-time logs
./manage.sh logs

# Or manually
tail -f service.log

# View last 100 lines
tail -n 100 service.log

# Search for errors
grep -i error service.log
```

---

## Getting Help

If you continue to experience issues:

1. **Check the GitHub Issues** https://github.com/Aixxww/Claude-NIM-Bridge/issues
2. **Create a new issue** with:
   - Error message
   - Steps to reproduce
   - System information (OS, Python version)
   - Relevant logs (sanitized)
3. **Check NVIDIA Status** https://status.nvidia.com/

---

## Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `NVIDIA_NIM_API_KEY` | Your NVIDIA API key | (required) |
| `MODEL` | Default model to use | `moonshotai/kimi-k2-thinking` |
| `NVIDIA_NIM_RATE_LIMIT` | Rate limit per window | `40` |
| `NVIDIA_NIM_RATE_WINDOW` | Rate window in seconds | `60` |
| `FAST_PREFIX_DETECTION` | Enable prefix detection | `true` |
| `ENABLE_NETWORK_PROBE_MOCK` | Mock network probes | `true` |
| `ENABLE_TITLE_GENERATION_SKIP` | Skip title generation | `true` |
| `HOST` | Server host | `0.0.0.0` |
| `PORT` | Server port | `8082` |
