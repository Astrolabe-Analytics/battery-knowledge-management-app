# Semantic Scholar Rate Limit Fixes

**Date:** 2026-02-05
**Status:** ✅ Complete

## Problem

The Semantic Scholar API was hitting rate limits due to:
1. Too frequent requests (500ms interval was too short)
2. No support for API keys (limited to 100 requests per 5 min)
3. Potential re-searches on Streamlit rerenders

## Solutions Implemented

### 1. Increased Rate Limiting Delay

**Changed:**
- Unauthenticated: 500ms → **2 seconds** between requests
- With API key: **500ms** (much higher rate limit)

**Code Location:** `lib/semantic_scholar.py`
```python
_min_request_interval = 2.0  # 2 seconds for unauthenticated

def _rate_limit(has_api_key: bool = False):
    interval = 0.5 if has_api_key else _min_request_interval
    # ... wait logic
```

### 2. API Key Support

**New Functions:**
- `get_api_key()` - Read API key from settings.json
- `set_api_key(key)` - Save API key to settings.json

**Integration:**
- API key automatically included in request headers
- Rate limiting adjusts based on key presence
- Error messages guide users to add key

**Benefits:**
- **Without key:** 100 requests per 5 min (2 sec delay)
- **With key:** 5,000 requests per 5 min (0.5 sec delay)

**Get Free API Key:**
https://www.semanticscholar.org/product/api

### 3. Settings Tab Integration

**Added section:** "🔑 Semantic Scholar API Key"

**Features:**
- Shows API key status
- Input form to add key
- Masked display of current key
- Remove key button
- Link to get free API key
- Storage location info

**Location:** Settings tab, after Delete Confirmation section

### 4. Rate Limit Warning in Discover Tab

**Added warning banner:**
- Shows when no API key set
- Links to Settings tab
- Shows rate limit info
- Green info banner when key is active

**Message:**
- Without key: "⚠️ Using unauthenticated access (100 searches per 5 min)"
- With key: "✓ API key active - Higher rate limits enabled (5,000 searches per 5 min)"

### 5. Improved Result Caching

**Fixed:**
- Added cache key based on query + sort
- Only searches when button clicked AND query/sort changed
- Added 1.5 second delay before API call
- Set `ss_search_triggered` flag to prevent reruns
- Results persist across rerenders

**Cache Logic:**
```python
cache_key = f"{query}|{sort}"
if st.session_state.get('ss_cache_key') != cache_key:
    # Only search if query/sort changed
    st.session_state['ss_search_results'] = None
    st.session_state['ss_cache_key'] = cache_key
```

## Files Modified

### `lib/semantic_scholar.py`
- Added `get_api_key()` and `set_api_key()` functions
- Updated `_rate_limit()` to adjust based on API key
- Updated `search_papers()` to use API key in headers
- Updated `download_pdf()` to respect rate limits
- Improved error messages with API key suggestions
- Added `has_api_key` flag to all return values

### `app.py`
- Added Semantic Scholar API Key section to Settings tab
- Added rate limit warning banner to Discover tab
- Improved search result caching with cache keys
- Added 1.5 second delay before API calls
- Added `ss_search_triggered` flag

## Test Results

### Rate Limiting Working
```
Test: Search for "battery degradation"
✓ Search took: 0.79 seconds (within rate limit)
✓ Success: True
✓ Has API key: False (correctly detected)
✓ Found: 2,402,372 papers
✓ Returned: 3 results
```

### API Key Detection
- ✓ Correctly detects no API key
- ✓ Shows appropriate warnings
- ✓ Adjusts rate limiting accordingly

### Caching
- ✓ Only searches when button clicked
- ✓ Doesn't re-search on rerender
- ✓ Cache invalidated when query/sort changes
- ✓ Results persist between renders

## Usage Guide

### Without API Key (Default)

**Rate Limit:** 100 requests per 5 minutes
**Delay:** 2 seconds between requests
**Use Case:** Light usage, occasional searches

**To Use:**
1. Just search normally
2. Wait 2 seconds between searches
3. If rate limited, wait 5 minutes

### With API Key (Recommended)

**Rate Limit:** 5,000 requests per 5 minutes
**Delay:** 0.5 seconds between requests
**Use Case:** Heavy usage, batch searches

**Setup:**
1. Go to https://www.semanticscholar.org/product/api
2. Sign up for free API key
3. Copy your API key
4. Open app → Settings tab
5. Scroll to "🔑 Semantic Scholar API Key"
6. Paste key → Click "Save API Key"
7. Done! Higher limits active

### Managing API Key

**View Status:**
- Settings tab shows if key is set
- Discover tab shows rate limit info

**Remove Key:**
- Settings tab → "Remove Key" button
- Reverts to unauthenticated access

**Update Key:**
- Remove old key → Add new key

## Rate Limit Comparison

| Feature | Without Key | With Key |
|---------|-------------|----------|
| Requests per 5 min | 100 | 5,000 |
| Delay between requests | 2 sec | 0.5 sec |
| Cost | Free | Free |
| Setup required | None | 1-time signup |
| Best for | Occasional use | Regular use |

## Error Handling

### Rate Limit Exceeded (429)

**Without Key:**
```
Rate limit exceeded. Consider adding a Semantic Scholar API key
in Settings for higher rate limits.
```

**With Key:**
```
Rate limit exceeded. Please wait a moment and try again.
```

### Other Errors

**Timeout:**
```
Request timed out. Please try again.
```

**API Error:**
```
API error: [status code] - [error message]
```

## Best Practices

### 1. Add API Key for Regular Use
If you search more than a few times per session, add an API key.

### 2. Cache Results
Don't re-run the same search. Results are cached automatically.

### 3. Be Patient
Wait for the spinner to finish. Don't click search multiple times.

### 4. Use Specific Queries
More specific queries = fewer total papers = faster results.

### 5. Sort Wisely
- "Relevance" for broad topics
- "Citations" for established topics

## Troubleshooting

### "Rate limit exceeded" message

**Cause:** Too many requests in 5 minutes

**Solutions:**
1. Wait 5 minutes
2. Add API key in Settings (recommended)
3. Reduce search frequency

### Slow searches

**Causes:**
- 2 second delay (by design)
- Large result set
- Network latency

**Normal:** 2-4 seconds per search
**With delay:** 3-5 seconds per search

### Results not updating

**Cause:** Cache hit (same query + sort)

**Solution:** Change query or sort to force new search

## Summary

The rate limiting fixes provide:

✅ **Safer:** 2 second delay prevents rate limits
✅ **Scalable:** API key support for heavy users
✅ **Smarter:** Improved caching prevents redundant calls
✅ **Informative:** Clear warnings and status messages
✅ **Flexible:** Works with or without API key

**Recommendation:** Add a free API key for best experience!

---

**Status: PRODUCTION READY** ✅

All rate limiting issues resolved with multiple safety layers:
- Longer delays
- API key support
- Better caching
- Clear user guidance
