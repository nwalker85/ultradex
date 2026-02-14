package cmd

import (
	"fmt"

	"github.com/ravenhelm/ultradex-cli/pkg/client"
	"github.com/spf13/cobra"
)

var syncCmd = &cobra.Command{
	Use:   "sync",
	Short: "Sync contacts from Dex to local database",
	Long: `Fetch all contacts from your Dex account and sync them to the local database.

This pulls the latest contact information and updates the local cache.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.NewClient(apiURL)

		fmt.Printf("Syncing contacts from Dex...\n")

		result, err := c.SyncContacts()
		if err != nil {
			return fmt.Errorf("failed to sync contacts: %w", err)
		}

		fmt.Printf("✓ Successfully synced %d contacts\n", result.ContactsSynced)
		fmt.Printf("  Status: %s\n", result.Status)
		fmt.Printf("  Timestamp: %s\n", result.Timestamp.Format("2006-01-02 15:04:05"))

		return nil
	},
}
