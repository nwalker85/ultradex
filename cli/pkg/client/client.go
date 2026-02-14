package client

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"time"
)

type Client struct {
	baseURL string
	client  *http.Client
}

type Contact struct {
	ID                string     `json:"id"`
	Name              string     `json:"name"`
	Email             *string    `json:"email"`
	Company           *string    `json:"company"`
	JobTitle          *string    `json:"job_title"`
	Phone             *string    `json:"phone"`
	Notes             *string    `json:"notes"`
	LastContacted     *time.Time `json:"last_contacted"`
	AIValue           *float64   `json:"ai_value"`
	AIReason          *string    `json:"ai_reason"`
	OutreachStrategy  *string    `json:"outreach_strategy"`
	SuggestedTiming   *string    `json:"suggested_timing"`
	LastAnalyzed      *time.Time `json:"last_analyzed"`
}

type SyncResult struct {
	Status         string    `json:"status"`
	ContactsSynced int       `json:"contacts_synced"`
	Timestamp      time.Time `json:"timestamp"`
}

type AnalysisResult struct {
	Status    string    `json:"status"`
	Analyzed  int       `json:"analyzed"`
	Neglected int       `json:"neglected"`
	Tokens    int       `json:"tokens"`
	Cost      float64   `json:"cost"`
	Timestamp time.Time `json:"timestamp"`
}

type AnalysisRun struct {
	ID                      string    `json:"id"`
	Timestamp               time.Time `json:"timestamp"`
	ContactsAnalyzed        int       `json:"contacts_analyzed"`
	NeglectedContactsFound  int       `json:"neglected_contacts_found"`
	EstimatedTokens         int       `json:"estimated_tokens"`
	EstimatedCost           float64   `json:"estimated_cost"`
	Success                 int       `json:"success"`
	ErrorMessage            *string   `json:"error_message"`
}

type Stats struct {
	TotalRuns              int     `json:"total_runs"`
	TotalContactsAnalyzed  int     `json:"total_contacts_analyzed"`
	TotalNeglectedFound    int     `json:"total_neglected_found"`
	TotalCost              float64 `json:"total_cost"`
	AverageCostPerRun      float64 `json:"average_cost_per_run"`
	Timestamp              time.Time `json:"timestamp"`
}

type HealthCheck struct {
	Status    string    `json:"status"`
	Timestamp time.Time `json:"timestamp"`
}

func NewClient(baseURL string) *Client {
	return &Client{
		baseURL: baseURL,
		client: &http.Client{
			Timeout: 60 * time.Second,
		},
	}
}

func (c *Client) SyncContacts() (*SyncResult, error) {
	var result SyncResult
	err := c.post("/api/v1/contacts/sync", nil, &result)
	return &result, err
}

func (c *Client) AnalyzeContacts(limit *int) (*AnalysisResult, error) {
	var result AnalysisResult
	query := ""
	if limit != nil {
		query = fmt.Sprintf("?limit=%d", *limit)
	}
	err := c.post("/api/v1/analyze"+query, nil, &result)
	return &result, err
}

func (c *Client) GetContacts() ([]Contact, error) {
	var contacts []Contact
	err := c.get("/api/v1/contacts", &contacts)
	return contacts, err
}

func (c *Client) GetContact(contactID string) (*Contact, error) {
	var contact Contact
	err := c.get(fmt.Sprintf("/api/v1/contacts/%s", contactID), &contact)
	return &contact, err
}

func (c *Client) GetNeglectedContacts() ([]Contact, error) {
	var contacts []Contact
	err := c.get("/api/v1/contacts/neglected/list", &contacts)
	return contacts, err
}

func (c *Client) WriteNote(contactID string, note string) error {
	payload := map[string]string{"content": note}
	return c.post(fmt.Sprintf("/api/v1/contacts/%s/note", contactID), payload, nil)
}

func (c *Client) GetAnalysisStats() (*Stats, error) {
	var stats Stats
	err := c.get("/api/v1/stats", &stats)
	return &stats, err
}

func (c *Client) GetAnalysisRuns(limit int) ([]AnalysisRun, error) {
	var runs []AnalysisRun
	err := c.get(fmt.Sprintf("/api/v1/analyze/runs?limit=%d", limit), &runs)
	return runs, err
}

func (c *Client) HealthCheck() (*HealthCheck, error) {
	var health HealthCheck
	err := c.get("/health", &health)
	return &health, err
}

func (c *Client) get(path string, result interface{}) error {
	resp, err := c.client.Get(c.baseURL + path)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	return c.parseResponse(resp, result)
}

func (c *Client) post(path string, payload interface{}, result interface{}) error {
	var body io.Reader
	if payload != nil {
		jsonData, err := json.Marshal(payload)
		if err != nil {
			return fmt.Errorf("failed to marshal payload: %w", err)
		}
		body = bytes.NewReader(jsonData)
	}

	req, err := http.NewRequest("POST", c.baseURL+path, body)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	return c.parseResponse(resp, result)
}

func (c *Client) parseResponse(resp *http.Response, result interface{}) error {
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		body, _ := io.ReadAll(resp.Body)
		return fmt.Errorf("API error (%d): %s", resp.StatusCode, string(body))
	}

	if result != nil {
		return json.NewDecoder(resp.Body).Decode(result)
	}
	return nil
}
