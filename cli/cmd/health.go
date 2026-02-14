package cmd

import (
	"fmt"

	"github.com/ravenhelm/hrafngrima-cli/pkg/client"
	"github.com/spf13/cobra"
)

var healthCmd = &cobra.Command{
	Use:   "health",
	Short: "Check API connectivity and service status",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.NewClient(apiURL)

		fmt.Printf("Checking Hrafngrima API at %s...\n", apiURL)

		health, err := c.HealthCheck()
		if err != nil {
			return fmt.Errorf("✗ API is unreachable: %w\n\nMake sure the Hrafngrima API is running:\n  docker-compose up", err)
		}

		fmt.Printf("✓ API is healthy\n")
		fmt.Printf("  Status: %s\n", health.Status)
		fmt.Printf("  Timestamp: %s\n", health.Timestamp.Format("2006-01-02 15:04:05"))

		return nil
	},
}
