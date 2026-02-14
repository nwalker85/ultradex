# Ultradex CLI Development Guide

## Setup

### Install Go

```bash
# macOS
brew install go

# Or download from https://golang.org/dl/
go version  # Should be 1.21+
```

### Clone and Build

```bash
cd ~/src/products/ultradex/cli

# Download dependencies
go mod download
go mod tidy

# Build
go build -o bin/ultradex

# Test
./bin/ultradex health
```

## Architecture

### Package Structure

```
cli/
├── main.go                    # Entry point
├── go.mod / go.sum            # Dependency management
├── Makefile                   # Build automation
├── cmd/                       # Command implementations
│   ├── root.go               # Root command, config, DI
│   ├── sync.go               # sync command
│   ├── analyze.go            # analyze command
│   ├── contacts.go           # contacts subcommands
│   ├── stats.go              # stats command
│   ├── health.go             # health command
│   └── config.go             # config subcommands
└── pkg/                       # Reusable packages
    └── client/
        └── client.go         # HTTP API client
```

### Key Design Patterns

1. **Cobra for CLI**: Command structure, flags, help
2. **Viper for Config**: Configuration file + env var management
3. **Client Package**: HTTP API abstraction

### Flow

```
main() 
  → rootCmd.Execute() (Cobra)
    → initConfig() (Viper)
    → Command.RunE()
      → client.NewClient()
        → client.GetContacts()
          → HTTP GET /api/v1/contacts
```

## Adding Commands

### 1. Create Command File

File: `cmd/mycommand.go`

```go
package cmd

import (
    "fmt"
    "github.com/ravenhelm/ultradex-cli/pkg/client"
    "github.com/spf13/cobra"
)

var mycommandCmd = &cobra.Command{
    Use:   "mycommand",
    Short: "Short description",
    Long:  `Longer description...`,
    RunE: func(cmd *cobra.Command, args []string) error {
        c := client.NewClient(apiURL)
        
        // Your implementation
        fmt.Println("Hello from mycommand")
        
        return nil
    },
}

func init() {
    // Add flags if needed
    mycommandCmd.Flags().StringP("flag-name", "f", "default", "Description")
}
```

### 2. Register Command

File: `cmd/root.go` (in init function)

```go
rootCmd.AddCommand(mycommandCmd)
```

### 3. Build and Test

```bash
make build
./bin/ultradex mycommand
```

## Adding API Endpoints

### 1. Add Client Method

File: `pkg/client/client.go`

```go
func (c *Client) MyEndpoint() (*Result, error) {
    var result Result
    err := c.get("/api/v1/my-endpoint", &result)
    return &result, err
}
```

### 2. Use in Command

```go
result, err := c.MyEndpoint()
if err != nil {
    return err
}
```

## Testing

### Unit Tests

```bash
# Create test file
touch pkg/client/client_test.go

# Write tests
go test -v ./...
```

### Integration Tests

Test against real API:

```bash
# Start API
cd ~/src/products/ultradex
docker-compose up

# In another terminal
cd cli
go run main.go health
go run main.go sync
go run main.go analyze --limit 5
```

### Manual Testing

```bash
# Build
make build

# Test all commands
./bin/ultradex health
./bin/ultradex sync
./bin/ultradex analyze
./bin/ultradex contacts list
./bin/ultradex contacts neglected
./bin/ultradex stats
./bin/ultradex config show
```

## Debugging

### Enable Verbose Output

Add to command:

```go
if verbose, _ := cmd.Flags().GetBool("verbose"); verbose {
    fmt.Printf("Debug: %+v\n", result)
}
```

### Check HTTP Traffic

Use curl directly:

```bash
curl http://localhost:8000/api/v1/contacts
```

### Log Client Calls

Add debugging to `pkg/client/client.go`:

```go
func (c *Client) get(path string, result interface{}) error {
    fmt.Printf("DEBUG: GET %s\n", c.baseURL+path)
    // ... rest of implementation
}
```

