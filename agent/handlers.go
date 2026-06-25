package main

import (
	"bytes"
	"context"
	"crypto/x509"
	"encoding/base64"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"io"
	"log"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"sync"
	"time"

	"gopkg.in/yaml.v3"
)

// ---- helpers ----------------------------------------------------------------

func jsonOK(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(v)
}

func jsonError(w http.ResponseWriter, msg string, code int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(map[string]any{"error": msg, "ok": false})
}

// ---- health -----------------------------------------------------------------

func (a *App) healthHandler(w http.ResponseWriter, r *http.Request) {
	jsonOK(w, map[string]any{"ok": true, "version": Version})
}

// ---- traefik proxy ----------------------------------------------------------

func (a *App) traefikProxy(w http.ResponseWriter, r *http.Request, traefikPath string) {
	target := strings.TrimRight(a.cfg.TraefikAPIURL, "/") + traefikPath
	ctx, cancel := context.WithTimeout(r.Context(), 12*time.Second)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, target, nil)
	if err != nil {
		jsonError(w, "proxy error: "+err.Error(), http.StatusInternalServerError)
		return
	}
	resp, err := a.httpClient.Do(req)
	if err != nil {
		jsonError(w, "traefik unavailable: "+err.Error(), http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

func (a *App) traefikFetchProto(ctx context.Context, traefikPath string) (json.RawMessage, error) {
	target := strings.TrimRight(a.cfg.TraefikAPIURL, "/") + traefikPath
	ctx2, cancel := context.WithTimeout(ctx, 12*time.Second)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx2, http.MethodGet, target, nil)
	if err != nil {
		return json.RawMessage("[]"), err
	}
	resp, err := a.httpClient.Do(req)
	if err != nil {
		return json.RawMessage("[]"), err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		return json.RawMessage("[]"), nil
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return json.RawMessage("[]"), nil
	}
	return json.RawMessage(body), nil
}

func (a *App) routersHandler(w http.ResponseWriter, r *http.Request) {
	httpR, err := a.traefikFetchProto(r.Context(), "/api/http/routers")
	if err != nil {
		jsonError(w, "traefik unavailable at "+a.cfg.TraefikAPIURL+": "+err.Error(), http.StatusBadGateway)
		return
	}
	tcpR, _ := a.traefikFetchProto(r.Context(), "/api/tcp/routers")
	udpR, _ := a.traefikFetchProto(r.Context(), "/api/udp/routers")
	jsonOK(w, map[string]json.RawMessage{"http": httpR, "tcp": tcpR, "udp": udpR})
}

func (a *App) servicesHandler(w http.ResponseWriter, r *http.Request) {
	httpS, err := a.traefikFetchProto(r.Context(), "/api/http/services")
	if err != nil {
		jsonError(w, "traefik unavailable at "+a.cfg.TraefikAPIURL+": "+err.Error(), http.StatusBadGateway)
		return
	}
	tcpS, _ := a.traefikFetchProto(r.Context(), "/api/tcp/services")
	udpS, _ := a.traefikFetchProto(r.Context(), "/api/udp/services")
	jsonOK(w, map[string]json.RawMessage{"http": httpS, "tcp": tcpS, "udp": udpS})
}

func (a *App) middlewaresHandler(w http.ResponseWriter, r *http.Request) {
	httpM, err := a.traefikFetchProto(r.Context(), "/api/http/middlewares")
	if err != nil {
		jsonError(w, "traefik unavailable at "+a.cfg.TraefikAPIURL+": "+err.Error(), http.StatusBadGateway)
		return
	}
	tcpM, _ := a.traefikFetchProto(r.Context(), "/api/tcp/middlewares")
	jsonOK(w, map[string]json.RawMessage{"http": httpM, "tcp": tcpM})
}

// ---- config files -----------------------------------------------------------

type fileEntry struct {
	Name    string `json:"name"`
	Content string `json:"content"`
}

func (a *App) configsReadHandler(w http.ResponseWriter, r *http.Request) {
	cfgPath := a.cfg.ConfigPath
	info, err := os.Stat(cfgPath)
	if err != nil {
		jsonError(w, "config path not found", http.StatusNotFound)
		return
	}
	files := []fileEntry{}
	if info.IsDir() {
		entries, err := os.ReadDir(cfgPath)
		if err != nil {
			jsonError(w, "cannot read config dir", http.StatusInternalServerError)
			return
		}
		for _, e := range entries {
			name := e.Name()
			if e.IsDir() || (!strings.HasSuffix(name, ".yml") && !strings.HasSuffix(name, ".yaml")) {
				continue
			}
			data, err := os.ReadFile(filepath.Join(cfgPath, name))
			if err == nil {
				files = append(files, fileEntry{Name: name, Content: string(data)})
			}
		}
	} else {
		data, err := os.ReadFile(cfgPath)
		if err != nil {
			jsonError(w, "cannot read config file", http.StatusInternalServerError)
			return
		}
		files = append(files, fileEntry{Name: filepath.Base(cfgPath), Content: string(data)})
	}
	jsonOK(w, map[string]any{"files": files})
}

func (a *App) configsWriteHandler(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Name    string `json:"name"`
		Content string `json:"content"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonError(w, "invalid request body", http.StatusBadRequest)
		return
	}
	cfgPath := a.cfg.ConfigPath
	info, err := os.Stat(cfgPath)
	var targetPath string
	if err == nil && info.IsDir() {
		if body.Name == "" || strings.Contains(body.Name, "/") || strings.Contains(body.Name, "..") {
			jsonError(w, "invalid file name", http.StatusBadRequest)
			return
		}
		targetPath = filepath.Join(cfgPath, body.Name)
	} else {
		targetPath = cfgPath
	}
	if err := a.createFileBak(targetPath, body.Name); err != nil {
		log.Printf("pre-write backup failed: %v", err)
	}
	if err := atomicWrite(targetPath, []byte(body.Content)); err != nil {
		jsonError(w, "write failed: "+err.Error(), http.StatusInternalServerError)
		return
	}
	if a.cfg.GitBackupEnabled && a.cfg.GitBackupAutoPush && a.cfg.GitBackupRepo != "" {
		go func() {
			if err := a.gitPush("config save", ""); err != nil {
				log.Printf("git auto-push failed: %v", err)
			}
		}()
	}
	jsonOK(w, map[string]any{"ok": true})
}

func atomicWrite(path string, data []byte) error {
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, data, 0o644); err != nil {
		return err
	}
	return os.Rename(tmp, path)
}

// ---- static config ----------------------------------------------------------

func (a *App) staticReadHandler(w http.ResponseWriter, r *http.Request) {
	if a.cfg.StaticConfigPath == "" {
		jsonError(w, "STATIC_CONFIG_PATH not configured", http.StatusNotFound)
		return
	}
	data, err := os.ReadFile(a.cfg.StaticConfigPath)
	if err != nil {
		jsonError(w, "cannot read static config: "+err.Error(), http.StatusInternalServerError)
		return
	}
	jsonOK(w, map[string]any{"content": string(data), "path": a.cfg.StaticConfigPath})
}

func (a *App) staticWriteHandler(w http.ResponseWriter, r *http.Request) {
	if a.cfg.StaticConfigPath == "" {
		jsonError(w, "STATIC_CONFIG_PATH not configured", http.StatusNotFound)
		return
	}
	var body struct {
		Content string `json:"content"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonError(w, "invalid request body", http.StatusBadRequest)
		return
	}
	if err := a.createFileBak(a.cfg.StaticConfigPath, ""); err != nil {
		log.Printf("pre-write static backup failed: %v", err)
	}
	if err := atomicWrite(a.cfg.StaticConfigPath, []byte(body.Content)); err != nil {
		jsonError(w, "write failed: "+err.Error(), http.StatusInternalServerError)
		return
	}
	jsonOK(w, map[string]any{"ok": true})
}

