package cmd

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var configCmd = &cobra.Command{
	Use:   "config",
	Short: "Manage CLI configuration",
}

var configSetCmd = &cobra.Command{
	Use:   "set [key] [value]",
	Short: "Set a configuration value",
	Args:  cobra.ExactArgs(2),
	RunE: func(cmd *cobra.Command, args []string) error {
		key := args[0]
		value := args[1]

		home, err := os.UserHomeDir()
		if err != nil {
			return fmt.Errorf("failed to get home directory: %w", err)
		}

		configDir := filepath.Join(home, ".hrafngrima")
		configFile := filepath.Join(configDir, "config.yaml")

		// Create config directory if it doesn't exist
		if err := os.MkdirAll(configDir, 0700); err != nil {
			return fmt.Errorf("failed to create config directory: %w", err)
		}

		viper.Set(key, value)
		if err := viper.WriteConfigAs(configFile); err != nil {
			return fmt.Errorf("failed to write config: %w", err)
		}

		fmt.Printf("✓ Configuration updated: %s = %s\n", key, value)
		fmt.Printf("  Config file: %s\n", configFile)

		return nil
	},
}

var configGetCmd = &cobra.Command{
	Use:   "get [key]",
	Short: "Get a configuration value",
	Args:  cobra.ExactArgs(1),
	RunE: func(cmd *cobra.Command, args []string) error {
		key := args[0]
		value := viper.Get(key)

		if value == nil {
			fmt.Printf("Configuration key '%s' not set\n", key)
			return nil
		}

		fmt.Printf("%s = %v\n", key, value)
		return nil
	},
}

var configShowCmd = &cobra.Command{
	Use:   "show",
	Short: "Show all configuration",
	RunE: func(cmd *cobra.Command, args []string) error {
		home, _ := os.UserHomeDir()
		configFile := filepath.Join(home, ".hrafngrima", "config.yaml")

		fmt.Printf("=== Configuration ===\n")
		fmt.Printf("API URL: %s\n", viper.GetString("api"))
		fmt.Printf("Output Format: %s\n", viper.GetString("output"))
		fmt.Printf("Timeout: %d seconds\n", viper.GetInt("timeout"))

		fmt.Printf("\nConfig file: %s\n", configFile)

		// Check if file exists
		if _, err := os.Stat(configFile); os.IsNotExist(err) {
			fmt.Printf("(Using defaults - no config file yet)\n")
		}

		return nil
	},
}

var configResetCmd = &cobra.Command{
	Use:   "reset",
	Short: "Reset configuration to defaults",
	RunE: func(cmd *cobra.Command, args []string) error {
		home, err := os.UserHomeDir()
		if err != nil {
			return fmt.Errorf("failed to get home directory: %w", err)
		}

		configFile := filepath.Join(home, ".hrafngrima", "config.yaml")

		if err := os.Remove(configFile); err != nil && !os.IsNotExist(err) {
			return fmt.Errorf("failed to remove config file: %w", err)
		}

		fmt.Printf("✓ Configuration reset to defaults\n")
		fmt.Printf("  - API URL: http://localhost:8000\n")
		fmt.Printf("  - Output: table\n")
		fmt.Printf("  - Timeout: 60 seconds\n")

		return nil
	},
}

func init() {
	configCmd.AddCommand(configSetCmd)
	configCmd.AddCommand(configGetCmd)
	configCmd.AddCommand(configShowCmd)
	configCmd.AddCommand(configResetCmd)
}
