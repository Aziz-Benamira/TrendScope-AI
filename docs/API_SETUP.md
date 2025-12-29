# 🎬 TrendScope-AI - API Keys Setup Guide

## Required API Credentials

### 1. TMDB API Key

**Steps to obtain:**

1. Go to [TMDB website](https://www.themoviedb.org/)
2. Create an account or log in
3. Go to Settings → API
4. Request an API key (choose "Developer" option)
5. Fill in the application form (use "Educational/Personal" as purpose)
6. Copy your API key (v3 auth)

**Add to `.env`:**
```env
TMDB_API_KEY=your_api_key_here
```

---

### 2. Reddit API Credentials

**Steps to obtain:**

1. Go to [Reddit Apps](https://www.reddit.com/prefs/apps)
2. Scroll to the bottom and click "create another app..."
3. Fill in:
   - **name**: TrendScope-AI
   - **type**: script
   - **description**: Movie trend analysis platform
   - **about url**: (leave blank)
   - **redirect uri**: http://localhost:8080
4. Click "create app"
5. Note down:
   - **Client ID**: Under the app name
   - **Client Secret**: The "secret" field

**Add to `.env`:**
```env
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USER_AGENT=TrendScope-AI/1.0
```

---

## Testing Your Credentials

### Test TMDB API:

```bash
# Linux/macOS
curl "https://api.themoviedb.org/3/trending/movie/day?api_key=YOUR_API_KEY"

# PowerShell
Invoke-WebRequest -Uri "https://api.themoviedb.org/3/trending/movie/day?api_key=YOUR_API_KEY"
```

### Test Reddit API:

You can test using the producer once the system is running.

---

## Security Notes

⚠️ **Never commit your `.env` file to version control!**

- The `.gitignore` file already excludes `.env`
- Use `.env.example` as a template
- Store production credentials securely (e.g., AWS Secrets Manager, HashiCorp Vault)

---

## Rate Limits

**TMDB:**
- 40 requests per 10 seconds
- Our default fetch interval (300s) is well within limits

**Reddit:**
- 60 requests per minute when using OAuth2
- Our streaming approach is optimized for this limit

---

## Troubleshooting

**TMDB "Invalid API key":**
- Double-check your API key in `.env`
- Ensure there are no extra spaces or quotes
- Verify the key is activated in TMDB settings

**Reddit "Invalid credentials":**
- Verify both CLIENT_ID and CLIENT_SECRET
- Check that the app type is "script"
- Ensure redirect URI is set correctly