## Building Releases

### For macOS (ARM64)

```bash
GOOS=darwin GOARCH=arm64 go build -o bin/ultradex-darwin-arm64

# Sign the binary (optional)
codesign -s - bin/ultradex-darwin-arm64
```

### For Linux

```bash
GOOS=linux GOARCH=amd64 go build -o bin/ultradex-linux-amd64
```

### For Windows

```bash
GOOS=windows GOARCH=amd64 go build -o bin/ultradex.exe
```

### Create Release Archive

```bash
#!/bin/bash
VERSION=$(go run main.go --version | awk '{print $NF}')
OS=$1
ARCH=$2

GOOS=$OS GOARCH=$ARCH go build -o bin/ultradex-$VERSION-$OS-$ARCH

# Create tarball
cd bin
tar -czf ultradex-$VERSION-$OS-$ARCH.tar.gz ultradex-$VERSION-$OS-$ARCH
cd ..
```

## Code Style

### Format Code

```bash
make fmt

# Or manually
go fmt ./...
```

### Lint

```bash
# Install golangci-lint first
brew install golangci-lint

make lint
```

### Style Guidelines

- Use CamelCase for exported symbols
- Use snake_case for flags/config keys
- Keep functions small and focused
- Add error handling for all API calls
- Use context for timeouts

## Documentation

### Update Help Text

```go
var myCmd = &cobra.Command{
    Use:   "mycommand",
    Short: "One-liner",
    Long: `Detailed description
    
    Examples:
        ultradex mycommand
        ultradex mycommand --flag value`,
}
```

### Generate Documentation

```bash
# Cobra can generate markdown docs
go run main.go > ultradex.md
```

## Common Tasks

### Add a Flag

```go
myCmd.Flags().IntP("limit", "l", 10, "Limit results")
// Use it:
limit, _ := cmd.Flags().GetInt("limit")
```

### Add Subcommands

```go
// Parent command
parentCmd := &cobra.Command{
    Use: "parent",
}

// Child commands
childCmd := &cobra.Command{
    Use: "child",
}

parentCmd.AddCommand(childCmd)
rootCmd.AddCommand(parentCmd)
```

### Format Output

```go
// Table format
w := tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
fmt.Fprintln(w, "COL1\tCOL2\tCOL3")
fmt.Fprintf(w, "%v\t%v\t%v\n", val1, val2, val3)
w.Flush()

// JSON format
jsonData, _ := json.MarshalIndent(result, "", "  ")
fmt.Println(string(jsonData))
```

## Performance Tips

### Lazy Load Data

Only fetch what's needed:

```go
// Good - only get neglected
c.GetNeglectedContacts()

// Less efficient - get all then filter client-side
contacts, _ := c.GetContacts()
// filter locally
```

### Use Query Parameters

```go
// Server-side filtering
c.AnalyzeContacts(limit)

// Better than
c.AnalyzeContacts(nil) // all
// then filter client-side
```

### Connection Pooling

The httpx client in Go's http package pools connections automatically.

## Troubleshooting

### "undefined: cobra"

```bash
go get -u github.com/spf13/cobra
go mod tidy
```

### "connection refused"

API not running:

```bash
cd ~/src/products/ultradex
docker-compose up
```

### Build fails on M1 Mac

```bash
# Use native ARM64 build
GOOS=darwin GOARCH=arm64 go build -o bin/ultradex
```

### "unexpected token" in JSON

Check API response:

```bash
curl -s http://localhost:8000/api/v1/contacts | jq '.' | head -20
```

## Contributing

1. Create feature branch
2. Make changes
3. Test: `make test`
4. Format: `make fmt`
5. Build: `make build`
6. Commit and push
7. Create MR

## References

- [Cobra Documentation](https://cobra.dev/)
- [Viper Documentation](https://github.com/spf13/viper)
- [Go HTTP Client](https://golang.org/pkg/net/http/)
