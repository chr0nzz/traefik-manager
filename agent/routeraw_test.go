package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

const routeOnlyYAML = `http:
  routers:
    plex-rtr:
      rule: "Host(` + "`plex.example.com`" + `)"
      middlewares:
        - chain-no-auth@file
      service: plex-svc
      tls:
        options: tls-opts
  services:
    plex-svc:
      loadBalancer:
        servers:
          - url: "http://10.0.0.5:32400"
        serversTransport: plex-transport
`

const sharedYAML = `http:
  middlewares:
    chain-no-auth:
      chain:
        middlewares: [sec-headers]
  serversTransports:
    plex-transport:
      forwardingTimeouts:
        dialTimeout: 30s
tls:
  options:
    tls-opts:
      minVersion: VersionTLS12
`

func splitConfigApp(t *testing.T) (*App, string, string) {
	t.Helper()
	dir := t.TempDir()
	own := filepath.Join(dir, "dynamic.yml")
	shared := filepath.Join(dir, "shared.yml")
	if err := os.WriteFile(own, []byte(routeOnlyYAML), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(shared, []byte(sharedYAML), 0o644); err != nil {
		t.Fatal(err)
	}
	return &App{cfg: &Config{ConfigPath: dir, BackupDir: t.TempDir()}}, own, shared
}

func rawGet(t *testing.T, a *App) map[string]any {
	t.Helper()
	rec := httptest.NewRecorder()
	a.routeRawGetHandler(rec, httptest.NewRequest(http.MethodGet, "/api/routes/plex-rtr/raw", nil),
		"plex-rtr")
	if rec.Code != http.StatusOK {
		t.Fatalf("GET returned %d: %s", rec.Code, rec.Body.String())
	}
	var body map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &body); err != nil {
		t.Fatal(err)
	}
	return body
}

func rawSave(t *testing.T, a *App, payload map[string]any) (int, map[string]any) {
	t.Helper()
	encoded, err := json.Marshal(payload)
	if err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(http.MethodPost, "/api/routes/plex-rtr/raw", strings.NewReader(string(encoded)))
	rec := httptest.NewRecorder()
	a.routeRawSaveHandler(rec, req, "plex-rtr")
	var body map[string]any
	json.Unmarshal(rec.Body.Bytes(), &body)
	return rec.Code, body
}

func originOf(t *testing.T, body map[string]any, scope, kind, name string) string {
	t.Helper()
	origins, _ := body["origins"].(map[string]any)
	scoped, _ := origins[scope].(map[string]any)
	kinds, _ := scoped[kind].(map[string]any)
	where, _ := kinds[name].(string)
	return where
}

func TestAgentRawCarriesDependenciesAndNamesTheirFile(t *testing.T) {
	a, _, _ := splitConfigApp(t)
	body := rawGet(t, a)
	raw, _ := body["raw"].(string)
	for _, want := range []string{"chain-no-auth", "dialTimeout", "VersionTLS12"} {
		if !strings.Contains(raw, want) {
			t.Errorf("raw YAML is missing %q:\n%s", want, raw)
		}
	}
	if got := originOf(t, body, "http", "middlewares", "chain-no-auth"); got != "shared.yml" {
		t.Errorf("middleware origin = %q, want shared.yml", got)
	}
	if got := originOf(t, body, "tls", "options", "tls-opts"); got != "shared.yml" {
		t.Errorf("tls origin = %q, want shared.yml", got)
	}
}

func TestAgentUntouchedSharedDefinitionIsNotCopiedIn(t *testing.T) {
	a, own, _ := splitConfigApp(t)
	code, _ := rawSave(t, a, map[string]any{"content": rawGet(t, a)["raw"]})
	if code != http.StatusOK {
		t.Fatalf("save returned %d", code)
	}
	after, _ := os.ReadFile(own)
	if strings.Contains(string(after), "chain-no-auth:") {
		t.Errorf("the shared middleware was duplicated into the route file:\n%s", after)
	}
}

