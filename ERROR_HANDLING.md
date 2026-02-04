# Error Handling & Robustness Features

The ingestion pipeline includes comprehensive error handling to ensure reliability during long-running operations.

## Features

### 1. Retry Logic with Exponential Backoff

All Anthropic API calls automatically retry on failure with exponential backoff:

- **Max retries**: 5 attempts
- **Initial delay**: 2 seconds
- **Exponential base**: 2x (delays: 2s, 4s, 8s, 16s, 32s)
- **Max delay**: 60 seconds

This handles transient errors like:
- Network timeouts
- Rate limiting
- Temporary API unavailability

**Implementation**: See `lib/retry.py` for the retry decorator.

### 2. Graceful Failure Handling

If a single paper fails during ingestion, the pipeline:
- ✓ Logs the error with full stack trace
- ✓ Displays a warning message
- ✓ Marks the paper as failed in state file
- ✓ **Continues with the next paper** (doesn't crash)

This ensures one problematic PDF doesn't block the entire batch.

### 3. Progress Tracking

The ingestion pipeline provides detailed progress feedback:

- **Progress bar**: Shows current paper being processed
- **Real-time status**: Displays extraction, metadata, chunking progress
- **Logging**: Writes detailed logs to `data/ingest.log`
- **Statistics**: Shows success/failure counts at the end

### 4. Resume Capability

If ingestion crashes or is interrupted, you can resume:

**State file**: `data/ingest_state.json`
```json
{
  "completed": ["paper1.pdf", "paper2.pdf"],
  "failed": ["paper3.pdf"],
  "last_updated": "2026-02-04 12:34:56"
}
```

**On restart**:
- ✓ Skips already-processed papers
- ✓ Skips previously-failed papers (can retry manually)
- ✓ Continues from where it left off

**Benefits**:
- Save time on large batches
- Recover from crashes without starting over
- Avoid re-calling expensive API operations

## Usage

### Normal Ingestion

```bash
python scripts/ingest.py
```

Output shows progress and handles errors automatically.

### Resume After Interruption

Just run the same command again:

```bash
python scripts/ingest.py
```

It will automatically detect and skip completed papers.

### Retry Failed Papers

1. Edit `data/ingest_state.json`
2. Remove failed paper names from `"failed"` array
3. Run ingestion again

Or delete the state file to start fresh:

```bash
rm data/ingest_state.json
python scripts/ingest.py
```

## Logging

### Log File Location

`data/ingest.log`

### Log Contents

- Timestamps for all operations
- Success/failure for each paper
- Full error messages with stack traces
- API retry attempts

### View Recent Logs

```bash
tail -50 data/ingest.log
```

### View Errors Only

```bash
grep ERROR data/ingest.log
```

## Error Scenarios

### Scenario 1: PDF Extraction Fails

**What happens**:
1. Error logged to `data/ingest.log`
2. Paper marked as failed in state
3. Warning displayed
4. **Continues with next paper**

**Result**: Other papers still get processed.

### Scenario 2: API Rate Limit Hit

**What happens**:
1. Request fails with rate limit error
2. Retry logic waits (exponential backoff)
3. Request retried up to 5 times
4. If all retries fail, paper marked as failed

**Result**: Automatic handling of rate limits.

### Scenario 3: Metadata Extraction Fails

**What happens**:
1. Retry logic attempts 5 times
2. If all fail, uses default metadata
3. Paper still gets ingested (without metadata)
4. Warning logged

**Result**: Paper is not lost, just missing metadata tags.

### Scenario 4: Process Crashes Halfway

**What happens**:
1. State file has list of completed papers
2. On restart, those papers are skipped
3. Processing resumes from next paper

**Result**: No wasted work, immediate resume.

## Configuration

### Adjust Retry Settings

Edit `lib/retry.py`:

```python
@retry_with_exponential_backoff(
    max_retries=5,        # Change retry count
    initial_delay=2.0,    # Change initial delay
    exponential_base=2.0, # Change backoff rate
    max_delay=60.0        # Change max delay cap
)
```

### Change Rate Limit Delay

Edit `scripts/ingest.py`:

```python
# Add delay to avoid rate limits
time.sleep(30)  # Change from 30 seconds
```

### Disable Resume Capability

Delete state file before each run:

```bash
rm data/ingest_state.json && python scripts/ingest.py
```

## Best Practices

1. **Monitor logs**: Check `data/ingest.log` during long runs
2. **Start small**: Test with a few papers before processing large batches
3. **Review failures**: After ingestion, check which papers failed and why
4. **Keep state file**: Don't delete it unless you want to reprocess everything
5. **Set API key**: Ensure `ANTHROPIC_API_KEY` is set to enable metadata extraction

## Troubleshooting

### "All papers already processed"

**Cause**: State file shows all papers completed.

**Solution**: Delete state file to reprocess:
```bash
rm data/ingest_state.json
```

### "Failed after 5 retries"

**Cause**: Persistent API or network issue.

**Solution**:
1. Check API key is valid
2. Check network connection
3. Wait a few minutes and retry
4. Check `data/ingest.log` for details

### Papers stuck in "failed" list

**Cause**: Permanent issue with those PDFs.

**Solution**:
1. Check log for specific error
2. Manually inspect the PDF files
3. Fix issues or remove problematic PDFs
4. Remove from failed list to retry

## Technical Details

### Retry Decorator

The `@anthropic_api_call_with_retry` decorator wraps any function:

```python
from lib.retry import anthropic_api_call_with_retry

@anthropic_api_call_with_retry
def my_api_call():
    # This will automatically retry on failure
    return client.messages.create(...)
```

### State Management

State is saved after **every paper** completes or fails:

```python
# After success
state['completed'].append(filename)
save_ingest_state(state)

# After failure
state['failed'].append(filename)
save_ingest_state(state)
```

This ensures minimal work is lost even if process crashes.