func (a *App) staticStatusHandler(w http.ResponseWriter, r *http.Request) {
	jsonOK(w, map[string]any{
		"configured":       a.cfg.StaticConfigPath != "",
		"path":             a.cfg.StaticConfigPath,
		"restart_method":   a.cfg.RestartMethod,
		"traefik_container": a.cfg.TraefikContainer,
	})
}

func (a *App) staticRestartHandler(w http.ResponseWriter, r *http.Request) {
	switch a.cfg.RestartMethod {
	case "poison-pill":
		if a.cfg.SignalFilePath == "" {
			jsonError(w, "SIGNAL_FILE_PATH not configured", http.StatusBadRequest)
			return
		}
		if err := os.WriteFile(a.cfg.SignalFilePath, []byte("restart"), 0o644); err != nil {
			jsonError(w, "failed to write signal file: "+err.Error(), http.StatusInternalServerError)
			return
		}
		jsonOK(w, map[string]any{"ok": true})

	case "socket", "proxy":
		if err := a.dockerKill(r.Context()); err != nil {
			jsonError(w, "docker restart failed: "+err.Error(), http.StatusInternalServerError)
			return
		}
		jsonOK(w, map[string]any{"ok": true})

	default:
		jsonError(w, "RESTART_METHOD not configured or unsupported", http.StatusBadRequest)
	}
}

func (a *App) dockerKill(ctx context.Context) error {
	container := a.cfg.TraefikContainer
	if container == "" {
		container = "traefik"
	}
	apiPath := "/containers/" + container + "/kill?signal=HUP"

	var client *http.Client
	var baseURL string

	dockerHost := a.cfg.DockerHost
	if a.cfg.RestartMethod == "socket" || dockerHost == "" {
		client = &http.Client{
			Transport: &http.Transport{
				DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
					return net.Dial("unix", "/var/run/docker.sock")
				},
			},
		}
		baseURL = "http://localhost"
	} else {
		client = http.DefaultClient
		baseURL = strings.TrimRight(dockerHost, "/")
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, baseURL+apiPath, nil)
	if err != nil {
		return err
	}
	resp, err := client.Do(req)
	if err != nil {
		return err
	}
	resp.Body.Close()
	if resp.StatusCode != http.StatusNoContent {
		return fmt.Errorf("docker API returned %s", resp.Status)
	}
	return nil
}

// ---- crowdsec proxy ---------------------------------------------------------

var (
	csJWT       string
	csJWTExpiry time.Time
	csJWTMu     sync.Mutex
)

