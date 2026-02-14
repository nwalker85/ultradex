package cmd

import (
	"fmt"

	"github.com/ravenhelm/hrafngrima-cli/pkg/client"
	"github.com/spf13/cobra"
)

var statsCmd = &cobra.Command{
	Use:   "stats",
	Short: "View analysis statistics and cost tracking",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.NewClient(apiURL)

		fmt.Printf("Fetching analysis statistics...\n\n")

		stats, err := c.GetAnalysisStats()
		if err != nil {
			return fmt.Errorf("failed to get stats: %w", err)
		}

		fmt.Printf("=== Analysis Statistics ===\n")
		fmt.Printf("Total Analysis Runs: %d\n", stats.TotalRuns)
		fmt.Printf("Total Contacts Analyzed: %d\n", stats.TotalContactsAnalyzed)
		fmt.Printf("Total Neglected Found: %d\n", stats.TotalNeglectedFound)

		fmt.Printf("\n=== Cost Tracking ===\n")
		fmt.Printf("Total Cost: $%.2f\n", stats.TotalCost)
		fmt.Printf("Average Cost Per Run: $%.2f\n", stats.AverageCostPerRun)
		fmt.Printf("Estimated Monthly Cost: $%.2f\n", stats.AverageCostPerRun*4.3) // ~4.3 weeks per month

		fmt.Printf("\nLast Updated: %s\n", stats.Timestamp.Format("2006-01-02 15:04:05"))

		// Show analysis history
		fmt.Printf("\n=== Recent Analysis Runs ===\n")
		runs, err := c.GetAnalysisRuns(5)
		if err != nil {
			fmt.Printf("(Could not fetch run history)\n")
		} else {
			for i, run := range runs {
				status := "✓"
				if run.Success == 0 {
					status = "✗"
				}
				fmt.Printf("%d. %s [%s] %d analyzed, %d neglected ($%.2f)\n",
					i+1,
					run.Timestamp.Format("2006-01-02 15:04"),
					status,
					run.ContactsAnalyzed,
					run.NeglectedContactsFound,
					run.EstimatedCost,
				)
			}
		}

		return nil
	},
}
