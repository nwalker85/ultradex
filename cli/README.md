# Ultradex CLI

Command-line interface for Ultradex - manage your professional relationships with AI.

## Overview

The Ultradex CLI provides administrative and operational commands for:
- Syncing contacts from Dex
- Running AI analysis on relationships
- Viewing contact details and AI insights
- Tracking analysis costs and statistics
- Managing configuration

## Requirements

- Go 1.21+
- Ultradex API running (docker-compose up)

## Installation

### From Source

```bash
cd ~/src/products/ultradex/cli
make install

# Verify installation
ultradex --version
```

### Manual Build

```bash
cd ~/src/products/ultradex/cli
go build -o bin/ultradex

# Copy to PATH
cp bin/ultradex ~/.local/bin/
export PATH="$HOME/.local/bin:$PATH"
```

## Quick Start

```bash
# Check API connectivity
ultradex health

# Sync contacts from Dex
ultradex sync

# Run analysis
ultradex analyze

# View results
ultradex contacts neglected
ultradex stats
```

## Commands

### sync

Sync all contacts from Dex to the local database.

```bash
ultradex sync
```

**Output:**
```
Syncing contacts from Dex...
✓ Successfully synced 247 contacts
  Status: success
  Timestamp: 2026-02-14 10:30:00
```

### analyze

Run AI analysis on contacts to identify neglected relationships.

```bash
# Analyze all contacts
ultradex analyze

# Analyze only first 50
ultradex analyze --limit 50

# Short flag
ultradex analyze -l 10
```

**Output:**
```
Running analysis... (limit: 10 contacts)
✓ Analysis complete
  Analyzed: 10 contacts
  Neglected found: 2
  Tokens used: 5000 (~$0.15)
  Timestamp: 2026-02-14 10:35:00

⚠ Found 2 neglected high-value contacts. Use 'ultradex contacts neglected' to see them.
```

### contacts

View and manage contacts.

#### contacts list

List all cached contacts with AI scores.

```bash
ultradex contacts list
```

**Output:**
```
NAME              COMPANY           JOB TITLE            VALUE  LAST ANALYZED
Jane Smith        Acme Corp         VP Engineering       82     2026-02-14
John Doe          TechStartup Inc   CTO                  71     2026-02-14
...
Total: 247 contacts
```

#### contacts neglected

Show high-value contacts you haven't reached out to recently.

```bash
ultradex contacts neglected
```

**Output:**
```
NAME              COMPANY           VALUE  DAYS AGO  RECOMMENDED ACTION
Jane Smith        Acme Corp         82     61        This week
John Doe          TechStartup Inc   71     45        Within 2 weeks
...
Neglected: 8 high-value contacts need attention
```

#### contacts view

View detailed information about a specific contact.

```bash
ultradex contacts view dex-123
```

**Output:**
```
=== Contact Details ===
Name: Jane Smith
Email: jane@acme.com
Company: Acme Corp
Job Title: VP Engineering
Phone: +1-555-0100

=== AI Analysis ===
Value Score: 82/100
Reason: Senior tech leader at growth-stage AI company. Strong mutual interest in LLM applications.
Outreach Strategy: Share recent article on token optimization. Reference previous conversation about multi-agent systems.
Suggested Timing: This week

=== Notes ===
Met at AI conference 2025. Interested in agent frameworks.
```

### stats

View analysis statistics and cost tracking.

```bash
ultradex stats
```

**Output:**
```
=== Analysis Statistics ===
Total Analysis Runs: 4
Total Contacts Analyzed: 156
Total Neglected Found: 18

=== Cost Tracking ===
Total Cost: $4.68
Average Cost Per Run: $1.17
Estimated Monthly Cost: $5.03

Last Updated: 2026-02-14 10:45:00

=== Recent Analysis Runs ===
1. 2026-02-14 10:35 [✓] 45 analyzed, 8 neglected ($0.68)
2. 2026-02-14 08:15 [✓] 52 analyzed, 6 neglected ($0.78)
3. 2026-02-14 06:00 [✓] 34 analyzed, 2 neglected ($0.51)
4. 2026-02-13 22:45 [✓] 25 analyzed, 2 neglected ($0.38)
```

### health

Check API connectivity and service status.

```bash
ultradex health
```

**Output:**
```
Checking Ultradex API at http://localhost:8000...
✓ API is healthy
  Status: ok
  Timestamp: 2026-02-14 10:50:00
```

### config

Manage CLI configuration.

#### config show

Display current configuration.

```bash
ultradex config show
```

**Output:**
```
=== Configuration ===
API URL: http://localhost:8000
Output Format: table
Timeout: 60 seconds

Config file: /home/user/.ultradex/config.yaml
(Using defaults - no config file yet)
```

#### config set

Set a configuration value.

```bash
ultradex config set api http://api.example.com:8000
ultradex config set output json
ultradex config set timeout 120
```

#### config get

Get a specific configuration value.

```bash
ultradex config get api
# Output: api = http://localhost:8000
```

#### config reset

Reset configuration to defaults.

```bash
ultradex config reset
```