func (a *App) csGetJWT(ctx context.Context) (string, error) {
	csJWTMu.Lock()
	defer csJWTMu.Unlock()
	if csJWT != "" && time.Now().Before(csJWTExpiry) {
		return csJWT, nil
	}
	body, _ := json.Marshal(map[string]any{
		"machine_id": a.cfg.CrowdSecMachineID,
		"password":   a.cfg.CrowdSecMachinePassword,
		"scenarios":  []string{},
	})
	target := strings.TrimRight(a.cfg.CrowdSecLAPIURL, "/") + "/v1/watchers/login"
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, target, bytes.NewReader(body))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	var result struct {
		Token  string `json:"token"`
		Expire string `json:"expire"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil || result.Token == "" {
		return "", fmt.Errorf("CrowdSec login failed (HTTP %d)", resp.StatusCode)
	}
	csJWT = result.Token
	if exp, err := time.Parse(time.RFC3339, result.Expire); err == nil {
		csJWTExpiry = exp.Add(-2 * time.Minute)
	} else {
		csJWTExpiry = time.Now().Add(58 * time.Minute)
	}
	return csJWT, nil
}

func (a *App) csHasMachine() bool {
	return a.cfg.CrowdSecMachineID != "" && a.cfg.CrowdSecMachinePassword != ""
}

func (a *App) csRequest(ctx context.Context, method, csPath string, body io.Reader, useJWT bool) (*http.Response, error) {
	target := strings.TrimRight(a.cfg.CrowdSecLAPIURL, "/") + csPath
	req, err := http.NewRequestWithContext(ctx, method, target, body)
	if err != nil {
		return nil, err
	}
	if useJWT && a.csHasMachine() {
		token, err := a.csGetJWT(ctx)
		if err != nil {
			return nil, err
		}
		req.Header.Set("Authorization", "Bearer "+token)
	} else if a.cfg.CrowdSecAPIKey != "" {
		req.Header.Set("X-Api-Key", a.cfg.CrowdSecAPIKey)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	return http.DefaultClient.Do(req)
}

func (a *App) csPageJSON(ctx context.Context, path string, useJWT bool) ([]json.RawMessage, error) {
	resp, err := a.csRequest(ctx, http.MethodGet, path, nil, useJWT)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("LAPI %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
	}
	var result []json.RawMessage
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return nil, nil
	}
	return result, nil
}

func (a *App) crowdsecDecisionsHandler(w http.ResponseWriter, r *http.Request) {
	if a.cfg.CrowdSecLAPIURL == "" {
		jsonError(w, "CROWDSEC_LAPI_URL not configured", http.StatusNotFound)
		return
	}
	var all []json.RawMessage
	now := time.Now().UTC()
	for page := 1; page <= 10; page++ {
		chunk, err := a.csPageJSON(r.Context(), fmt.Sprintf("/v1/decisions?limit=500&page=%d", page), false)
		if err != nil {
			if page == 1 {
				jsonError(w, "crowdsec unavailable: "+err.Error(), http.StatusBadGateway)
				return
			}
			break
		}
		if len(chunk) == 0 {
			break
		}
		for _, raw := range chunk {
			var d struct {
				Until string `json:"until"`
			}
			if err := json.Unmarshal(raw, &d); err == nil && d.Until != "" {
				exp, err := time.Parse(time.RFC3339, d.Until)
				if err == nil && exp.Before(now) {
					continue
				}
			}
			all = append(all, raw)
		}
		if len(chunk) < 500 {
			break
		}
	}
	if all == nil {
		all = []json.RawMessage{}
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(all)
}

func (a *App) crowdsecAlertsHandler(w http.ResponseWriter, r *http.Request) {
	if a.cfg.CrowdSecLAPIURL == "" {
		jsonError(w, "CROWDSEC_LAPI_URL not configured", http.StatusNotFound)
		return
	}
	chunk, err := a.csPageJSON(r.Context(), "/v1/alerts?limit=200", true)
	if err != nil {
		jsonError(w, "crowdsec unavailable: "+err.Error(), http.StatusBadGateway)
		return
	}
	out := make([]json.RawMessage, 0, len(chunk))
	for _, raw := range chunk {
		var meta struct {
			Decisions []struct {
				Origin string `json:"origin"`
			} `json:"decisions"`
		}
		if json.Unmarshal(raw, &meta) == nil && len(meta.Decisions) > 0 && meta.Decisions[0].Origin == "lists" {
			continue
		}
		out = append(out, raw)
	}
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(out)
}

func (a *App) crowdsecAddDecisionHandler(w http.ResponseWriter, r *http.Request) {
	if a.cfg.CrowdSecLAPIURL == "" {
		jsonError(w, "CROWDSEC_LAPI_URL not configured", http.StatusNotFound)
		return
	}
	var body struct {
		Value    string `json:"value"`
		Type     string `json:"type"`
		Duration string `json:"duration"`
		Reason   string `json:"reason"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonError(w, "invalid request body", http.StatusBadRequest)
		return
	}
	ip := strings.TrimSpace(body.Value)
	if ip == "" {
		jsonError(w, "IP/Range is required", http.StatusBadRequest)
		return
	}
	dtype := strings.TrimSpace(body.Type)
	if dtype == "" {
		dtype = "ban"
	}
	if dtype != "ban" && dtype != "captcha" && dtype != "bypass" {
		jsonError(w, "Invalid type", http.StatusBadRequest)
		return
	}
	duration := strings.TrimSpace(body.Duration)
	if duration == "" {
		duration = "24h"
	}
	reason := strings.TrimSpace(body.Reason)
	if reason == "" {
		reason = "manual ban from Traefik Manager"
	}
	now := time.Now().UTC().Format("2006-01-02T15:04:05Z")
	payload := []map[string]any{{
		"capacity": 0,
		"decisions": []map[string]any{{
			"duration": duration, "origin": "manual", "scenario": reason,
			"scope": "Ip", "type": dtype, "value": ip, "simulated": false,
		}},
		"events": []any{}, "events_count": 1, "labels": nil, "leakspeed": "0",
		"message": reason, "scenario": reason, "scenario_hash": "", "scenario_version": "",
		"simulated": false,
		"source":   map[string]any{"ip": ip, "scope": "Ip", "value": ip},
		"start_at": now, "stop_at": now,
	}}
	buf, _ := json.Marshal(payload)
	resp, err := a.csRequest(r.Context(), http.MethodPost, "/v1/alerts", bytes.NewReader(buf), true)
	if err != nil {
		jsonError(w, "crowdsec unavailable: "+err.Error(), http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		b, _ := io.ReadAll(resp.Body)
		jsonError(w, "failed to add decision: "+strings.TrimSpace(string(b)), resp.StatusCode)
		return
	}
	jsonOK(w, map[string]any{"ok": true})
}