func TestAgentChangedSharedDefinitionAsksFirst(t *testing.T) {
	a, _, shared := splitConfigApp(t)
	raw := strings.Replace(rawGet(t, a)["raw"].(string), "30s", "99s", 1)
	code, body := rawSave(t, a, map[string]any{"content": raw})
	if code != http.StatusConflict {
		t.Fatalf("save returned %d, want 409", code)
	}
	if body["needsConfirm"] != true {
		t.Errorf("body = %v, want needsConfirm", body)
	}
	changes, _ := body["sharedChanges"].([]any)
	if len(changes) != 1 {
		t.Fatalf("sharedChanges = %v", changes)
	}
	first, _ := changes[0].(map[string]any)
	if first["file"] != "shared.yml" || first["name"] != "plex-transport" {
		t.Errorf("change = %v", first)
	}
	after, _ := os.ReadFile(shared)
	if !strings.Contains(string(after), "30s") {
		t.Errorf("shared file was written before the confirm:\n%s", after)
	}
}

func TestAgentConfirmedSaveWritesTheOwningFile(t *testing.T) {
	a, own, shared := splitConfigApp(t)
	raw := strings.Replace(rawGet(t, a)["raw"].(string), "30s", "99s", 1)
	code, body := rawSave(t, a, map[string]any{"content": raw, "applyShared": true})
	if code != http.StatusOK {
		t.Fatalf("save returned %d: %v", code, body)
	}
	if after, _ := os.ReadFile(shared); !strings.Contains(string(after), "99s") {
		t.Errorf("the edit did not reach shared.yml:\n%s", after)
	}
	if after, _ := os.ReadFile(own); strings.Contains(string(after), "dialTimeout") {
		t.Errorf("the transport was duplicated into the route file:\n%s", after)
	}
}

func TestAgentReadOnlySharedFileIsRefused(t *testing.T) {
	a, own, shared := splitConfigApp(t)
	before, _ := os.ReadFile(own)
	if err := os.Chmod(shared, 0o444); err != nil {
		t.Fatal(err)
	}
	defer os.Chmod(shared, 0o644)
	raw := strings.Replace(rawGet(t, a)["raw"].(string), "30s", "99s", 1)
	code, body := rawSave(t, a, map[string]any{"content": raw, "applyShared": true})
	if code != http.StatusConflict || body["code"] != "shared_definition_read_only" {
		t.Fatalf("save returned %d %v", code, body)
	}
	if after, _ := os.ReadFile(own); string(after) != string(before) {
		t.Errorf("the route file was written despite the refusal")
	}
}

func TestAgentStaleSharedFileAbortsTheSave(t *testing.T) {
	a, _, shared := splitConfigApp(t)
	body := rawGet(t, a)
	raw := strings.Replace(body["raw"].(string), "30s", "99s", 1)
	if err := os.WriteFile(shared, []byte(strings.Replace(sharedYAML, "30s", "31s", 1)), 0o644); err != nil {
		t.Fatal(err)
	}
	code, reply := rawSave(t, a, map[string]any{
		"content": raw, "applyShared": true, "fingerprints": body["fingerprints"],
	})
	if code != http.StatusConflict || reply["code"] != "shared_file_changed" {
		t.Fatalf("save returned %d %v", code, reply)
	}
	if after, _ := os.ReadFile(shared); !strings.Contains(string(after), "31s") {
		t.Errorf("the file that moved underneath was overwritten:\n%s", after)
	}
}

func TestAgentRenamingASharedDefinitionIsRefused(t *testing.T) {
	a, own, shared := splitConfigApp(t)
	raw := strings.Replace(rawGet(t, a)["raw"].(string), "plex-transport:", "plex-transport-x:", 1)
	code, body := rawSave(t, a, map[string]any{"content": raw, "applyShared": true})
	if code != http.StatusConflict || body["code"] != "shared_definition_renamed" {
		t.Fatalf("save returned %d %v", code, body)
	}
	if after, _ := os.ReadFile(own); strings.Contains(string(after), "plex-transport-x") {
		t.Errorf("a renamed orphan was created:\n%s", after)
	}
	if after, _ := os.ReadFile(shared); !strings.Contains(string(after), "plex-transport:") {
		t.Errorf("the original definition lost its name:\n%s", after)
	}
}

