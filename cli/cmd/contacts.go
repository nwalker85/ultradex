package cmd

import (
	"fmt"
	"strings"
	"text/tabwriter"

	"github.com/ravenhelm/ultradex-cli/pkg/client"
	"github.com/spf13/cobra"
)

var contactsCmd = &cobra.Command{
	Use:   "contacts",
	Short: "Manage and view contacts",
	Long:  `View cached contacts and their AI analysis results.`,
}

var contactsListCmd = &cobra.Command{
	Use:   "list",
	Short: "List all cached contacts",
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.NewClient(apiURL)

		fmt.Printf("Fetching contacts...\n\n")

		contacts, err := c.GetContacts()
		if err != nil {
			return fmt.Errorf("failed to get contacts: %w", err)
		}

		if len(contacts) == 0 {
			fmt.Printf("No contacts found. Run 'ultradex sync' first.\n")
			return nil
		}

		w := tabwriter.NewWriter(nil, 0, 0, 2, ' ', 0)
		w.SetOutput(cmd.OutOrStdout())

		fmt.Fprintln(w, "NAME\tCOMPANY\tJOB TITLE\tVALUE\tLAST ANALYZED")
		fmt.Fprintln(w, strings.Repeat("-", 100))

		for _, contact := range contacts {
			value := "-"
			if contact.AIValue != nil {
				value = fmt.Sprintf("%.0f", *contact.AIValue)
			}
			company := "-"
			if contact.Company != nil {
				company = *contact.Company
			}
			jobTitle := "-"
			if contact.JobTitle != nil {
				jobTitle = *contact.JobTitle
			}
			lastAnalyzed := "-"
			if contact.LastAnalyzed != nil {
				lastAnalyzed = contact.LastAnalyzed.Format("2006-01-02")
			}

			fmt.Fprintf(w, "%s\t%s\t%s\t%s\t%s\n", contact.Name, company, jobTitle, value, lastAnalyzed)
		}

		w.Flush()
		fmt.Printf("\nTotal: %d contacts\n", len(contacts))

		return nil
	},
}

var contactsNeglectedCmd = &cobra.Command{
	Use:   "neglected",
	Short: "List neglected high-value contacts",
	Long: `Show high-value contacts that haven't been contacted recently.

Criteria: value ≥60 and days since contact ≥30`,
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.NewClient(apiURL)

		fmt.Printf("Fetching neglected contacts...\n\n")

		contacts, err := c.GetNeglectedContacts()
		if err != nil {
			return fmt.Errorf("failed to get neglected contacts: %w", err)
		}

		if len(contacts) == 0 {
			fmt.Printf("✓ No neglected contacts! You're staying on top of your relationships.\n")
			return nil
		}

		w := tabwriter.NewWriter(nil, 0, 0, 2, ' ', 0)
		w.SetOutput(cmd.OutOrStdout())

		fmt.Fprintln(w, "NAME\tCOMPANY\tVALUE\tDAYS AGO\tRECOMMENDED ACTION")
		fmt.Fprintln(w, strings.Repeat("-", 120))

		for _, contact := range contacts {
			value := "-"
			if contact.AIValue != nil {
				value = fmt.Sprintf("%.0f", *contact.AIValue)
			}
			company := "-"
			if contact.Company != nil {
				company = *contact.Company
			}
			daysAgo := "-"
			if contact.LastContacted != nil {
				now := contact.LastAnalyzed
				if now != nil {
					days := int(now.Sub(*contact.LastContacted).Hours() / 24)
					daysAgo = fmt.Sprintf("%d", days)
				}
			}
			timing := "-"
			if contact.SuggestedTiming != nil {
				timing = *contact.SuggestedTiming
			}

			fmt.Fprintf(w, "%s\t%s\t%s\t%s\t%s\n", contact.Name, company, value, daysAgo, timing)
		}

		w.Flush()
		fmt.Printf("\nNeglected: %d high-value contacts need attention\n", len(contacts))

		return nil
	},
}

var contactsDetailCmd = &cobra.Command{
	Use:   "view [contact-id]",
	Short: "View details of a specific contact",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		c := client.NewClient(apiURL)

		contactID := args[0]
		fmt.Printf("Fetching contact details for %s...\n\n", contactID)

		contact, err := c.GetContact(contactID)
		if err != nil {
			return fmt.Errorf("failed to get contact: %w", err)
		}

		fmt.Printf("=== Contact Details ===\n")
		fmt.Printf("Name: %s\n", contact.Name)
		if contact.Email != nil {
			fmt.Printf("Email: %s\n", *contact.Email)
		}
		if contact.Company != nil {
			fmt.Printf("Company: %s\n", *contact.Company)
		}
		if contact.JobTitle != nil {
			fmt.Printf("Job Title: %s\n", *contact.JobTitle)
		}
		if contact.Phone != nil {
			fmt.Printf("Phone: %s\n", *contact.Phone)
		}

		fmt.Printf("\n=== AI Analysis ===\n")
		if contact.AIValue != nil {
			fmt.Printf("Value Score: %.0f/100\n", *contact.AIValue)
		}
		if contact.AIReason != nil {
			fmt.Printf("Reason: %s\n", *contact.AIReason)
		}
		if contact.OutreachStrategy != nil {
			fmt.Printf("Outreach Strategy: %s\n", *contact.OutreachStrategy)
		}
		if contact.SuggestedTiming != nil {
			fmt.Printf("Suggested Timing: %s\n", *contact.SuggestedTiming)
		}

		if contact.Notes != nil {
			fmt.Printf("\n=== Notes ===\n%s\n", *contact.Notes)
		}

		return nil
	},
}

func init() {
	contactsCmd.AddCommand(contactsListCmd)
	contactsCmd.AddCommand(contactsNeglectedCmd)
	contactsCmd.AddCommand(contactsDetailCmd)
}
