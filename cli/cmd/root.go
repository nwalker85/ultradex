package cmd

import (
	"fmt"
	"os"

	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var (
	cfgFile string
	apiURL  string
)

var rootCmd = &cobra.Command{
	Use:   "hrafngrima",
	Short: "CLI for Hrafngrima - AI-powered networking assistant",
	Long: `Hrafngrima CLI - Manage your professional relationships with AI.

Sync contacts from Dex, run analysis to identify neglected high-value relationships,
and get AI-generated outreach strategies.`,
	Version: "1.0.0",
}

func Execute() error {
	return rootCmd.Execute()
}

func init() {
	cobra.OnInitialize(initConfig)

	rootCmd.PersistentFlags().StringVar(&cfgFile, "config", "", "config file (default is $HOME/.hrafngrima/config.yaml)")
	rootCmd.PersistentFlags().StringVar(&apiURL, "api", "http://localhost:8000", "Hrafngrima API URL")

	rootCmd.AddCommand(syncCmd)
	rootCmd.AddCommand(analyzeCmd)
	rootCmd.AddCommand(contactsCmd)
	rootCmd.AddCommand(statsCmd)
	rootCmd.AddCommand(healthCmd)
	rootCmd.AddCommand(configCmd)
}

func initConfig() {
	if cfgFile != "" {
		viper.SetConfigFile(cfgFile)
	} else {
		home, err := os.UserHomeDir()
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error getting home directory: %v\n", err)
			return
		}
		viper.AddConfigPath(home + "/.hrafngrima")
		viper.SetConfigType("yaml")
		viper.SetConfigName("config")
	}

	viper.SetEnvPrefix("HRAFNGRIMA")
	viper.AutomaticEnv()

	// Set defaults
	viper.SetDefault("api", "http://localhost:8000")
	viper.SetDefault("output", "table")
	viper.SetDefault("timeout", 60)

	// Try to read config, but don't fail if it doesn't exist
	_ = viper.ReadInConfig()
}