func TestAgentBlastRadiusCountsEveryRouteThatShares(t *testing.T) {
	a, own, _ := splitConfigApp(t)
	extra := strings.Replace(routeOnlyYAML, "  services:",
		"    sonarr-rtr:\n      rule: \"Host(`sonarr.example.com`)\"\n      service: plex-svc\n  services:", 1)
	if err := os.WriteFile(own, []byte(extra), 0o644); err != nil {
		t.Fatal(err)
	}
	raw := strings.Replace(rawGet(t, a)["raw"].(string), "30s", "99s", 1)
	_, body := rawSave(t, a, map[string]any{"content": raw})
	changes, _ := body["sharedChanges"].([]any)
	first, _ := changes[0].(map[string]any)
	used, _ := first["usedBy"].(map[string]any)
	if used["count"] != float64(2) {
		t.Errorf("usedBy = %v, want 2 routes", used)
	}
}

func TestAgentSameFileDefinitionsStillSaveWithTheRoute(t *testing.T) {
	dir := t.TempDir()
	own := filepath.Join(dir, "dynamic.yml")
	if err := os.WriteFile(own, []byte(routeOnlyYAML+strings.TrimPrefix(sharedYAML, "http:\n")), 0o644); err != nil {
		t.Fatal(err)
	}
	a := &App{cfg: &Config{ConfigPath: dir, BackupDir: t.TempDir()}}
	raw := strings.Replace(rawGet(t, a)["raw"].(string), "30s", "99s", 1)
	code, body := rawSave(t, a, map[string]any{"content": raw})
	if code != http.StatusOK {
		t.Fatalf("save returned %d: %v", code, body)
	}
	after, _ := os.ReadFile(own)
	if !strings.Contains(string(after), "99s") {
		t.Errorf("a definition in the route's own file must save with it:\n%s", after)
	}
}

func TestAgentMissingMiddlewareBlocksTheSave(t *testing.T) {
	a, own, _ := splitConfigApp(t)
	before, _ := os.ReadFile(own)
	raw := strings.Replace(rawGet(t, a)["raw"].(string), "chain-no-auth@file", "chain-no-auths@file", 1)
	code, body := rawSave(t, a, map[string]any{"content": raw, "applyShared": true})
	if code != http.StatusConflict || body["code"] != "middleware_not_defined" {
		t.Fatalf("save returned %d %v", code, body)
	}
	if after, _ := os.ReadFile(own); string(after) != string(before) {
		t.Errorf("a route with a broken reference was written anyway")
	}
}

func TestAgentMissingServiceAndTransportBlockTheSave(t *testing.T) {
	for _, tc := range []struct{ from, to, code string }{
		{"service: plex-svc", "service: gone-svc", "service_not_defined"},
		{"serversTransport: plex-transport", "serversTransport: gone-tr", "transport_not_defined"},
		{"options: tls-opts", "options: gone-opts", "tls_options_not_defined"},
	} {
		a, _, _ := splitConfigApp(t)
		raw := strings.Replace(rawGet(t, a)["raw"].(string), tc.from, tc.to, 1)
		code, body := rawSave(t, a, map[string]any{"content": raw, "applyShared": true})
		if code != http.StatusConflict || body["code"] != tc.code {
			t.Errorf("%s: returned %d %v", tc.from, code, body)
		}
	}
}

func TestAgentAnotherProviderAndDefaultTLSAreNotMissing(t *testing.T) {
	a, _, _ := splitConfigApp(t)
	raw := strings.Replace(rawGet(t, a)["raw"].(string), "chain-no-auth@file", "crowdsec@docker", 1)
	raw = strings.Replace(raw, "options: tls-opts", "options: default", 1)
	code, body := rawSave(t, a, map[string]any{"content": raw, "applyShared": true})
	if code != http.StatusOK {
		t.Fatalf("save returned %d %v", code, body)
	}
}
