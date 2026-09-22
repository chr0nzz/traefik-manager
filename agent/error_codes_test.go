package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
)

func TestJSONErrorCodeKeepsTheEnglishErrorAndAddsTheCode(t *testing.T) {
	rec := httptest.NewRecorder()
	jsonErrorCode(rec, "invalid_yaml", map[string]any{"detail": "line 3"}, "invalid YAML: line 3", http.StatusBadRequest)
	if rec.Code != http.StatusBadRequest {
		t.Fatalf("status %d", rec.Code)
	}
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if body["error"] != "invalid YAML: line 3" || body["code"] != "invalid_yaml" || body["ok"] != false {
		t.Fatalf("body %v", body)
	}
	if params, _ := body["params"].(map[string]any); params["detail"] != "line 3" {
		t.Fatalf("params %v", body["params"])
	}
}

func TestJSONErrorCodeOmitsEmptyParams(t *testing.T) {
	rec := httptest.NewRecorder()
	jsonErrorCode(rec, "unauthorized", nil, "unauthorized", http.StatusUnauthorized)
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	if _, ok := body["params"]; ok {
		t.Fatalf("params should be omitted: %v", body)
	}
	if body["error"] != "unauthorized" || body["code"] != "unauthorized" {
		t.Fatalf("body %v", body)
	}
}
