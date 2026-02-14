package cmd

import (
	"fmt"

	"github.com/ravenhelm/hrafngrima-cli/pkg/client"
	"github.com/spf13/cobra"
)

var analyzeCmd = &cobra.Command{
	Use:   "analyze",
	Short: "Run AI analysis on contacts",
	Long: `Run AI analysis to identify high-value relationships and generate outreach strategies.

Claude analyzes each contact to:
- Score their networking value (0-100)
- Identify neglected high-value relationships (value ≥60, days ≥30)
- Generate personalized outreach strategies
- Suggest timing for reaching out

Use --limit to analyze only N contacts instead of all.`,
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.NewClient(apiURL)

		limit, _ := cmd.Flags().GetInt("limit")
		var limitPtr *int
		if limit > 0 {
			limitPtr = &limit
		}

		fmt.Printf("Running analysis...")
		if limitPtr != nil {
			fmt.Printf(" (limit: %d contacts)\n", *limitPtr)
		} else {
			fmt.Printf("\n")
		}

		result, err := c.AnalyzeContacts(limitPtr)
		if err != nil {
			return fmt.Errorf("failed to run analysis: %w", err)
		}

		fmt.Printf("✓ Analysis complete\n")
		fmt.Printf("  Analyzed: %d contacts\n", result.Analyzed)
		fmt.Printf("  Neglected found: %d\n", result.Neglected)
		fmt.Printf("  Tokens used: %d (~$%.2f)\n", result.Tokens, result.Cost)
		fmt.Printf("  Timestamp: %s\n", result.Timestamp.Format("2006-01-02 15:04:05"))

		if result.Neglected > 0 {
			fmt.Printf("\n⚠ Found %d neglected high-value contacts. Use 'hrafngrima contacts neglected' to see them.\n", result.Neglected)
		}

		return nil
	},
}

func init() {
	analyzeCmd.Flags().IntP("limit", "l", 0, "Maximum number of contacts to analyze (0 = all)")
}