## Configuration

Configuration is stored in `~/.ultradex/config.yaml`.

### Via Command

```bash
ultradex config set api http://api.example.com:8000
```

### Manually

Create `~/.ultradex/config.yaml`:

```yaml
api: http://localhost:8000
output: table
timeout: 60
```

### Environment Variables

Override config with environment variables:

```bash
export HRAFNGRIMA_API=http://api.example.com:8000
export HRAFNGRIMA_OUTPUT=json
export HRAFNGRIMA_TIMEOUT=120
```

## Global Flags

Available on all commands:

```bash
# Specify config file
ultradex --config /path/to/config.yaml [command]

# Specify API URL
ultradex --api http://api.example.com:8000 [command]
```

## Examples

### Daily Workflow

```bash
# Morning: Check what's happening
ultradex health
ultradex stats

# Run analysis if needed
ultradex analyze

# See who needs attention
ultradex contacts neglected

# Get details on someone
ultradex contacts view dex-456
```

### Batch Operations

```bash
# Sync and analyze
ultradex sync && ultradex analyze

# Check results
ultradex contacts neglected | head -5
ultradex stats
```

### Configuration

```bash
# Set API to production
ultradex config set api https://api.production.example.com:8000

# Or temporarily override
ultradex --api https://api.production.example.com:8000 contacts list
```

## Output Formats

### Table (Default)

```bash
ultradex contacts list
# Creates tabular output with alignment
```

### JSON (Future)

```bash
ultradex --output json contacts list
# Returns raw JSON for scripting
```

### CSV (Future)

```bash
ultradex --output csv contacts list
# Returns CSV for import to spreadsheet
```

## Error Handling

### API Unreachable

```
✗ API is unreachable: connection refused

Make sure the Ultradex API is running:
  docker-compose up
```

**Solution:**
```bash
# Start API
cd ~/src/products/ultradex
docker-compose up

# Or check what's running
docker ps | grep ultradex
```

### Invalid Contact ID

```
API error (404): Contact not found
```

**Solution:**
```bash
# List contacts to find valid ID
ultradex contacts list
ultradex contacts view [valid-id]
```

### Rate Limiting

If API returns 429 (Too Many Requests), wait before retrying:

```bash
sleep 5
ultradex [command]
```

## Building

### Development Build

```bash
cd cli
go build -o bin/ultradex

# Test
./bin/ultradex health
```

### Release Build

```bash
cd cli
make clean
make build

# Creates bin/ultradex
```

### Cross-Platform Build

```bash
# macOS
GOOS=darwin GOARCH=arm64 go build -o bin/ultradex-darwin

# Linux
GOOS=linux GOARCH=amd64 go build -o bin/ultradex-linux

# Windows
GOOS=windows GOARCH=amd64 go build -o bin/ultradex.exe
```

## Development

### Project Structure

```
cli/
├── main.go              # Entry point
├── go.mod              # Module definition
├── go.sum              # Dependency checksums
├── Makefile            # Build targets
├── cmd/
│   ├── root.go         # Root command + setup
│   ├── sync.go         # sync command
│   ├── analyze.go      # analyze command
│   ├── contacts.go     # contacts subcommands
│   ├── stats.go        # stats command
│   ├── health.go       # health command
│   └── config.go       # config subcommands
└── pkg/
    └── client/
        └── client.go   # HTTP API client
```

### Adding New Commands

1. Create file `cmd/[command].go`
2. Define `*cobra.Command`
3. Add to `rootCmd.AddCommand()` in `root.go`

Example:

```go
// cmd/export.go
var exportCmd = &cobra.Command{
    Use: "export",
    Short: "Export contacts",
    RunE: func(cmd *cobra.Command, args []string) error {
        // Implementation
        return nil
    },
}

// cmd/root.go init()
rootCmd.AddCommand(exportCmd)
```

### Testing

```bash
cd cli

# Run tests
make test

# Format code
make fmt

# Check for issues
make lint  # Requires golangci-lint
```

## Troubleshooting

### Build Fails: "command not found: go"

Install Go 1.21+:
```bash
# macOS
brew install go

# Or download from https://golang.org/dl/
```

### "API is unreachable"

Check that Ultradex API is running:
```bash
curl http://localhost:8000/health

# If not running, start it
cd ~/src/products/ultradex
docker-compose up
```

### Strange connection errors

Try resetting config:
```bash
ultradex config reset
ultradex health
```

## Performance

- **sync**: ~500ms (fast - just Dex API call + DB write)
- **analyze**: ~1-2 seconds per contact (rate limited)
- **contacts list**: ~100ms
- **contacts neglected**: ~50ms
- **stats**: ~100ms

For 200 contacts:
- Full sync + analyze: ~200 seconds (~3 minutes)
- Just query neglected: <100ms

## Future Enhancements

- [ ] JSON/CSV output formats
- [ ] Export to file
- [ ] Batch note writing
- [ ] Calendar integration
- [ ] Email template generation
- [ ] Scheduled analysis
- [ ] Slack notifications
- [ ] Dashboard/web UI