func (a *App) crowdsecProxy(w http.ResponseWriter, r *http.Request, method, csPath string) {
	if a.cfg.CrowdSecLAPIURL == "" {
		jsonError(w, "CROWDSEC_LAPI_URL not configured", http.StatusNotFound)
		return
	}
	resp, err := a.csRequest(r.Context(), method, csPath, r.Body, true)
	if err != nil {
		jsonError(w, "crowdsec unavailable: "+err.Error(), http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

// ---- local backups ----------------------------------------------------------

func (a *App) backupDir() string {
	return filepath.Join(a.cfg.BackupDir, "backups")
}

func (a *App) createFileBak(targetPath, name string) error {
	data, err := os.ReadFile(targetPath)
	if err != nil {
		return nil
	}
	dir := a.backupDir()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	base := name
	if base == "" {
		base = filepath.Base(targetPath)
	}
	ts := time.Now().UTC().Format("20060102_150405")
	bakName := base + "." + ts + ".bak"
	if err := os.WriteFile(filepath.Join(dir, bakName), data, 0o644); err != nil {
		return err
	}
	a.pruneBackups(base)
	return nil
}

func (a *App) pruneBackups(base string) {
	keep := a.cfg.BackupKeepCount
	if keep <= 0 {
		return
	}
	dir := a.backupDir()
	entries, err := os.ReadDir(dir)
	if err != nil {
		return
	}
	prefix := base + "."
	var matches []string
	for _, e := range entries {
		n := e.Name()
		if !e.IsDir() && strings.HasPrefix(n, prefix) && strings.HasSuffix(n, ".bak") {
			matches = append(matches, n)
		}
	}
	if len(matches) <= keep {
		return
	}
	sort.Sort(sort.Reverse(sort.StringSlice(matches)))
	for _, n := range matches[keep:] {
		os.Remove(filepath.Join(dir, n))
	}
}

func (a *App) backupsListHandler(w http.ResponseWriter, r *http.Request) {
	dir := a.backupDir()
	entries, err := os.ReadDir(dir)
	if err != nil {
		jsonOK(w, map[string]any{"backups": []any{}})
		return
	}
	type backup struct {
		Name string `json:"name"`
		Size int64  `json:"size"`
		Date string `json:"date"`
	}
	var list []backup
	for _, e := range entries {
		n := e.Name()
		if !strings.HasSuffix(n, ".bak") {
			continue
		}
		info, _ := e.Info()
		size := int64(0)
		date := ""
		if info != nil {
			size = info.Size()
			date = info.ModTime().UTC().Format(time.RFC3339)
		}
		list = append(list, backup{Name: n, Size: size, Date: date})
	}
	jsonOK(w, map[string]any{"backups": list})
}

func (a *App) backupCreateHandler(w http.ResponseWriter, r *http.Request) {
	names, err := a.createBackup()
	if err != nil {
		jsonError(w, "backup failed: "+err.Error(), http.StatusInternalServerError)
		return
	}
	last := ""
	if len(names) > 0 {
		last = names[len(names)-1]
	}
	jsonOK(w, map[string]any{"ok": true, "name": last, "count": len(names)})
}

func (a *App) createBackup() ([]string, error) {
	dir := a.backupDir()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return nil, err
	}
	ts := time.Now().UTC().Format("20060102_150405")
	var names []string
	bakFile := func(src, base string) {
		data, err := os.ReadFile(src)
		if err != nil {
			return
		}
		name := base + "." + ts + ".bak"
		if err := os.WriteFile(filepath.Join(dir, name), data, 0o644); err == nil {
			names = append(names, name)
			a.pruneBackups(base)
		}
	}
	cfgPath := a.cfg.ConfigPath
	info, err := os.Stat(cfgPath)
	if err == nil {
		if info.IsDir() {
			entries, _ := os.ReadDir(cfgPath)
			for _, e := range entries {
				if !e.IsDir() && (strings.HasSuffix(e.Name(), ".yml") || strings.HasSuffix(e.Name(), ".yaml")) {
					bakFile(filepath.Join(cfgPath, e.Name()), e.Name())
				}
			}
		} else {
			bakFile(cfgPath, filepath.Base(cfgPath))
		}
	}
	if a.cfg.StaticConfigPath != "" {
		bakFile(a.cfg.StaticConfigPath, filepath.Base(a.cfg.StaticConfigPath))
	}
	return names, nil
}

func (a *App) restoreHandler(w http.ResponseWriter, r *http.Request) {
	filename := strings.TrimPrefix(r.URL.Path, "/api/restore/")
	if strings.Contains(filename, "/") || strings.Contains(filename, "..") || !strings.HasSuffix(filename, ".bak") {
		jsonError(w, "invalid filename", http.StatusBadRequest)
		return
	}
	bakPath := filepath.Join(a.backupDir(), filename)
	data, err := os.ReadFile(bakPath)
	if err != nil {
		jsonError(w, "cannot read backup: "+err.Error(), http.StatusNotFound)
		return
	}
	origName := strings.TrimSuffix(filename, ".bak")
	if idx := strings.LastIndex(origName, "."); idx >= 0 {
		candidate := origName[:idx]
		if len(origName)-idx == 16 {
			origName = candidate
		}
	}
	cfgPath := a.cfg.ConfigPath
	info, _ := os.Stat(cfgPath)
	var dest string
	if info != nil && info.IsDir() {
		dest = filepath.Join(cfgPath, origName)
	} else {
		dest = cfgPath
	}
	if err := atomicWrite(dest, data); err != nil {
		jsonError(w, "restore failed: "+err.Error(), http.StatusInternalServerError)
		return
	}
	jsonOK(w, map[string]any{"ok": true})
}

func (a *App) backupDeleteHandler(w http.ResponseWriter, r *http.Request) {
	filename := strings.TrimPrefix(r.URL.Path, "/api/backup/delete/")
	if strings.Contains(filename, "/") || strings.Contains(filename, "..") || !strings.HasSuffix(filename, ".bak") {
		jsonError(w, "invalid filename", http.StatusBadRequest)
		return
	}
	path := filepath.Join(a.backupDir(), filename)
	if err := os.Remove(path); err != nil {
		jsonError(w, "delete failed: "+err.Error(), http.StatusInternalServerError)
		return
	}
	jsonOK(w, map[string]any{"ok": true})
}

// ---- git backup -------------------------------------------------------------

func (a *App) gitRepoDir() string {
	return filepath.Join(a.cfg.BackupDir, "git-repo")
}

func (a *App) gitRun(args []string, cwd string) (string, string, int) {
	cmd := exec.Command("git", args...)
	if cwd == "" {
		cwd = a.gitRepoDir()
	}
	cmd.Dir = cwd
	cmd.Env = append(os.Environ(), "GIT_TERMINAL_PROMPT=0")
	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr
	err := cmd.Run()
	rc := 0
	if err != nil {
		if ex, ok := err.(*exec.ExitError); ok {
			rc = ex.ExitCode()
		} else {
			rc = 1
		}
	}
	return strings.TrimSpace(stdout.String()), strings.TrimSpace(stderr.String()), rc
}

func (a *App) gitAuthURL() string {
	repo := a.cfg.GitBackupRepo
	token := a.cfg.GitBackupToken
	if token == "" {
		return repo
	}
	u, err := url.Parse(repo)
	if err != nil {
		return repo
	}
	if a.cfg.GitBackupUsername != "" {
		u.User = url.UserPassword(a.cfg.GitBackupUsername, token)
	} else {
		u.User = url.User(token)
	}
	return u.String()
}

func (a *App) gitEnsureRepo() (string, error) {
	repoDir := a.gitRepoDir()
	gitDir := filepath.Join(repoDir, ".git")
	branch := a.cfg.GitBackupBranch
	authURL := a.gitAuthURL()

	if _, err := os.Stat(gitDir); os.IsNotExist(err) {
		if entries, err := os.ReadDir(repoDir); err == nil && len(entries) > 0 {
			os.RemoveAll(repoDir)
			log.Printf("git repo dir was non-empty without .git - cleared for fresh clone")
		}
		if err := os.MkdirAll(repoDir, 0o755); err != nil {
			return "", err
		}
		_, _, rc := a.gitRun([]string{"clone", "--branch", branch, authURL, "."}, repoDir)
		if rc != 0 {
			a.gitRun([]string{"init"}, repoDir)
			a.gitRun([]string{"remote", "add", "origin", authURL}, repoDir)
			a.gitRun([]string{"config", "user.email", "traefik-manager-agent@localhost"}, repoDir)
			a.gitRun([]string{"config", "user.name", "Traefik Manager Agent"}, repoDir)
			a.gitRun([]string{"pull", "origin", branch}, repoDir)
		}
	} else {
		a.gitRun([]string{"remote", "set-url", "origin", authURL}, repoDir)
		a.gitRun([]string{"config", "user.email", "traefik-manager-agent@localhost"}, repoDir)
		a.gitRun([]string{"config", "user.name", "Traefik Manager Agent"}, repoDir)
	}
	return repoDir, nil
}

func (a *App) gitPush(action string, customMsg string) error {
	if a.cfg.GitBackupRepo == "" {
		return fmt.Errorf("no repository configured")
	}
	repoDir, err := a.gitEnsureRepo()
	if err != nil {
		return fmt.Errorf("repo init failed: %w", err)
	}
	dynDir := filepath.Join(repoDir, "dynamic")
	staticDir := filepath.Join(repoDir, "static")
	os.MkdirAll(dynDir, 0o755)
	os.MkdirAll(staticDir, 0o755)

	copyToDir := func(src, destDir string) {
		info, err := os.Stat(src)
		if err != nil {
			return
		}
		if info.IsDir() {
			entries, _ := os.ReadDir(src)
			for _, e := range entries {
				if !e.IsDir() {
					data, err := os.ReadFile(filepath.Join(src, e.Name()))
					if err == nil {
						os.WriteFile(filepath.Join(destDir, e.Name()), data, 0o644)
					}
				}
			}
		} else {
			data, err := os.ReadFile(src)
			if err == nil {
				os.WriteFile(filepath.Join(destDir, filepath.Base(src)), data, 0o644)
			}
		}
	}

	copyToDir(a.cfg.ConfigPath, dynDir)
	if a.cfg.StaticConfigPath != "" {
		copyToDir(a.cfg.StaticConfigPath, staticDir)
	}

	ts := time.Now().Format("2006-01-02 15:04:05")
	msg := strings.NewReplacer("{action}", action, "{timestamp}", ts).Replace(a.cfg.GitBackupCommitMsg)
	if strings.TrimSpace(customMsg) != "" {
		msg = strings.TrimSpace(customMsg)
	}

	a.gitRun([]string{"add", "-A"}, repoDir)
	_, _, rc := a.gitRun([]string{"diff", "--cached", "--quiet"}, repoDir)
	if rc == 0 {
		return nil
	}
	_, errOut, rc := a.gitRun([]string{"commit", "-m", msg}, repoDir)
	if rc != 0 {
		return fmt.Errorf("commit failed: %s", errOut)
	}
	_, errOut, rc = a.gitRun([]string{"push", "-u", "origin", a.cfg.GitBackupBranch}, repoDir)
	if rc != 0 {
		token := a.cfg.GitBackupToken
		if token != "" {
			errOut = strings.ReplaceAll(errOut, token, "***")
		}
		return fmt.Errorf("push failed: %s", errOut)
	}
	log.Printf("git backup pushed: %s", msg)
	return nil
}

var shaRe = regexp.MustCompile(`^[0-9a-f]{7,40}$`)

func (a *App) gitStatusHandler(w http.ResponseWriter, r *http.Request) {
	result := map[string]any{
		"enabled":    a.cfg.GitBackupEnabled,
		"configured": a.cfg.GitBackupRepo != "",
		"last_sha":   nil,
		"last_push":  nil,
	}
	repoDir := a.gitRepoDir()
	if _, err := os.Stat(filepath.Join(repoDir, ".git")); err == nil {
		out, _, rc := a.gitRun([]string{"log", "-1", "--format=%H|%ci|%s"}, repoDir)
		if rc == 0 && strings.Contains(out, "|") {
			parts := strings.SplitN(out, "|", 3)
			if len(parts) >= 2 {
				result["last_sha"] = parts[0][:8]
				result["last_push"] = strings.TrimSpace(parts[1])
			}
		}
	}
	jsonOK(w, result)
}

func (a *App) gitPushHandler(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Message string `json:"message"`
	}
	json.NewDecoder(r.Body).Decode(&body)
	if err := a.gitPush("manual", body.Message); err != nil {
		jsonError(w, err.Error(), http.StatusInternalServerError)
		return
	}
	jsonOK(w, map[string]any{"ok": true})
}

func (a *App) gitTestHandler(w http.ResponseWriter, r *http.Request) {
	var body struct {
		RepoURL  string `json:"repo_url"`
		Username string `json:"username"`
		Token    string `json:"token"`
	}
	json.NewDecoder(r.Body).Decode(&body)
	repo := body.RepoURL
	if repo == "" {
		repo = a.cfg.GitBackupRepo
	}
	username := body.Username
	if username == "" {
		username = a.cfg.GitBackupUsername
	}
	token := body.Token
	if token == "" {
		token = a.cfg.GitBackupToken
	}
	if repo == "" {
		jsonError(w, "no repository URL configured", http.StatusBadRequest)
		return
	}
	u, err := url.Parse(repo)
	if err != nil {
		jsonError(w, "invalid repo URL", http.StatusBadRequest)
		return
	}
	if token != "" {
		if username != "" {
			u.User = url.UserPassword(username, token)
		} else {
			u.User = url.User(token)
		}
	}
	tmpDir, err := os.MkdirTemp("", "tma-git-test-*")
	if err != nil {
		jsonError(w, "internal error", http.StatusInternalServerError)
		return
	}
	defer os.RemoveAll(tmpDir)
	_, errOut, rc := a.gitRun([]string{"ls-remote", "--quiet", u.String()}, tmpDir)
	if rc != 0 {
		if token != "" {
			errOut = strings.ReplaceAll(errOut, token, "***")
		}
		jsonError(w, errOut, http.StatusBadRequest)
		return
	}
	jsonOK(w, map[string]any{"ok": true})
}

func (a *App) gitCommitsHandler(w http.ResponseWriter, r *http.Request) {
	repoDir := a.gitRepoDir()
	if _, err := os.Stat(filepath.Join(repoDir, ".git")); err != nil {
		jsonOK(w, []any{})
		return
	}
	out, _, rc := a.gitRun([]string{"log", "--format=%H|%ci|%s", "-50"}, repoDir)
	if rc != 0 {
		jsonOK(w, []any{})
		return
	}
	type commit struct {
		SHA      string `json:"sha"`
		SHAShort string `json:"sha_short"`
		Time     string `json:"timestamp"`
		Message  string `json:"message"`
	}
	var commits []commit
	for _, line := range strings.Split(out, "\n") {
		parts := strings.SplitN(line, "|", 3)
		if len(parts) == 3 {
			commits = append(commits, commit{
				SHA:      parts[0],
				SHAShort: parts[0][:8],
				Time:     strings.TrimSpace(parts[1]),
				Message:  parts[2],
			})
		}
	}
	jsonOK(w, commits)
}

func (a *App) gitDiffHandler(w http.ResponseWriter, r *http.Request, sha string) {
	if !shaRe.MatchString(sha) {
		jsonError(w, "invalid sha", http.StatusBadRequest)
		return
	}
	repoDir := a.gitRepoDir()
	if _, err := os.Stat(filepath.Join(repoDir, ".git")); err != nil {
		jsonOK(w, map[string]any{"stat": "", "files": []any{}})
		return
	}
	stat, _, _ := a.gitRun([]string{"show", "--stat", "--format=", sha}, repoDir)
	changed, _, rc := a.gitRun([]string{"diff-tree", "--no-commit-id", "-r", "--name-status", sha}, repoDir)
	if rc != 0 {
		jsonError(w, "diff failed", http.StatusInternalServerError)
		return
	}
	type fileDiff struct {
		Filename string `json:"filename"`
		Status   string `json:"status"`
		Old      string `json:"old"`
		New      string `json:"new"`
	}
	var files []fileDiff
	for _, line := range strings.Split(changed, "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		parts := strings.SplitN(line, "\t", 2)
		if len(parts) != 2 {
			continue
		}
		status, filename := strings.TrimSpace(parts[0]), strings.TrimSpace(parts[1])
		newContent, _, newRC := a.gitRun([]string{"show", sha + ":" + filename}, repoDir)
		oldContent, _, oldRC := a.gitRun([]string{"show", sha + "^:" + filename}, repoDir)
		files = append(files, fileDiff{
			Filename: filename,
			Status:   status,
			Old:      map[bool]string{true: oldContent, false: ""}[oldRC == 0],
			New:      map[bool]string{true: newContent, false: ""}[newRC == 0],
		})
	}
	jsonOK(w, map[string]any{"stat": stat, "files": files})
}

func (a *App) gitRestoreHandler(w http.ResponseWriter, r *http.Request, sha string) {
	if !shaRe.MatchString(sha) {
		jsonError(w, "invalid sha", http.StatusBadRequest)
		return
	}
	repoDir := a.gitRepoDir()
	if _, err := os.Stat(filepath.Join(repoDir, ".git")); err != nil {
		jsonError(w, "git repo not initialized", http.StatusBadRequest)
		return
	}
	if _, err := a.createBackup(); err != nil {
		log.Printf("pre-restore backup failed: %v", err)
	}
	cfgPath := a.cfg.ConfigPath
	info, _ := os.Stat(cfgPath)
	isDir := info != nil && info.IsDir()
	changed, _, rc := a.gitRun([]string{"diff-tree", "--no-commit-id", "-r", "--name-only", sha}, repoDir)
	if rc != 0 {
		jsonError(w, "failed to list commit files", http.StatusInternalServerError)
		return
	}
	for _, filename := range strings.Split(changed, "\n") {
		filename = strings.TrimSpace(filename)
		if filename == "" {
			continue
		}
		content, _, fileRC := a.gitRun([]string{"show", sha + ":" + filename}, repoDir)
		if fileRC != 0 {
			continue
		}
		base := filepath.Base(filename)
		var dest string
		if isDir {
			dest = filepath.Join(cfgPath, base)
		} else {
			dest = cfgPath
		}
		atomicWrite(dest, []byte(content))
	}
	if a.cfg.StaticConfigPath != "" {
		base := filepath.Base(a.cfg.StaticConfigPath)
		content, _, rc := a.gitRun([]string{"show", sha + ":static/" + base}, repoDir)
		if rc == 0 {
			atomicWrite(a.cfg.StaticConfigPath, []byte(content))
		}
	}
	jsonOK(w, map[string]any{"ok": true})
}

func (a *App) certsHandler(w http.ResponseWriter, r *http.Request) {
	if a.cfg.ACMEJSONPath == "" {
		jsonOK(w, map[string]any{"certs": []any{}, "error": "ACME_JSON_PATH not configured"})
		return
	}
	data, err := os.ReadFile(a.cfg.ACMEJSONPath)
	if err != nil {
		jsonOK(w, map[string]any{"certs": []any{}, "error": "acme.json not found at " + a.cfg.ACMEJSONPath})
		return
	}
	var acme map[string]any
	if err := json.Unmarshal(data, &acme); err != nil {
		jsonOK(w, map[string]any{"certs": []any{}, "error": "failed to parse acme.json"})
		return
	}
	type certEntry struct {
		Resolver string   `json:"resolver"`
		Main     string   `json:"main"`
		Sans     []string `json:"sans"`
		NotAfter *string  `json:"not_after"`
	}
	var certs []certEntry
	for resolverName, resolverData := range acme {
		rd, ok := resolverData.(map[string]any)
		if !ok {
			continue
		}
		rawCerts, _ := rd["Certificates"].([]any)
		if rawCerts == nil {
			rawCerts, _ = rd["certificates"].([]any)
		}
		for _, rc := range rawCerts {
			c, ok := rc.(map[string]any)
			if !ok {
				continue
			}
			domainMap, _ := c["domain"].(map[string]any)
			main, _ := domainMap["main"].(string)
			sans := []string{}
			if sv, ok := domainMap["sans"].([]any); ok {
				for _, s := range sv {
					if str, ok := s.(string); ok {
						sans = append(sans, str)
					}
				}
			}
			var notAfter *string
			if certB64, ok := c["certificate"].(string); ok && certB64 != "" {
				if na := parseCertExpiry(certB64); na != "" {
					notAfter = &na
				}
			}
			certs = append(certs, certEntry{Resolver: resolverName, Main: main, Sans: sans, NotAfter: notAfter})
		}
	}
	if certs == nil {
		certs = []certEntry{}
	}
	jsonOK(w, map[string]any{"certs": certs})
}

func parseCertExpiry(b64pem string) string {
	pemBytes, err := base64.StdEncoding.DecodeString(b64pem)
	if err != nil {
		return ""
	}
	block, _ := pem.Decode(pemBytes)
	if block == nil {
		return ""
	}
	cert, err := x509.ParseCertificate(block.Bytes)
	if err != nil {
		return ""
	}
	return cert.NotAfter.UTC().Format("2006-01-02T15:04:05Z")
}

func (a *App) configFiles() []string {
	cfgPath := a.cfg.ConfigPath
	info, err := os.Stat(cfgPath)
	if err != nil {
		return nil
	}
	if !info.IsDir() {
		return []string{cfgPath}
	}
	entries, _ := os.ReadDir(cfgPath)
	var files []string
	for _, e := range entries {
		n := e.Name()
		if !e.IsDir() && (strings.HasSuffix(n, ".yml") || strings.HasSuffix(n, ".yaml")) {
			files = append(files, filepath.Join(cfgPath, n))
		}
	}
	return files
}

func (a *App) routeRawGetHandler(w http.ResponseWriter, r *http.Request, routeID string) {
	var rname, cf string
	if idx := strings.Index(routeID, "::"); idx >= 0 {
		cf = routeID[:idx]
		rname = routeID[idx+2:]
	} else {
		rname = routeID
	}

	var scanPaths []string
	if cf != "" {
		scanPaths = []string{filepath.Join(a.cfg.ConfigPath, cf)}
	} else {
		scanPaths = a.configFiles()
	}

	for _, p := range scanPaths {
		data, err := os.ReadFile(p)
		if err != nil {
			continue
		}
		var config map[string]any
		if err := yaml.Unmarshal(data, &config); err != nil {
			continue
		}
		for _, proto := range []string{"http", "tcp", "udp"} {
			protoMap, _ := config[proto].(map[string]any)
			if protoMap == nil {
				continue
			}
			routers, _ := protoMap["routers"].(map[string]any)
			router, ok := routers[rname]
			if !ok {
				continue
			}
			routerMap, _ := router.(map[string]any)
			svcName := rname
			if sn, ok := routerMap["service"].(string); ok && sn != "" {
				svcName = sn
			}
			out := map[string]any{proto: map[string]any{"routers": map[string]any{rname: router}}}
			services, _ := protoMap["services"].(map[string]any)
			if svc, ok := services[svcName]; ok {
				out[proto].(map[string]any)["services"] = map[string]any{svcName: svc}
			}
			raw, err := yaml.Marshal(out)
			if err != nil {
				jsonError(w, "failed to marshal YAML", http.StatusInternalServerError)
				return
			}
			jsonOK(w, map[string]any{"raw": string(raw), "configFile": filepath.Base(p), "proto": proto})
			return
		}
	}
	jsonError(w, "Route not found", http.StatusNotFound)
}

func (a *App) routeRawSaveHandler(w http.ResponseWriter, r *http.Request, routeID string) {
	var body struct {
		Content string `json:"content"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || strings.TrimSpace(body.Content) == "" {
		jsonError(w, "invalid request body", http.StatusBadRequest)
		return
	}

	var rname, cf string
	if idx := strings.Index(routeID, "::"); idx >= 0 {
		cf = routeID[:idx]
		rname = routeID[idx+2:]
	} else {
		rname = routeID
	}

	var newData map[string]any
	if err := yaml.Unmarshal([]byte(body.Content), &newData); err != nil {
		jsonError(w, "invalid YAML: "+err.Error(), http.StatusBadRequest)
		return
	}

	var targetPath string
	if cf != "" {
		targetPath = filepath.Join(a.cfg.ConfigPath, cf)
	} else {
		for _, p := range a.configFiles() {
			data, err := os.ReadFile(p)
			if err != nil {
				continue
			}
			var cfg map[string]any
			if err := yaml.Unmarshal(data, &cfg); err != nil {
				continue
			}
			for _, proto := range []string{"http", "tcp", "udp"} {
				protoMap, _ := cfg[proto].(map[string]any)
				routers, _ := protoMap["routers"].(map[string]any)
				if _, ok := routers[rname]; ok {
					targetPath = p
					break
				}
			}
			if targetPath != "" {
				break
			}
		}
	}
	if targetPath == "" {
		jsonError(w, "Route not found", http.StatusNotFound)
		return
	}

	data, _ := os.ReadFile(targetPath)
	var config map[string]any
	yaml.Unmarshal(data, &config)
	if config == nil {
		config = map[string]any{}
	}

	for _, proto := range []string{"http", "tcp", "udp"} {
		protoMap, _ := config[proto].(map[string]any)
		if protoMap == nil {
			continue
		}
		routers, _ := protoMap["routers"].(map[string]any)
		if router, ok := routers[rname]; ok {
			routerMap, _ := router.(map[string]any)
			svcName := rname
			if sn, ok := routerMap["service"].(string); ok && sn != "" {
				svcName = sn
			}
			delete(routers, rname)
			if services, ok := protoMap["services"].(map[string]any); ok {
				delete(services, svcName)
			}
		}
	}

	for _, proto := range []string{"http", "tcp", "udp"} {
		newProto, _ := newData[proto].(map[string]any)
		if newProto == nil {
			continue
		}
		section, _ := config[proto].(map[string]any)
		if section == nil {
			section = map[string]any{}
			config[proto] = section
		}
		if newRouters, ok := newProto["routers"].(map[string]any); ok {
			existing, _ := section["routers"].(map[string]any)
			if existing == nil {
				existing = map[string]any{}
			}
			for k, v := range newRouters {
				existing[k] = v
			}
			section["routers"] = existing
		}
		if newServices, ok := newProto["services"].(map[string]any); ok {
			existing, _ := section["services"].(map[string]any)
			if existing == nil {
				existing = map[string]any{}
			}
			for k, v := range newServices {
				existing[k] = v
			}
			section["services"] = existing
		}
	}

	if err := a.createFileBak(targetPath, filepath.Base(targetPath)); err != nil {
		log.Printf("pre-write backup failed: %v", err)
	}
	out, err := yaml.Marshal(config)
	if err != nil {
		jsonError(w, "failed to marshal YAML", http.StatusInternalServerError)
		return
	}
	if err := atomicWrite(targetPath, out); err != nil {
		jsonError(w, "write failed: "+err.Error(), http.StatusInternalServerError)
		return
	}
	if a.cfg.GitBackupEnabled && a.cfg.GitBackupAutoPush && a.cfg.GitBackupRepo != "" {
		go func() {
			if err := a.gitPush("route raw save", ""); err != nil {
				log.Printf("git auto-push failed: %v", err)
			}
		}()
	}
	jsonOK(w, map[string]any{"ok": true})
}

func (a *App) logsHandler(w http.ResponseWriter, r *http.Request) {
	if a.cfg.AccessLogPath == "" {
		jsonOK(w, map[string]any{"error": "ACCESS_LOG_PATH not configured", "lines": []any{}})
		return
	}
	linesReq := 100
	if v := r.URL.Query().Get("lines"); v != "" {
		fmt.Sscanf(v, "%d", &linesReq)
		if linesReq > 1000 {
			linesReq = 1000
		}
	}
	f, err := os.Open(a.cfg.AccessLogPath)
	if err != nil {
		jsonOK(w, map[string]any{"error": "Access log not found at " + a.cfg.AccessLogPath, "lines": []any{}})
		return
	}
	defer f.Close()

	info, _ := f.Stat()
	size := info.Size()
	const bufSize = 8192
	var collected []string
	remaining := size
	partial := []byte{}
	for remaining > 0 && len(collected) < linesReq {
		chunk := int64(bufSize)
		if chunk > remaining {
			chunk = remaining
		}
		remaining -= chunk
		buf := make([]byte, chunk)
		f.Seek(remaining, io.SeekStart)
		f.Read(buf)
		data := append(buf, partial...)
		parts := bytes.Split(data, []byte("\n"))
		partial = parts[0]
		for i := len(parts) - 1; i >= 1; i-- {
			line := strings.TrimSpace(string(parts[i]))
			if line != "" {
				collected = append([]string{line}, collected...)
				if len(collected) >= linesReq {
					break
				}
			}
		}
	}
	if len(collected) > linesReq {
		collected = collected[len(collected)-linesReq:]
	}
	jsonOK(w, map[string]any{"lines": collected})
}

func (a *App) gitResetHandler(w http.ResponseWriter, r *http.Request) {
	repoDir := a.gitRepoDir()
	if err := os.RemoveAll(repoDir); err != nil {
		jsonError(w, "reset failed: "+err.Error(), http.StatusInternalServerError)
		return
	}
	log.Printf("git repo directory reset by user")
	jsonOK(w, map[string]any{"ok": true})
}
