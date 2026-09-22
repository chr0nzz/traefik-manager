package main

import (
	"bytes"
	"context"
	"crypto/sha1"
	"crypto/sha256"
	"crypto/x509"
	"encoding/base64"
	"encoding/hex"
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
	"strconv"
	"strings"
	"sync"
	"time"

	"gopkg.in/yaml.v3"
)

func jsonOK(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(v)
}

func jsonError(w http.ResponseWriter, msg string, code int) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	json.NewEncoder(w).Encode(map[string]any{"error": msg, "ok": false})
}

func jsonErrorCode(w http.ResponseWriter, errCode string, params map[string]any, msg string, status int) {
	body := map[string]any{"error": msg, "code": errCode, "ok": false}
	if len(params) > 0 {
		body["params"] = params
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(body)
}

func (a *App) debugf(format string, args ...any) {
	if a.cfg.Debug {
		log.Printf("[debug] "+format, args...)
	}
}

func (a *App) applyTraefikAuth(req *http.Request) {
	if a.cfg.TraefikAPIUser != "" && a.cfg.TraefikAPIPassword != "" {
		req.SetBasicAuth(a.cfg.TraefikAPIUser, a.cfg.TraefikAPIPassword)
	}
}

func (a *App) healthHandler(w http.ResponseWriter, r *http.Request) {
	jsonOK(w, map[string]any{"ok": true, "version": Version})
}

func (a *App) routerDetailHandler(w http.ResponseWriter, r *http.Request, rest string) {
	parts := strings.SplitN(rest, "/", 2)
	if len(parts) != 2 || parts[1] == "" {
		jsonErrorCode(w, "router_name_required", nil, "router name is required", http.StatusBadRequest)
		return
	}
	proto := strings.ToLower(parts[0])
	if proto != "http" && proto != "tcp" && proto != "udp" {
		proto = "http"
	}
	a.traefikProxy(w, r, "/api/"+proto+"/routers/"+url.PathEscape(parts[1]))
}

func (a *App) traefikProxy(w http.ResponseWriter, r *http.Request, traefikPath string) {
	target := strings.TrimRight(a.cfg.TraefikAPIURL, "/") + traefikPath
	ctx, cancel := context.WithTimeout(r.Context(), 12*time.Second)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, target, nil)
	if err != nil {
		jsonErrorCode(w, "proxy_error", map[string]any{"detail": err.Error()}, "proxy error: "+err.Error(), http.StatusInternalServerError)
		return
	}
	a.applyTraefikAuth(req)
	resp, err := a.httpClient.Do(req)
	if err != nil {
		a.debugf("traefik proxy %s failed: %v", target, err)
		jsonErrorCode(w, "traefik_unavailable", map[string]any{"detail": err.Error()}, "traefik unavailable: "+err.Error(), http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		a.debugf("traefik proxy %s returned status %d", target, resp.StatusCode)
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

const (
	traefikPageSize = 1000
	traefikMaxPages = 50
)

func (a *App) traefikFetchPage(ctx context.Context, target string) (json.RawMessage, int, error) {
	ctx2, cancel := context.WithTimeout(ctx, 12*time.Second)
	defer cancel()
	req, err := http.NewRequestWithContext(ctx2, http.MethodGet, target, nil)
	if err != nil {
		return nil, 0, err
	}
	a.applyTraefikAuth(req)
	resp, err := a.httpClient.Do(req)
	if err != nil {
		a.debugf("traefik fetch %s failed: %v", target, err)
		return nil, 0, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		a.debugf("traefik fetch %s returned status %d", target, resp.StatusCode)
		return nil, 0, fmt.Errorf("traefik returned status %d", resp.StatusCode)
	}
	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, 0, err
	}
	next, _ := strconv.Atoi(resp.Header.Get("X-Next-Page"))
	return json.RawMessage(body), next, nil
}

func (a *App) traefikFetchProto(ctx context.Context, traefikPath string) (json.RawMessage, error) {
	sep := "?"
	if strings.Contains(traefikPath, "?") {
		sep = "&"
	}
	base := strings.TrimRight(a.cfg.TraefikAPIURL, "/") + traefikPath + sep + "per_page=" + strconv.Itoa(traefikPageSize)
	all := []json.RawMessage{}
	page := 1
	for i := 0; i < traefikMaxPages; i++ {
		target := base
		if page > 1 {
			target += "&page=" + strconv.Itoa(page)
		}
		body, next, err := a.traefikFetchPage(ctx, target)
		if err != nil {
			if i == 0 {
				return json.RawMessage("[]"), err
			}
			return json.RawMessage("[]"), fmt.Errorf("page %d of %s: %w", page, traefikPath, err)
		}
		var chunk []json.RawMessage
		if err := json.Unmarshal(body, &chunk); err != nil {
			if i == 0 {
				return body, nil
			}
			return json.RawMessage("[]"), fmt.Errorf("page %d of %s: %w", page, traefikPath, err)
		}
		all = append(all, chunk...)
		if len(chunk) == 0 || next <= page {
			break
		}
		page = next
	}
	out, err := json.Marshal(all)
	if err != nil {
		return json.RawMessage("[]"), err
	}
	return json.RawMessage(out), nil
}

func (a *App) routersHandler(w http.ResponseWriter, r *http.Request) {
	httpR, err := a.traefikFetchProto(r.Context(), "/api/http/routers")
	if err != nil {
		jsonErrorCode(w, "traefik_unavailable_at", map[string]any{"url": a.cfg.TraefikAPIURL, "detail": err.Error()}, "traefik unavailable at "+a.cfg.TraefikAPIURL+": "+err.Error(), http.StatusBadGateway)
		return
	}
	tcpR, tcpErr := a.traefikFetchProto(r.Context(), "/api/tcp/routers")
	udpR, udpErr := a.traefikFetchProto(r.Context(), "/api/udp/routers")
	out := map[string]any{"http": httpR, "tcp": tcpR, "udp": udpR, "complete": tcpErr == nil && udpErr == nil}
	if tcpErr != nil {
		out["tcp_error"] = tcpErr.Error()
	}
	if udpErr != nil {
		out["udp_error"] = udpErr.Error()
	}
	jsonOK(w, out)
}

func (a *App) servicesHandler(w http.ResponseWriter, r *http.Request) {
	httpS, err := a.traefikFetchProto(r.Context(), "/api/http/services")
	if err != nil {
		jsonErrorCode(w, "traefik_unavailable_at", map[string]any{"url": a.cfg.TraefikAPIURL, "detail": err.Error()}, "traefik unavailable at "+a.cfg.TraefikAPIURL+": "+err.Error(), http.StatusBadGateway)
		return
	}
	tcpS, _ := a.traefikFetchProto(r.Context(), "/api/tcp/services")
	udpS, _ := a.traefikFetchProto(r.Context(), "/api/udp/services")
	jsonOK(w, map[string]json.RawMessage{"http": httpS, "tcp": tcpS, "udp": udpS})
}

func (a *App) middlewaresHandler(w http.ResponseWriter, r *http.Request) {
	httpM, err := a.traefikFetchProto(r.Context(), "/api/http/middlewares")
	if err != nil {
		jsonErrorCode(w, "traefik_unavailable_at", map[string]any{"url": a.cfg.TraefikAPIURL, "detail": err.Error()}, "traefik unavailable at "+a.cfg.TraefikAPIURL+": "+err.Error(), http.StatusBadGateway)
		return
	}
	tcpM, _ := a.traefikFetchProto(r.Context(), "/api/tcp/middlewares")
	jsonOK(w, map[string]json.RawMessage{"http": httpM, "tcp": tcpM})
}

type fileEntry struct {
	Name    string `json:"name"`
	Content string `json:"content"`
}

func (a *App) configsReadHandler(w http.ResponseWriter, r *http.Request) {
	cfgPath := a.cfg.ConfigPath
	info, err := os.Stat(cfgPath)
	if err != nil {
		jsonErrorCode(w, "config_path_not_found", nil, "config path not found", http.StatusNotFound)
		return
	}
	files := []fileEntry{}
	if info.IsDir() {
		entries, err := os.ReadDir(cfgPath)
		if err != nil {
			jsonErrorCode(w, "config_dir_unreadable", nil, "cannot read config dir", http.StatusInternalServerError)
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
			jsonErrorCode(w, "config_file_unreadable", nil, "cannot read config file", http.StatusInternalServerError)
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
		jsonErrorCode(w, "invalid_body", nil, "invalid request body", http.StatusBadRequest)
		return
	}
	cfgPath := a.cfg.ConfigPath
	info, err := os.Stat(cfgPath)
	var targetPath string
	if err == nil && info.IsDir() {
		if _, ok := safeBaseName(body.Name); !ok {
			jsonErrorCode(w, "invalid_file_name", nil, "invalid file name", http.StatusBadRequest)
			return
		}
		targetPath = filepath.Join(cfgPath, body.Name)
	} else {
		targetPath = cfgPath
	}
	a.cfgMu.Lock()
	defer a.cfgMu.Unlock()
	if err := a.createFileBak(targetPath, filepath.Base(targetPath)); err != nil {
		a.failuref("backup", "pre-write backup of %s failed: %v", targetPath, err)
		jsonErrorCode(w, "backup_failed_nothing_written", map[string]any{"detail": err.Error()}, "backup failed, nothing was written: "+err.Error(), http.StatusInternalServerError)
		return
	}
	if err := atomicWrite(targetPath, []byte(body.Content)); err != nil {
		jsonErrorCode(w, "write_failed", map[string]any{"detail": err.Error()}, "write failed: "+err.Error(), http.StatusInternalServerError)
		return
	}
	if a.cfg.GitBackupEnabled && a.cfg.GitBackupAutoPush && a.cfg.GitBackupRepo != "" {
		go func() {
			if err := a.gitPush("config save", ""); err != nil {
				a.failuref("git", "auto-push failed: %v", err)
			}
		}()
	}
	jsonOK(w, map[string]any{"ok": true})
}

func atomicWrite(path string, data []byte) error {
	f, err := os.CreateTemp(filepath.Dir(path), "."+filepath.Base(path)+".tmp-*")
	if err != nil {
		return err
	}
	tmp := f.Name()
	_, werr := f.Write(data)
	if cerr := f.Close(); werr == nil {
		werr = cerr
	}
	if werr == nil {
		werr = os.Chmod(tmp, 0o644)
	}
	if werr != nil {
		os.Remove(tmp)
		return werr
	}
	if err := os.Rename(tmp, path); err != nil {
		os.Remove(tmp)
		return os.WriteFile(path, data, 0o644)
	}
	return nil
}

func (a *App) staticReadHandler(w http.ResponseWriter, r *http.Request) {
	if a.cfg.StaticConfigPath == "" {
		jsonErrorCode(w, "static_config_missing", nil, "STATIC_CONFIG_PATH not configured", http.StatusNotFound)
		return
	}
	data, err := os.ReadFile(a.cfg.StaticConfigPath)
	if err != nil {
		jsonErrorCode(w, "static_config_unreadable", map[string]any{"detail": err.Error()}, "cannot read static config: "+err.Error(), http.StatusInternalServerError)
		return
	}
	jsonOK(w, map[string]any{"content": string(data), "path": a.cfg.StaticConfigPath})
}

func (a *App) staticWriteHandler(w http.ResponseWriter, r *http.Request) {
	if a.cfg.StaticConfigPath == "" {
		jsonErrorCode(w, "static_config_missing", nil, "STATIC_CONFIG_PATH not configured", http.StatusNotFound)
		return
	}
	var body struct {
		Content string `json:"content"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErrorCode(w, "invalid_body", nil, "invalid request body", http.StatusBadRequest)
		return
	}
	if err := a.createFileBak(a.cfg.StaticConfigPath, ""); err != nil {
		a.failuref("backup", "pre-write backup of %s failed: %v", a.cfg.StaticConfigPath, err)
		jsonErrorCode(w, "backup_failed_nothing_written", map[string]any{"detail": err.Error()}, "backup failed, nothing was written: "+err.Error(), http.StatusInternalServerError)
		return
	}
	if err := atomicWrite(a.cfg.StaticConfigPath, []byte(body.Content)); err != nil {
		jsonErrorCode(w, "write_failed", map[string]any{"detail": err.Error()}, "write failed: "+err.Error(), http.StatusInternalServerError)
		return
	}
	jsonOK(w, map[string]any{"ok": true})
}

func (a *App) pluginsHandler(w http.ResponseWriter, r *http.Request) {
	empty := []map[string]any{}
	if a.cfg.StaticConfigPath == "" {
		jsonOK(w, map[string]any{"plugins": empty, "error": "STATIC_CONFIG_PATH not configured on this agent", "code": "static_config_missing"})
		return
	}
	data, err := os.ReadFile(a.cfg.StaticConfigPath)
	if err != nil {
		jsonOK(w, map[string]any{"plugins": empty, "error": "cannot read static config: " + err.Error(), "code": "static_config_unreadable", "params": map[string]any{"detail": err.Error()}})
		return
	}
	var cfg struct {
		Experimental struct {
			Plugins map[string]struct {
				ModuleName string `yaml:"moduleName"`
				Version    string `yaml:"version"`
				Settings   any    `yaml:"settings"`
			} `yaml:"plugins"`
		} `yaml:"experimental"`
	}
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		jsonOK(w, map[string]any{"plugins": empty, "error": "invalid YAML: " + err.Error(), "code": "invalid_yaml", "params": map[string]any{"detail": err.Error()}})
		return
	}
	plugins := make([]map[string]any, 0, len(cfg.Experimental.Plugins))
	for name, p := range cfg.Experimental.Plugins {
		plugins = append(plugins, map[string]any{"name": name, "moduleName": p.ModuleName, "version": p.Version, "settings": p.Settings})
	}
	sort.Slice(plugins, func(i, j int) bool {
		return plugins[i]["name"].(string) < plugins[j]["name"].(string)
	})
	jsonOK(w, map[string]any{"plugins": plugins})
}

func (a *App) staticStatusHandler(w http.ResponseWriter, r *http.Request) {
	jsonOK(w, map[string]any{
		"configured":        a.cfg.StaticConfigPath != "",
		"path":              a.cfg.StaticConfigPath,
		"restart_method":    a.cfg.RestartMethod,
		"traefik_container": a.cfg.TraefikContainer,
	})
}

func (a *App) staticRestartHandler(w http.ResponseWriter, r *http.Request) {
	switch a.cfg.RestartMethod {
	case "poison-pill":
		if a.cfg.SignalFilePath == "" {
			jsonErrorCode(w, "signal_file_missing", nil, "SIGNAL_FILE_PATH not configured", http.StatusBadRequest)
			return
		}
		if err := os.WriteFile(a.cfg.SignalFilePath, []byte("restart"), 0o644); err != nil {
			jsonErrorCode(w, "signal_file_write_failed", map[string]any{"detail": err.Error()}, "failed to write signal file: "+err.Error(), http.StatusInternalServerError)
			return
		}
		jsonOK(w, map[string]any{"ok": true, "restarting": true})

	case "socket", "proxy":
		if err := a.dockerPreflight(r.Context()); err != nil {
			jsonErrorCode(w, "docker_restart_failed", map[string]any{"detail": err.Error()}, "docker restart failed: "+err.Error(), http.StatusInternalServerError)
			return
		}
		jsonOK(w, map[string]any{"ok": true, "restarting": true})
		go func() {
			time.Sleep(400 * time.Millisecond)
			ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
			defer cancel()
			if err := a.dockerRestart(ctx); err != nil {
				a.failuref("restart", "Traefik restart failed: %v", err)
			}
		}()

	default:
		jsonErrorCode(w, "restart_method_missing", nil, "RESTART_METHOD not configured or unsupported", http.StatusBadRequest)
	}
}

func (a *App) traefikContainer() string {
	if a.cfg.TraefikContainer != "" {
		return a.cfg.TraefikContainer
	}
	return "traefik"
}

func (a *App) dockerClient() (*http.Client, string) {
	dockerHost := a.cfg.DockerHost
	if a.cfg.RestartMethod == "socket" || dockerHost == "" {
		return &http.Client{
			Transport: &http.Transport{
				DialContext: func(ctx context.Context, _, _ string) (net.Conn, error) {
					return net.Dial("unix", "/var/run/docker.sock")
				},
			},
		}, "http://localhost"
	}
	h := strings.TrimRight(dockerHost, "/")
	if strings.HasPrefix(h, "tcp://") {
		h = "http://" + strings.TrimPrefix(h, "tcp://")
	} else if !strings.HasPrefix(h, "http://") && !strings.HasPrefix(h, "https://") {
		h = "http://" + h
	}
	return http.DefaultClient, h
}

func (a *App) dockerPreflight(ctx context.Context) error {
	client, baseURL := a.dockerClient()
	req, err := http.NewRequestWithContext(ctx, http.MethodGet,
		baseURL+"/containers/"+a.traefikContainer()+"/json", nil)
	if err != nil {
		return err
	}
	resp, err := client.Do(req)
	if err != nil {
		return fmt.Errorf("cannot reach the Docker API: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode == http.StatusNotFound {
		return fmt.Errorf("container %q not found", a.traefikContainer())
	}
	return nil
}

func (a *App) dockerRestart(ctx context.Context) error {
	apiPath := "/containers/" + a.traefikContainer() + "/restart?t=10"
	client, baseURL := a.dockerClient()

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
	payload := map[string]any{"scenarios": []string{}}
	if a.cfg.CrowdSecMachineID != "" && a.cfg.CrowdSecMachinePassword != "" {
		payload["machine_id"] = a.cfg.CrowdSecMachineID
		payload["password"] = a.cfg.CrowdSecMachinePassword
	}
	body, _ := json.Marshal(payload)
	target := strings.TrimRight(a.cfg.CrowdSecLAPIURL, "/") + "/v1/watchers/login"
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, target, bytes.NewReader(body))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")
	resp, err := a.cs().Do(req)
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

func (a *App) cs() *http.Client {
	if a.csClient != nil {
		return a.csClient
	}
	return http.DefaultClient
}

func (a *App) csHasCert() bool {
	return a.cfg.CrowdSecClientCert != "" && a.cfg.CrowdSecClientKey != ""
}

func (a *App) csHasMachine() bool {
	return (a.cfg.CrowdSecMachineID != "" && a.cfg.CrowdSecMachinePassword != "") || a.csHasCert()
}

func csJWTReset() {
	csJWTMu.Lock()
	defer csJWTMu.Unlock()
	csJWT = ""
	csJWTExpiry = time.Time{}
}

func (a *App) csSend(ctx context.Context, method, target string, body io.Reader, useJWT bool) (*http.Response, error) {
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
	return a.cs().Do(req)
}

func (a *App) csRequest(ctx context.Context, method, csPath string, body io.Reader, useJWT bool) (*http.Response, error) {
	target := strings.TrimRight(a.cfg.CrowdSecLAPIURL, "/") + csPath
	var buf []byte
	if body != nil {
		var err error
		if buf, err = io.ReadAll(body); err != nil {
			return nil, err
		}
	}
	replay := func() io.Reader {
		if body == nil {
			return nil
		}
		return bytes.NewReader(buf)
	}
	resp, err := a.csSend(ctx, method, target, replay(), useJWT)
	if err != nil || resp == nil {
		return resp, err
	}
	if resp.StatusCode != http.StatusUnauthorized || !useJWT || !a.csHasMachine() {
		return resp, nil
	}
	resp.Body.Close()
	log.Printf("crowdsec: machine token refused, logging in again")
	csJWTReset()
	return a.csSend(ctx, method, target, replay(), useJWT)
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

const (
	csPageSize = 1000
	csMaxPages = 200
)

func (a *App) csActiveDecisions(ctx context.Context, forceFull bool) ([]json.RawMessage, string, error) {
	now := time.Now().UTC()

	if csStreamable {
		rows, mode, err := a.csDecisionsStream(ctx, forceFull)
		if err == nil {
			return csFilterActive(rows, now), csStaleNoteFromMode(mode), nil
		}
		if strings.Contains(err.Error(), "LAPI 404") || strings.Contains(err.Error(), "LAPI 405") {
			log.Printf("crowdsec: LAPI has no /v1/decisions/stream, falling back to the paged walk")
			csStreamable = false
		} else {
			return nil, "", err
		}
	}

	all := []json.RawMessage{}
	cursor := int64(0)
	for page := 0; page < csMaxPages; page++ {
		path := fmt.Sprintf("/v1/decisions?limit=%d&id_gt=%d", csPageSize, cursor)
		chunk, err := a.csPageJSON(ctx, path, false)
		if err != nil {
			if page == 0 {
				return nil, "", err
			}
			break
		}
		if len(chunk) == 0 {
			break
		}
		maxID := cursor
		for _, raw := range chunk {
			var d struct {
				ID    int64  `json:"id"`
				Until string `json:"until"`
			}
			if err := json.Unmarshal(raw, &d); err == nil {
				if d.ID > maxID {
					maxID = d.ID
				}
				if d.Until != "" {
					if exp, perr := time.Parse(time.RFC3339, d.Until); perr == nil && exp.Before(now) {
						continue
					}
				}
			}
			all = append(all, raw)
		}
		if maxID == cursor || len(chunk) < csPageSize {
			break
		}
		cursor = maxID
	}
	return all, "", nil
}

func (a *App) crowdsecDecisionsHandler(w http.ResponseWriter, r *http.Request) {
	if a.cfg.CrowdSecLAPIURL == "" {
		jsonErrorCode(w, "crowdsec_missing", nil, "CROWDSEC_LAPI_URL not configured", http.StatusNotFound)
		return
	}
	rows, staleNote, err := a.csActiveDecisions(r.Context(), r.URL.Query().Get("full") == "1")
	if err != nil {
		jsonErrorCode(w, "crowdsec_unavailable", map[string]any{"detail": err.Error()}, "crowdsec unavailable: "+err.Error(), http.StatusBadGateway)
		return
	}
	w.Header().Set("Content-Type", "application/json")
	if staleNote != "" {
		w.Header().Set("X-CS-Stale", staleNote)
	}
	json.NewEncoder(w).Encode(rows)
}

func (a *App) crowdsecDecisionsSearchHandler(w http.ResponseWriter, r *http.Request) {
	if a.cfg.CrowdSecLAPIURL == "" {
		jsonErrorCode(w, "crowdsec_missing", nil, "CROWDSEC_LAPI_URL not configured", http.StatusNotFound)
		return
	}
	rows, staleNote, err := a.csActiveDecisions(r.Context(), false)
	if err != nil {
		jsonErrorCode(w, "crowdsec_unavailable", map[string]any{"detail": err.Error()}, "crowdsec unavailable: "+err.Error(), http.StatusBadGateway)
		return
	}
	if staleNote != "" {
		w.Header().Set("X-CS-Stale", staleNote)
	}

	q := r.URL.Query()
	page := 1
	if n, perr := strconv.Atoi(q.Get("page")); perr == nil && n >= 1 {
		page = n
	}
	per := 20
	if n, perr := strconv.Atoi(q.Get("per")); perr == nil && n >= 1 && n <= 200 {
		per = n
	}

	originFilter := strings.ToLower(strings.TrimSpace(q.Get("origin")))
	typeFilter := strings.ToLower(strings.TrimSpace(q.Get("type")))
	ipFilter := strings.TrimSpace(q.Get("ip"))
	scenarioFilter := strings.TrimSpace(q.Get("scenario"))
	term := strings.ToLower(strings.TrimSpace(q.Get("q")))

	parsed := make([]csSearchRow, 0, len(rows))
	for _, raw := range rows {
		var d struct {
			ID       int64  `json:"id"`
			Origin   string `json:"origin"`
			Type     string `json:"type"`
			Value    string `json:"value"`
			Scope    string `json:"scope"`
			Scenario string `json:"scenario"`
		}
		if json.Unmarshal(raw, &d) != nil {
			continue
		}
		originKey := strings.ToLower(strings.TrimSpace(d.Origin))
		parsed = append(parsed, csSearchRow{
			raw: raw, id: d.ID, origin: originKey, typ: strings.ToLower(d.Type),
			value: d.Value, scope: d.Scope, scenario: d.Scenario,
			own: originKey != "capi" && originKey != "lists",
		})
	}

	matchOrigin := func(d csSearchRow) bool {
		switch originFilter {
		case "":
			return true
		case "subscribed":
			return d.origin == "capi" || d.origin == "lists"
		case "own":
			return d.own
		case "byhand":
			return d.origin == "cscli" || d.origin == "manual"
		default:
			return d.origin == originFilter
		}
	}
	matchType := func(d csSearchRow) bool { return typeFilter == "" || d.typ == typeFilter }
	matchIP := func(d csSearchRow) bool { return ipFilter == "" || d.value == ipFilter }
	matchScenario := func(d csSearchRow) bool { return scenarioFilter == "" || d.scenario == scenarioFilter }
	matchQ := func(d csSearchRow) bool {
		if term == "" {
			return true
		}
		hay := strings.ToLower(d.value + " " + d.scenario + " " + d.origin + " " + d.scope + " " + d.typ)
		return strings.Contains(hay, term)
	}

	var filtered []csSearchRow
	facetOrigin, facetType := 0, 0
	for _, d := range parsed {
		if matchOrigin(d) && matchType(d) && matchIP(d) && matchScenario(d) && matchQ(d) {
			filtered = append(filtered, d)
		}
		if matchOrigin(d) && matchQ(d) {
			facetOrigin++
		}
		if matchType(d) && matchQ(d) {
			facetType++
		}
	}

	sort.SliceStable(filtered, func(i, j int) bool {
		if filtered[i].own != filtered[j].own {
			return filtered[i].own
		}
		return filtered[i].id > filtered[j].id
	})

	total := len(filtered)
	pages := 1
	if total > 0 {
		pages = (total + per - 1) / per
	}
	if page > pages {
		page = pages
	}
	start := (page - 1) * per
	if start > total {
		start = total
	}
	end := start + per
	if end > total {
		end = total
	}
	outRows := make([]json.RawMessage, 0, end-start)
	for _, d := range filtered[start:end] {
		outRows = append(outRows, d.raw)
	}

	jsonOK(w, map[string]any{
		"rows": outRows, "total": total, "page": page, "pages": pages, "per": per,
		"facet_totals": map[string]any{"origin": facetOrigin, "type": facetType},
	})
}

type csSearchRow struct {
	raw      json.RawMessage
	id       int64
	origin   string
	typ      string
	value    string
	scope    string
	scenario string
	own      bool
}

func (a *App) crowdsecAlertsHandler(w http.ResponseWriter, r *http.Request) {
	if a.cfg.CrowdSecLAPIURL == "" {
		jsonErrorCode(w, "crowdsec_missing", nil, "CROWDSEC_LAPI_URL not configured", http.StatusNotFound)
		return
	}
	limit := a.cfg.CrowdSecAlertLimit
	if q := r.URL.Query().Get("limit"); q != "" {
		if n, err := strconv.Atoi(q); err == nil && n >= 0 && n <= 100000 {
			limit = n
		}
	}
	forceFull := r.URL.Query().Get("full") == "1"
	chunk, _, _, err := a.csAlerts(r.Context(), limit, forceFull)
	if err != nil {
		jsonErrorCode(w, "crowdsec_unavailable", map[string]any{"detail": err.Error()}, "crowdsec unavailable: "+err.Error(), http.StatusBadGateway)
		return
	}
	capped := limit > 0 && len(chunk) >= limit
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
	w.Header().Set("X-CS-Alert-Limit", strconv.Itoa(limit))
	if capped {
		w.Header().Set("X-CS-Alert-Capped", "1")
	} else {
		w.Header().Set("X-CS-Alert-Capped", "0")
	}
	json.NewEncoder(w).Encode(out)
}

func (a *App) crowdsecAddDecisionHandler(w http.ResponseWriter, r *http.Request) {
	if a.cfg.CrowdSecLAPIURL == "" {
		jsonErrorCode(w, "crowdsec_missing", nil, "CROWDSEC_LAPI_URL not configured", http.StatusNotFound)
		return
	}
	var body struct {
		Value    string `json:"value"`
		Type     string `json:"type"`
		Duration string `json:"duration"`
		Reason   string `json:"reason"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil {
		jsonErrorCode(w, "invalid_body", nil, "invalid request body", http.StatusBadRequest)
		return
	}
	ip := strings.TrimSpace(body.Value)
	if ip == "" {
		jsonErrorCode(w, "ip_required", nil, "IP/Range is required", http.StatusBadRequest)
		return
	}
	dtype := strings.TrimSpace(body.Type)
	if dtype == "" {
		dtype = "ban"
	}
	if dtype != "ban" && dtype != "captcha" && dtype != "bypass" {
		jsonErrorCode(w, "invalid_type", nil, "Invalid type", http.StatusBadRequest)
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
		"source":    map[string]any{"ip": ip, "scope": "Ip", "value": ip},
		"start_at":  now, "stop_at": now,
	}}
	buf, _ := json.Marshal(payload)
	resp, err := a.csRequest(r.Context(), http.MethodPost, "/v1/alerts", bytes.NewReader(buf), true)
	if err != nil {
		jsonErrorCode(w, "crowdsec_unavailable", map[string]any{"detail": err.Error()}, "crowdsec unavailable: "+err.Error(), http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()
	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		b, _ := io.ReadAll(resp.Body)
		jsonErrorCode(w, "decision_add_failed", map[string]any{"detail": strings.TrimSpace(string(b))}, "failed to add decision: "+strings.TrimSpace(string(b)), resp.StatusCode)
		return
	}
	csCacheReset()
	csAlertCacheReset()
	jsonOK(w, map[string]any{"ok": true})
}

func (a *App) crowdsecProxy(w http.ResponseWriter, r *http.Request, method, csPath string) {
	if a.cfg.CrowdSecLAPIURL == "" {
		jsonErrorCode(w, "crowdsec_missing", nil, "CROWDSEC_LAPI_URL not configured", http.StatusNotFound)
		return
	}
	resp, err := a.csRequest(r.Context(), method, csPath, r.Body, true)
	if err != nil {
		jsonErrorCode(w, "crowdsec_unavailable", map[string]any{"detail": err.Error()}, "crowdsec unavailable: "+err.Error(), http.StatusBadGateway)
		return
	}
	defer resp.Body.Close()
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(resp.StatusCode)
	io.Copy(w, resp.Body)
}

func (a *App) backupDir() string {
	return filepath.Join(a.cfg.BackupDir, "backups")
}

func safeBaseName(name string) (string, bool) {
	if name == "" || name == "." || name == ".." {
		return "", false
	}
	if strings.ContainsAny(name, "/\\\x00") || strings.Contains(name, "..") {
		return "", false
	}
	if filepath.Base(name) != name {
		return "", false
	}
	return name, true
}

func (a *App) createFileBak(targetPath, name string) error {
	data, err := os.ReadFile(targetPath)
	if err != nil {
		return nil
	}
	base := name
	if base == "" {
		base = filepath.Base(targetPath)
	}
	if _, ok := safeBaseName(base); !ok {
		return fmt.Errorf("unsafe backup name %q", base)
	}
	dir := a.backupDir()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	ts := time.Now().UTC().Format("20060102_150405")
	dest := filepath.Join(dir, base+"."+ts+".bak")
	if rel, err := filepath.Rel(dir, dest); err != nil || strings.ContainsRune(rel, filepath.Separator) {
		return fmt.Errorf("unsafe backup name %q", base)
	}
	if err := os.WriteFile(dest, data, 0o644); err != nil {
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
		Kind string `json:"kind"`
	}
	staticBase := ""
	if a.cfg.StaticConfigPath != "" {
		staticBase = filepath.Base(a.cfg.StaticConfigPath)
	}
	certNames := map[string]bool{}
	for path, key := range acmeBackupKeys(acmeJSONPaths(a.cfg.ACMEJSONPath)) {
		certNames[key] = true
		certNames[filepath.Base(path)] = true
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
		kind := "routes"
		if base := bakBaseName(n); certNames[base] {
			kind = "certs"
		} else if staticBase != "" && base == staticBase {
			kind = "static"
		}
		list = append(list, backup{Name: n, Size: size, Date: date, Kind: kind})
	}
	jsonOK(w, map[string]any{"backups": list, "static_configured": a.cfg.StaticConfigPath != ""})
}

func (a *App) backupCreateHandler(w http.ResponseWriter, r *http.Request) {
	names, err := a.createBackup()
	if err != nil {
		jsonErrorCode(w, "backup_failed", map[string]any{"detail": err.Error()}, "backup failed: "+err.Error(), http.StatusInternalServerError)
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
	if _, ok := safeBaseName(filename); !ok || !strings.HasSuffix(filename, ".bak") {
		jsonErrorCode(w, "invalid_file_name", nil, "invalid filename", http.StatusBadRequest)
		return
	}
	bakPath := filepath.Join(a.backupDir(), filename)
	data, err := os.ReadFile(bakPath)
	if err != nil {
		jsonErrorCode(w, "backup_unreadable", map[string]any{"detail": err.Error()}, "cannot read backup: "+err.Error(), http.StatusNotFound)
		return
	}
	origName := bakBaseName(filename)
	sameName := 0
	for path, key := range acmeBackupKeys(acmeJSONPaths(a.cfg.ACMEJSONPath)) {
		if key == origName {
			a.restoreCertStore(w, r, path, data)
			return
		}
		if filepath.Base(path) == origName {
			sameName++
		}
	}
	if sameName > 1 {
		jsonErrorCode(w, "acme_store_ambiguous", map[string]any{"file": origName}, origName+" matches more than one certificate store, so this backup cannot be restored safely", http.StatusConflict)
		return
	}
	var dest string
	if a.cfg.StaticConfigPath != "" && origName == filepath.Base(a.cfg.StaticConfigPath) {
		dest = a.cfg.StaticConfigPath
	} else {
		cfgPath := a.cfg.ConfigPath
		info, _ := os.Stat(cfgPath)
		isDir := info != nil && info.IsDir()
		if !dynamicConfigName(origName) && (isDir || origName != filepath.Base(cfgPath)) {
			jsonErrorCode(w, "no_config_match", map[string]any{"file": origName}, "no config file matches "+origName, http.StatusBadRequest)
			return
		}
		if isDir {
			dest = filepath.Join(cfgPath, origName)
		} else {
			dest = cfgPath
		}
	}
	a.cfgMu.Lock()
	defer a.cfgMu.Unlock()
	if err := a.createFileBak(dest, origName); err != nil {
		a.failuref("backup", "pre-restore backup of %s failed: %v", dest, err)
		jsonErrorCode(w, "backup_failed_nothing_restored", map[string]any{"detail": err.Error()}, "backup failed, nothing was restored: "+err.Error(), http.StatusInternalServerError)
		return
	}
	if err := atomicWrite(dest, data); err != nil {
		jsonErrorCode(w, "restore_failed", map[string]any{"detail": err.Error()}, "restore failed: "+err.Error(), http.StatusInternalServerError)
		return
	}
	jsonOK(w, map[string]any{"ok": true})
}

func (a *App) restoreCertStore(w http.ResponseWriter, r *http.Request, path string, data []byte) {
	restart := a.cfg.RestartMethod == "proxy" || a.cfg.RestartMethod == "socket" || a.cfg.RestartMethod == "poison-pill"
	if !restart {
		jsonErrorCode(w, "acme_needs_restart", nil, "no RESTART_METHOD is configured on this agent, and Traefik only reads acme.json at startup", http.StatusForbidden)
		return
	}
	if trimmed := bytes.TrimSpace(data); len(trimmed) > 0 && !json.Valid(trimmed) {
		jsonErrorCode(w, "backup_not_json", nil, "this backup is not valid JSON, nothing was restored", http.StatusBadRequest)
		return
	}
	acmeMu.Lock()
	defer acmeMu.Unlock()
	if !acmeWritable(path) {
		jsonErrorCode(w, "read_only_not_restored", map[string]any{"file": filepath.Base(path)}, filepath.Base(path)+" is mounted read only on this agent, nothing was restored", http.StatusForbidden)
		return
	}
	current, err := os.ReadFile(path)
	if err != nil {
		jsonErrorCode(w, "file_unreadable", map[string]any{"file": filepath.Base(path), "detail": err.Error()}, "could not read "+filepath.Base(path)+": "+err.Error(), http.StatusInternalServerError)
		return
	}
	if _, err := acmeBackupBytes(path, current, a); err != nil {
		a.failuref("backup", "pre-restore backup of %s failed: %v", path, err)
		jsonErrorCode(w, "backup_failed_nothing_restored", map[string]any{"detail": err.Error()}, "backup failed, nothing was restored: "+err.Error(), http.StatusInternalServerError)
		return
	}
	if err := acmeWriteInPlace(path, data, current); err != nil {
		status := http.StatusInternalServerError
		if _, changed := err.(acmeChangedError); changed {
			status = http.StatusConflict
		}
		jsonErrorCode(w, "restore_failed", map[string]any{"detail": err.Error()}, "restore failed: "+err.Error(), status)
		return
	}
	restarted := a.restartAfterCertChange(r)
	jsonOK(w, map[string]any{"ok": true, "restarted": restarted})
}

func (a *App) backupDeleteHandler(w http.ResponseWriter, r *http.Request) {
	filename := strings.TrimPrefix(r.URL.Path, "/api/backup/delete/")
	if _, ok := safeBaseName(filename); !ok || !strings.HasSuffix(filename, ".bak") {
		jsonErrorCode(w, "invalid_file_name", nil, "invalid filename", http.StatusBadRequest)
		return
	}
	path := filepath.Join(a.backupDir(), filename)
	if err := os.Remove(path); err != nil {
		jsonErrorCode(w, "delete_failed", map[string]any{"detail": err.Error()}, "delete failed: "+err.Error(), http.StatusInternalServerError)
		return
	}
	jsonOK(w, map[string]any{"ok": true})
}

func (a *App) gitRepoDir() string {
	return filepath.Join(a.cfg.BackupDir, "git-repo")
}

type gitCreds struct {
	username string
	token    string
}

func validGitURL(u string) bool {
	l := strings.ToLower(u)
	return strings.HasPrefix(l, "https://") ||
		strings.HasPrefix(l, "http://") ||
		strings.HasPrefix(l, "ssh://") ||
		strings.HasPrefix(l, "git://")
}

func ssrfOK(raw string) bool {
	u, err := url.Parse(raw)
	if err != nil || u.Hostname() == "" {
		return false
	}
	ips, err := net.LookupIP(u.Hostname())
	if err != nil || len(ips) == 0 {
		return false
	}
	for _, ip := range ips {
		if ip.IsLinkLocalUnicast() || ip.IsLinkLocalMulticast() || ip.IsInterfaceLocalMulticast() || ip.IsMulticast() || ip.IsUnspecified() {
			return false
		}
		if v4 := ip.To4(); v4 != nil && v4[0] >= 240 {
			return false
		}
	}
	return true
}

func sameGitRemote(a, b string) bool {
	if a == "" || b == "" {
		return false
	}
	return strings.EqualFold(strings.TrimRight(a, "/"), strings.TrimRight(b, "/"))
}

func (a *App) gitAskpassScript() (string, error) {
	path := filepath.Join(a.cfg.BackupDir, ".git-askpass.sh")
	if _, err := os.Stat(path); err == nil {
		return path, nil
	}
	if err := os.MkdirAll(a.cfg.BackupDir, 0o755); err != nil {
		return "", err
	}
	script := "#!/bin/sh\ncase \"$1\" in\n*Username*) printf '%s' \"$GIT_ASKPASS_USER\" ;;\n*) printf '%s' \"$GIT_ASKPASS_PASS\" ;;\nesac\n"
	if err := os.WriteFile(path, []byte(script), 0o700); err != nil {
		return "", err
	}
	return path, nil
}

func (a *App) gitRun(args []string, cwd string, creds ...gitCreds) (string, string, int) {
	full := append([]string{"-c", "protocol.ext.allow=never", "-c", "protocol.file.allow=user", "-c", "protocol.fd.allow=user", "-c", "credential.helper="}, args...)
	cmd := exec.Command("git", full...)
	if cwd == "" {
		cwd = a.gitRepoDir()
	}
	cmd.Dir = cwd
	cmd.Env = append(os.Environ(), "GIT_TERMINAL_PROMPT=0")
	if len(creds) > 0 && creds[0].token != "" {
		if script, err := a.gitAskpassScript(); err == nil {
			cmd.Env = append(cmd.Env,
				"GIT_ASKPASS="+script,
				"GIT_ASKPASS_USER="+creds[0].username,
				"GIT_ASKPASS_PASS="+creds[0].token,
			)
		}
	}
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

func (a *App) gitEnsureRepo() (string, error) {
	repoDir := a.gitRepoDir()
	gitDir := filepath.Join(repoDir, ".git")
	branch := a.cfg.GitBackupBranch
	repoURL := a.cfg.GitBackupRepo
	if !validGitURL(repoURL) {
		return "", fmt.Errorf("invalid repository URL scheme")
	}
	creds := gitCreds{username: a.cfg.GitBackupUsername, token: a.cfg.GitBackupToken}

	if _, err := os.Stat(gitDir); os.IsNotExist(err) {
		if entries, err := os.ReadDir(repoDir); err == nil && len(entries) > 0 {
			os.RemoveAll(repoDir)
			log.Printf("git repo dir was non-empty without .git - cleared for fresh clone")
		}
		if err := os.MkdirAll(repoDir, 0o755); err != nil {
			return "", err
		}
		_, _, rc := a.gitRun([]string{"clone", "--branch", branch, "--", repoURL, "."}, repoDir, creds)
		if rc != 0 {
			a.gitRun([]string{"init"}, repoDir)
			a.gitRun([]string{"remote", "add", "origin", repoURL}, repoDir)
			a.gitRun([]string{"config", "user.email", "traefik-manager-agent@localhost"}, repoDir)
			a.gitRun([]string{"config", "user.name", "Traefik Manager Agent"}, repoDir)
			a.gitRun([]string{"pull", "origin", branch}, repoDir, creds)
		}
	} else {
		a.gitRun([]string{"remote", "set-url", "origin", repoURL}, repoDir)
		a.gitRun([]string{"config", "user.email", "traefik-manager-agent@localhost"}, repoDir)
		a.gitRun([]string{"config", "user.name", "Traefik Manager Agent"}, repoDir)
	}
	return repoDir, nil
}

func (a *App) gitPush(action string, customMsg string) error {
	if a.cfg.GitBackupRepo == "" {
		return fmt.Errorf("no repository configured")
	}
	if !validGitURL(a.cfg.GitBackupRepo) {
		return fmt.Errorf("invalid repository URL scheme")
	}
	repoDir, err := a.gitEnsureRepo()
	if err != nil {
		return fmt.Errorf("repo init failed: %w", err)
	}
	dynDir := filepath.Join(repoDir, "dynamic")
	staticDir := filepath.Join(repoDir, "static")

	ts := time.Now().Format("2006-01-02 15:04:05")
	msg := strings.NewReplacer("{action}", action, "{timestamp}", ts).Replace(a.cfg.GitBackupCommitMsg)
	if strings.TrimSpace(customMsg) != "" {
		msg = strings.TrimSpace(customMsg)
	}

	creds := gitCreds{username: a.cfg.GitBackupUsername, token: a.cfg.GitBackupToken}
	var errOut string
	for attempt := 0; attempt < 2; attempt++ {
		_, _, frc := a.gitRun([]string{"fetch", "origin", a.cfg.GitBackupBranch}, repoDir, creds)
		if frc == 0 {
			a.gitRun([]string{"reset", "--hard", "FETCH_HEAD"}, repoDir)
		}
		a.gitStage(dynDir, staticDir)
		a.gitRun([]string{"add", "-A"}, repoDir)
		_, _, rc := a.gitRun([]string{"diff", "--cached", "--quiet"}, repoDir)
		if rc == 0 {
			return nil
		}
		var commitErr string
		_, commitErr, rc = a.gitRun([]string{"commit", "-m", msg}, repoDir)
		if rc != 0 {
			return fmt.Errorf("commit failed: %s", commitErr)
		}
		_, errOut, rc = a.gitRun([]string{"push", "-u", "origin", a.cfg.GitBackupBranch}, repoDir, creds)
		if rc == 0 {
			log.Printf("git backup pushed: %s", msg)
			return nil
		}
	}
	token := a.cfg.GitBackupToken
	if token != "" {
		errOut = strings.ReplaceAll(errOut, token, "***")
	}
	return fmt.Errorf("push failed: %s", errOut)
}

func (a *App) gitStage(dynDir, staticDir string) {
	os.MkdirAll(dynDir, 0o755)
	os.MkdirAll(staticDir, 0o755)
	stores := map[string]bool{}
	for _, p := range acmeJSONPaths(a.cfg.ACMEJSONPath) {
		stores[filepath.Base(p)] = true
	}
	copyFile := func(src, destDir string) {
		if data, err := os.ReadFile(src); err == nil {
			os.WriteFile(filepath.Join(destDir, filepath.Base(src)), data, 0o644)
		}
	}
	if info, err := os.Stat(a.cfg.ConfigPath); err == nil {
		if info.IsDir() {
			entries, _ := os.ReadDir(a.cfg.ConfigPath)
			for _, e := range entries {
				if !e.IsDir() && dynamicConfigName(e.Name()) && !stores[e.Name()] {
					copyFile(filepath.Join(a.cfg.ConfigPath, e.Name()), dynDir)
				}
			}
		} else if !stores[filepath.Base(a.cfg.ConfigPath)] {
			copyFile(a.cfg.ConfigPath, dynDir)
		}
	}
	if a.cfg.StaticConfigPath != "" {
		copyFile(a.cfg.StaticConfigPath, staticDir)
	}
}

func dynamicConfigName(name string) bool {
	lower := strings.ToLower(name)
	return strings.HasSuffix(lower, ".yml") || strings.HasSuffix(lower, ".yaml") || strings.HasSuffix(lower, ".toml")
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
	if token == "" && sameGitRemote(repo, a.cfg.GitBackupRepo) {
		token = a.cfg.GitBackupToken
	}
	if repo == "" {
		jsonErrorCode(w, "git_no_repo", nil, "no repository URL configured", http.StatusBadRequest)
		return
	}
	if !validGitURL(repo) {
		jsonErrorCode(w, "git_bad_scheme", nil, "invalid repository URL scheme", http.StatusBadRequest)
		return
	}
	if !ssrfOK(repo) {
		jsonErrorCode(w, "target_not_allowed", nil, "target address not allowed", http.StatusBadRequest)
		return
	}
	tmpDir, err := os.MkdirTemp("", "tma-git-test-*")
	if err != nil {
		jsonErrorCode(w, "internal_error", nil, "internal error", http.StatusInternalServerError)
		return
	}
	defer os.RemoveAll(tmpDir)
	creds := gitCreds{username: username, token: token}
	_, errOut, rc := a.gitRun([]string{"-c", "http.followRedirects=false", "ls-remote", "--quiet", "--", repo}, tmpDir, creds)
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
		jsonErrorCode(w, "invalid_sha", nil, "invalid sha", http.StatusBadRequest)
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
		jsonErrorCode(w, "diff_failed", nil, "diff failed", http.StatusInternalServerError)
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

type gitRestoreItem struct {
	repoPath string
	dest     string
}

func (a *App) gitRestoreTargets(repoDir, sha string) ([]gitRestoreItem, bool) {
	listed, _, rc := a.gitRun([]string{"ls-tree", "-r", "--name-only", sha}, repoDir)
	if rc != 0 {
		return nil, false
	}
	var paths []string
	inCommit := map[string]bool{}
	for _, line := range strings.Split(listed, "\n") {
		if line = strings.TrimSpace(line); line != "" {
			paths = append(paths, line)
			inCommit[line] = true
		}
	}
	first := func(names ...string) string {
		for _, name := range names {
			if inCommit[name] {
				return name
			}
		}
		return ""
	}
	var items []gitRestoreItem
	cfgPath := a.cfg.ConfigPath
	if info, err := os.Stat(cfgPath); err == nil && info.IsDir() {
		for _, p := range paths {
			if !strings.HasPrefix(p, "dynamic/") {
				continue
			}
			name := strings.TrimPrefix(p, "dynamic/")
			if _, ok := safeBaseName(name); !ok || !dynamicConfigName(name) {
				continue
			}
			items = append(items, gitRestoreItem{repoPath: p, dest: filepath.Join(cfgPath, name)})
		}
	} else if cfgPath != "" {
		base := filepath.Base(cfgPath)
		if src := first("dynamic/"+base, base); src != "" {
			items = append(items, gitRestoreItem{repoPath: src, dest: cfgPath})
		}
	}
	if a.cfg.StaticConfigPath != "" {
		base := filepath.Base(a.cfg.StaticConfigPath)
		if src := first("static/"+base, base); src != "" {
			items = append(items, gitRestoreItem{repoPath: src, dest: a.cfg.StaticConfigPath})
		}
	}
	return items, true
}

func (a *App) gitRestoreHandler(w http.ResponseWriter, r *http.Request, sha string) {
	if !shaRe.MatchString(sha) {
		jsonErrorCode(w, "invalid_sha", nil, "invalid sha", http.StatusBadRequest)
		return
	}
	a.cfgMu.Lock()
	defer a.cfgMu.Unlock()
	repoDir := a.gitRepoDir()
	if _, err := os.Stat(filepath.Join(repoDir, ".git")); err != nil {
		jsonErrorCode(w, "git_not_initialized", nil, "git repo not initialized", http.StatusBadRequest)
		return
	}
	items, found := a.gitRestoreTargets(repoDir, sha)
	if !found {
		jsonErrorCode(w, "commit_not_found", nil, "commit not found", http.StatusNotFound)
		return
	}
	if len(items) == 0 {
		jsonErrorCode(w, "commit_no_configs", nil, "the commit holds no config files for this agent", http.StatusNotFound)
		return
	}
	if _, err := a.createBackup(); err != nil {
		a.failuref("backup", "pre-restore backup failed: %v", err)
		jsonErrorCode(w, "backup_failed_nothing_restored", map[string]any{"detail": err.Error()}, "backup failed, nothing was restored: "+err.Error(), http.StatusInternalServerError)
		return
	}
	for _, item := range items {
		content, _, rc := a.gitRun([]string{"show", sha + ":" + item.repoPath}, repoDir)
		var err error
		if rc != 0 {
			err = fmt.Errorf("cannot read it from the commit")
		} else {
			err = atomicWrite(item.dest, []byte(content))
		}
		if err != nil {
			a.failuref("git", "restore of %s stopped at %s: %v", sha, item.repoPath, err)
			jsonErrorCode(w, "restore_stopped", map[string]any{"file": item.repoPath, "detail": err.Error()}, "restore stopped at "+item.repoPath+": "+err.Error()+". A backup was taken before the restore", http.StatusInternalServerError)
			return
		}
	}
	jsonOK(w, map[string]any{"ok": true, "restored": len(items)})
}

func acmeJSONPaths(raw string) []string {
	var out []string
	seen := map[string]bool{}
	add := func(p string) {
		if p != "" && !seen[p] {
			seen[p] = true
			out = append(out, p)
		}
	}
	for _, part := range strings.Split(raw, ",") {
		part = strings.TrimSpace(part)
		if part == "" {
			continue
		}
		if info, err := os.Stat(part); err == nil && info.IsDir() {
			entries, err := os.ReadDir(part)
			if err != nil {
				continue
			}
			var names []string
			for _, e := range entries {
				if !e.IsDir() && strings.HasSuffix(e.Name(), ".json") {
					names = append(names, e.Name())
				}
			}
			sort.Strings(names)
			for _, n := range names {
				add(filepath.Join(part, n))
			}
			continue
		}
		add(part)
	}
	return out
}

type certEntry struct {
	Resolver string   `json:"resolver"`
	Main     string   `json:"main"`
	Sans     []string `json:"sans"`
	NotAfter *string  `json:"not_after"`
	Source   string   `json:"source"`
}

func (a *App) certsHandler(w http.ResponseWriter, r *http.Request) {
	var certs []certEntry
	var errs []string

	paths := acmeJSONPaths(a.cfg.ACMEJSONPath)
	if len(paths) == 0 {
		jsonOK(w, map[string]any{"certs": []any{}, "error": "ACME_JSON_PATH not configured", "code": "acme_path_missing"})
		return
	}

	for _, path := range paths {
		source := filepath.Base(path)
		data, err := os.ReadFile(path)
		if os.IsPermission(err) {
			errs = append(errs, "Permission denied reading "+path+". Run the agent as the user that owns it, do not chmod it.")
			continue
		}
		if err != nil {
			errs = append(errs, "acme.json not found at "+path)
			continue
		}
		var acme map[string]any
		if len(strings.TrimSpace(string(data))) == 0 {
			continue
		}
		if err := json.Unmarshal(data, &acme); err != nil {
			errs = append(errs, "failed to parse "+source)
			continue
		}
		collectCerts(acme, source, &certs)
	}

	if certs == nil {
		certs = []certEntry{}
	}
	resp := map[string]any{"certs": certs}
	if len(certs) == 0 && len(errs) > 0 {
		resp["error"] = strings.Join(errs, " | ")
	}
	jsonOK(w, resp)
}

func collectCerts(acme map[string]any, source string, certs *[]certEntry) {
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
			*certs = append(*certs, certEntry{Resolver: resolverName, Main: main, Sans: sans, NotAfter: notAfter, Source: source})
		}
	}
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
		if _, ok := safeBaseName(cf); !ok {
			jsonErrorCode(w, "invalid_config_file", nil, "invalid config file", http.StatusBadRequest)
			return
		}
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
			svc := services[svcName]
			if svc != nil {
				out[proto].(map[string]any)["services"] = map[string]any{svcName: svc}
			}
			origins := a.addRouteDependencies(out, config, proto, routerMap, svc, p)
			raw, err := yaml.Marshal(out)
			if err != nil {
				jsonErrorCode(w, "yaml_marshal_failed", nil, "failed to marshal YAML", http.StatusInternalServerError)
				return
			}
			jsonOK(w, map[string]any{"raw": string(raw), "configFile": filepath.Base(p), "proto": proto,
				"origins": origins, "fingerprints": a.dependencyFingerprints(origins, p),
				"warnings": a.definitionReferenceWarnings(out, origins, config, p)})
			return
		}
	}
	jsonErrorCode(w, "route_not_found", nil, "Route not found", http.StatusNotFound)
}

func (a *App) routeRawSaveHandler(w http.ResponseWriter, r *http.Request, routeID string) {
	var body struct {
		Content      string            `json:"content"`
		ApplyShared  bool              `json:"applyShared"`
		ApplyRename  bool              `json:"applyRename"`
		Fingerprints map[string]string `json:"fingerprints"`
	}
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || strings.TrimSpace(body.Content) == "" {
		jsonErrorCode(w, "invalid_body", nil, "invalid request body", http.StatusBadRequest)
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
		jsonErrorCode(w, "invalid_yaml", map[string]any{"detail": err.Error()}, "invalid YAML: "+err.Error(), http.StatusBadRequest)
		return
	}

	a.cfgMu.Lock()
	defer a.cfgMu.Unlock()

	var targetPath string
	if cf != "" {
		if _, ok := safeBaseName(cf); !ok {
			jsonErrorCode(w, "invalid_config_file", nil, "invalid config file", http.StatusBadRequest)
			return
		}
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
		jsonErrorCode(w, "route_not_found", nil, "Route not found", http.StatusNotFound)
		return
	}

	data, _ := os.ReadFile(targetPath)
	var config map[string]any
	yaml.Unmarshal(data, &config)
	if config == nil {
		config = map[string]any{}
	}

	if name, file := a.renamedSharedDefinition(newData, config, targetPath); name != "" {
		jsonErrorCode(w, "shared_definition_renamed", map[string]any{"name": name, "file": file},
			"renaming "+name+" here would leave it behind in "+file, http.StatusConflict)
		return
	}

	if copied := a.renamedCopy(newData, config, targetPath, rname); copied != nil && !body.ApplyRename {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusConflict)
		json.NewEncoder(w).Encode(map[string]any{"ok": false, "renamedCopy": copied})
		return
	}

	unchangedShared, changedShared := a.sectionsDefinedElsewhere(newData, config, targetPath)
	for _, change := range changedShared {
		if err := writableFile(change.Path); err != nil {
			jsonErrorCode(w, "shared_definition_read_only",
				map[string]any{"name": change.Dep.Name, "file": change.File},
				change.Dep.Name+" is defined in "+change.File+", which is read-only here",
				http.StatusConflict)
			return
		}
		if was := body.Fingerprints[change.File]; was != "" && was != fileFingerprint(change.Path) {
			jsonErrorCode(w, "shared_file_changed", map[string]any{"file": change.File},
				change.File+" changed on disk since this editor opened", http.StatusConflict)
			return
		}
	}
	if missing := a.missingRouteReferences(newData, config, targetPath, unchangedShared); len(missing) > 0 {
		name := missing[0].Name
		params := map[string]any{"name": name}
		tail := " is not defined anywhere. Create it first, or correct the name."
		switch missing[0].Kind {
		case "services":
			jsonErrorCode(w, "service_not_defined", params, "The service "+name+tail, http.StatusConflict)
		case "serversTransports":
			jsonErrorCode(w, "transport_not_defined", params, "The serversTransport "+name+tail, http.StatusConflict)
		case "options":
			jsonErrorCode(w, "tls_options_not_defined", params,
				"The TLS options "+name+" are not defined anywhere. Create them first, or correct the name.",
				http.StatusConflict)
		default:
			jsonErrorCode(w, "middleware_not_defined", params, "The middleware "+name+tail, http.StatusConflict)
		}
		return
	}

	if len(changedShared) > 0 && !body.ApplyShared {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusConflict)
		json.NewEncoder(w).Encode(map[string]any{
			"ok": false, "needsConfirm": true, "sharedChanges": a.sharedChangePrompt(changedShared),
		})
		return
	}
	for _, change := range append(unchangedShared, changedShared...) {
		delete(sectionMap(newData, change.Dep.Scope, change.Dep.Kind), change.Dep.Name)
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
		for _, kind := range []string{"serversTransports", "middlewares"} {
			edited, _ := newProto[kind].(map[string]any)
			if len(edited) == 0 {
				continue
			}
			existing, _ := section[kind].(map[string]any)
			if existing == nil {
				existing = map[string]any{}
			}
			for k, v := range edited {
				existing[k] = v
			}
			section[kind] = existing
		}
	}

	if newOptions := sectionMap(newData, "tls", "options"); len(newOptions) > 0 {
		scoped, _ := config["tls"].(map[string]any)
		if scoped == nil {
			scoped = map[string]any{}
			config["tls"] = scoped
		}
		existing, _ := scoped["options"].(map[string]any)
		if existing == nil {
			existing = map[string]any{}
		}
		for k, v := range newOptions {
			existing[k] = v
		}
		scoped["options"] = existing
	}

	if len(changedShared) > 0 {
		if err := a.writeSharedDefinitions(changedShared); err != nil {
			a.failuref("config", "writing shared definitions failed: %v", err)
			jsonErrorCode(w, "write_failed", map[string]any{"detail": err.Error()}, "write failed: "+err.Error(), http.StatusInternalServerError)
			return
		}
	}

	if err := a.createFileBak(targetPath, filepath.Base(targetPath)); err != nil {
		a.failuref("backup", "pre-write backup of %s failed: %v", targetPath, err)
		jsonErrorCode(w, "backup_failed_nothing_written", map[string]any{"detail": err.Error()}, "backup failed, nothing was written: "+err.Error(), http.StatusInternalServerError)
		return
	}
	out, err := yaml.Marshal(config)
	if err != nil {
		jsonErrorCode(w, "yaml_marshal_failed", nil, "failed to marshal YAML", http.StatusInternalServerError)
		return
	}
	if err := atomicWrite(targetPath, out); err != nil {
		jsonErrorCode(w, "write_failed", map[string]any{"detail": err.Error()}, "write failed: "+err.Error(), http.StatusInternalServerError)
		return
	}
	if a.cfg.GitBackupEnabled && a.cfg.GitBackupAutoPush && a.cfg.GitBackupRepo != "" {
		go func() {
			if err := a.gitPush("route raw save", ""); err != nil {
				a.failuref("git", "auto-push failed: %v", err)
			}
		}()
	}
	jsonOK(w, map[string]any{"ok": true})
}

func (a *App) logsHandler(w http.ResponseWriter, r *http.Request) {
	linesReq := 100
	if values, present := r.URL.Query()["lines"]; present {
		n, err := strconv.Atoi(strings.TrimSpace(values[0]))
		if err != nil || n < 1 {
			jsonErrorCode(w, "invalid_lines", nil, "Invalid lines parameter", http.StatusBadRequest)
			return
		}
		linesReq = n
		if linesReq > 1000 {
			linesReq = 1000
		}
	}
	if a.cfg.AccessLogPath == "" {
		jsonOK(w, map[string]any{"error": "ACCESS_LOG_PATH not configured", "code": "access_log_missing", "lines": []any{}})
		return
	}
	f, err := os.Open(a.cfg.AccessLogPath)
	if err != nil {
		jsonOK(w, map[string]any{"error": "Access log not found at " + a.cfg.AccessLogPath, "code": "access_log_not_found", "params": map[string]any{"path": a.cfg.AccessLogPath}, "lines": []any{}})
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
		jsonErrorCode(w, "reset_failed", map[string]any{"detail": err.Error()}, "reset failed: "+err.Error(), http.StatusInternalServerError)
		return
	}
	log.Printf("git repo directory reset by user")
	jsonOK(w, map[string]any{"ok": true})
}

type csStreamCache struct {
	mu    sync.Mutex
	items map[int64]json.RawMessage
	fp    string
	ready bool
	sync  time.Time
}

var csCache = &csStreamCache{items: map[int64]json.RawMessage{}}

const csStreamResync = time.Hour

func (a *App) csFingerprint() string {
	sum := sha256.Sum256([]byte(a.cfg.CrowdSecLAPIURL + "|" + a.cfg.CrowdSecAPIKey + "|" + a.cfg.CrowdSecClientCert))
	return hex.EncodeToString(sum[:8])
}

type csStreamPayload struct {
	New     []json.RawMessage `json:"new"`
	Deleted []json.RawMessage `json:"deleted"`
}

func decID(raw json.RawMessage) int64 {
	var d struct {
		ID int64 `json:"id"`
	}
	if err := json.Unmarshal(raw, &d); err != nil {
		return 0
	}
	return d.ID
}

func csCacheReset() {
	csCache.mu.Lock()
	defer csCache.mu.Unlock()
	csCache.items = map[int64]json.RawMessage{}
	csCache.ready = false
	csCache.sync = time.Time{}
}

func (a *App) csDecisionsStream(ctx context.Context, forceFull bool) ([]json.RawMessage, string, error) {
	fp := a.csFingerprint()
	csCache.mu.Lock()
	defer csCache.mu.Unlock()

	full := forceFull || !csCache.ready || csCache.fp != fp ||
		(!csCache.sync.IsZero() && time.Since(csCache.sync) > csStreamResync)
	path := "/v1/decisions/stream"
	if full {
		path += "?startup=true"
	}
	resp, err := a.csRequest(ctx, http.MethodGet, path, nil, false)
	if err != nil {
		if csCache.ready && csCache.fp == fp {
			return csCacheItems(), csStaleMode(csCacheDecisionAge(), err), nil
		}
		return nil, "", err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		lapiErr := fmt.Errorf("LAPI %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
		if csCache.ready && csCache.fp == fp && resp.StatusCode >= 500 {
			return csCacheItems(), csStaleMode(csCacheDecisionAge(), lapiErr), nil
		}
		return nil, "", lapiErr
	}
	var payload csStreamPayload
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		return nil, "", fmt.Errorf("LAPI 404: stream payload not understood: %w", err)
	}
	if full {
		csCache.items = map[int64]json.RawMessage{}
	}
	for _, raw := range payload.New {
		if id := decID(raw); id != 0 {
			csCache.items[id] = raw
		}
	}
	for _, raw := range payload.Deleted {
		if id := decID(raw); id != 0 {
			delete(csCache.items, id)
		}
	}
	csCache.fp = fp
	csCache.ready = true
	csCache.sync = time.Now()
	if full {
		return csCacheItems(), "full", nil
	}
	return csCacheItems(), "delta", nil
}

func csCacheDecisionAge() time.Duration {
	if csCache.sync.IsZero() {
		return 0
	}
	return time.Since(csCache.sync)
}

func csCacheItems() []json.RawMessage {
	out := make([]json.RawMessage, 0, len(csCache.items))
	for _, v := range csCache.items {
		out = append(out, v)
	}
	return out
}

var csStreamable = true

const csStaleAfter = 15 * time.Minute

func csStaleMode(age time.Duration, err error) string {
	if age >= csStaleAfter {
		return fmt.Sprintf("stale:%d:%s", int(age.Seconds()), err.Error())
	}
	return "cache"
}

func csStaleNoteFromMode(mode string) string {
	if !strings.HasPrefix(mode, "stale:") {
		return ""
	}
	parts := strings.SplitN(mode, ":", 3)
	if len(parts) != 3 {
		return "CrowdSec has not answered recently, so these decisions are the last ones read and may be out of date."
	}
	return fmt.Sprintf("CrowdSec has not answered for %ss, so these decisions are the last ones read and may be "+
		"out of date. %s", parts[1], parts[2])
}

func csTruthy(v string) bool {
	v = strings.ToLower(strings.TrimSpace(v))
	return v == "1" || v == "true" || v == "yes"
}

func csFilterActive(rows []json.RawMessage, now time.Time) []json.RawMessage {
	active := make([]json.RawMessage, 0, len(rows))
	for _, raw := range rows {
		var d struct {
			Until string `json:"until"`
		}
		if json.Unmarshal(raw, &d) == nil && d.Until != "" {
			if exp, err := time.Parse(time.RFC3339, strings.Replace(d.Until, "Z", "+00:00", 1)); err == nil && exp.Before(now) {
				continue
			}
		}
		active = append(active, raw)
	}
	return active
}

type csAlertCacheData struct {
	mu     sync.Mutex
	items  map[int64]json.RawMessage
	fp     string
	limit  int
	ready  bool
	synced time.Time
}

var csAlertCache = &csAlertCacheData{items: map[int64]json.RawMessage{}}

const csAlertFreshWindow = 5 * time.Second

func csAlertCacheReset() {
	csAlertCache.mu.Lock()
	defer csAlertCache.mu.Unlock()
	csAlertCache.items = map[int64]json.RawMessage{}
	csAlertCache.fp = ""
	csAlertCache.limit = 0
	csAlertCache.ready = false
	csAlertCache.synced = time.Time{}
}

func csAlertItems() []json.RawMessage {
	out := make([]json.RawMessage, 0, len(csAlertCache.items))
	for _, v := range csAlertCache.items {
		out = append(out, v)
	}
	sort.Slice(out, func(i, j int) bool { return decID(out[i]) > decID(out[j]) })
	return out
}

func csAlertTrimToLimit(limit int) {
	if limit <= 0 || len(csAlertCache.items) <= limit {
		return
	}
	ids := make([]int64, 0, len(csAlertCache.items))
	for id := range csAlertCache.items {
		ids = append(ids, id)
	}
	sort.Slice(ids, func(i, j int) bool { return ids[i] > ids[j] })
	keep := make(map[int64]json.RawMessage, limit)
	for _, id := range ids[:limit] {
		keep[id] = csAlertCache.items[id]
	}
	csAlertCache.items = keep
}

func (a *App) csAlerts(ctx context.Context, limit int, forceFull bool) ([]json.RawMessage, string, int, error) {
	fp := a.csFingerprint()
	csAlertCache.mu.Lock()
	defer csAlertCache.mu.Unlock()

	now := time.Now()
	age := time.Duration(0)
	if !csAlertCache.synced.IsZero() {
		age = now.Sub(csAlertCache.synced)
	}
	readyForFP := csAlertCache.ready && csAlertCache.fp == fp && csAlertCache.limit == limit

	if !forceFull && readyForFP && age < csAlertFreshWindow {
		return csAlertItems(), "cache", 200, nil
	}

	full := forceFull || !readyForFP || age > csStreamResync
	path := fmt.Sprintf("/v1/alerts?limit=%d&with_decisions=false", limit)
	if !full {
		path = fmt.Sprintf("/v1/alerts?since=%ds&limit=%d&with_decisions=false", int(age.Seconds())+60, limit)
	}
	resp, err := a.csRequest(ctx, http.MethodGet, path, nil, true)
	if err != nil {
		if readyForFP {
			return csAlertItems(), csStaleMode(age, err), 0, nil
		}
		return nil, "", 0, err
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		lapiErr := fmt.Errorf("LAPI %d: %s", resp.StatusCode, strings.TrimSpace(string(body)))
		if readyForFP {
			return csAlertItems(), csStaleMode(age, lapiErr), resp.StatusCode, nil
		}
		return nil, "", resp.StatusCode, lapiErr
	}
	var payload []json.RawMessage
	if err := json.NewDecoder(resp.Body).Decode(&payload); err != nil {
		if readyForFP {
			return csAlertItems(), csStaleMode(age, err), 0, nil
		}
		return nil, "", 0, err
	}
	if full {
		csAlertCache.items = map[int64]json.RawMessage{}
	}
	for _, raw := range payload {
		if id := decID(raw); id != 0 {
			csAlertCache.items[id] = raw
		}
	}
	csAlertTrimToLimit(limit)
	csAlertCache.fp = fp
	csAlertCache.limit = limit
	csAlertCache.ready = true
	csAlertCache.synced = now
	if full {
		return csAlertItems(), "full", 200, nil
	}
	return csAlertItems(), "delta", 200, nil
}

type csDecisionsSummary struct {
	OK         bool              `json:"ok"`
	Error      string            `json:"error"`
	Stale      string            `json:"stale"`
	Total      int               `json:"total"`
	Own        int               `json:"own"`
	Subscribed int               `json:"subscribed"`
	Wide       int               `json:"wide"`
	Origins    map[string]int    `json:"origins"`
	Types      map[string]int    `json:"types"`
	Rows       []json.RawMessage `json:"rows"`
	RowsMore   int               `json:"rows_more"`
}

type csAlertsSummary struct {
	OK     bool             `json:"ok"`
	Error  string           `json:"error"`
	Status int              `json:"status"`
	Limit  int              `json:"limit"`
	Capped bool             `json:"capped"`
	Rows   []map[string]any `json:"rows"`
}

const csSummaryRowCap = 500

func (a *App) csSummaryDecisions(ctx context.Context, forceFull bool) (csDecisionsSummary, []int64, map[string]bool) {
	block := csDecisionsSummary{Origins: map[string]int{}, Types: map[string]int{}, Rows: []json.RawMessage{}}
	rows, staleNote, err := a.csActiveDecisions(ctx, forceFull)
	if err != nil {
		block.Error = err.Error()
		return block, nil, map[string]bool{}
	}
	block.OK = true
	block.Stale = staleNote

	valueSet := map[string]bool{}
	type ownRow struct {
		raw json.RawMessage
		id  int64
	}
	var ownRows []ownRow
	ids := make([]int64, 0, len(rows))
	for _, raw := range rows {
		var d struct {
			ID     int64  `json:"id"`
			Origin string `json:"origin"`
			Type   string `json:"type"`
			Scope  string `json:"scope"`
			Value  string `json:"value"`
		}
		if json.Unmarshal(raw, &d) != nil {
			continue
		}
		block.Total++
		ids = append(ids, d.ID)
		originKey := strings.ToLower(strings.TrimSpace(d.Origin))
		subscribed := originKey == "capi" || originKey == "lists"
		if subscribed {
			block.Subscribed++
		} else {
			block.Own++
		}
		if d.Scope != "Ip" {
			block.Wide++
		}
		if d.Scope == "Ip" || d.Scope == "Range" {
			valueSet[d.Value] = true
		}
		block.Origins[originKey]++
		block.Types[strings.ToLower(d.Type)]++
		if !subscribed && originKey != "crowdsec" {
			ownRows = append(ownRows, ownRow{raw: raw, id: d.ID})
		}
	}
	sort.Slice(ownRows, func(i, j int) bool { return ownRows[i].id > ownRows[j].id })
	if len(ownRows) > csSummaryRowCap {
		block.RowsMore = len(ownRows) - csSummaryRowCap
		ownRows = ownRows[:csSummaryRowCap]
	}
	block.Rows = make([]json.RawMessage, 0, len(ownRows))
	for _, r := range ownRows {
		block.Rows = append(block.Rows, r.raw)
	}
	return block, ids, valueSet
}

var csAlertTrimKeys = []string{
	"id", "uuid", "scenario", "scenario_version", "events_count", "capacity",
	"leakspeed", "simulated", "machine_id", "message", "start_at", "stop_at", "created_at", "source", "meta",
}

func csTrimAlert(raw json.RawMessage, valueSet map[string]bool, decisionsOK bool) map[string]any {
	var full map[string]any
	if json.Unmarshal(raw, &full) != nil {
		return map[string]any{}
	}
	out := make(map[string]any, len(csAlertTrimKeys)+1)
	for _, k := range csAlertTrimKeys {
		if v, ok := full[k]; ok {
			out[k] = v
		}
	}
	if decisionsOK {
		ip := ""
		if src, ok := full["source"].(map[string]any); ok {
			if v, ok := src["ip"].(string); ok && v != "" {
				ip = v
			} else if v, ok := src["value"].(string); ok {
				ip = v
			}
		}
		out["handled"] = valueSet[ip]
	}
	return out
}

func (a *App) csSummaryAlerts(ctx context.Context, limit int, forceFull, decisionsOK bool,
	valueSet map[string]bool) (csAlertsSummary, []int64) {
	block := csAlertsSummary{Limit: limit, Rows: []map[string]any{}}
	rows, _, status, err := a.csAlerts(ctx, limit, forceFull)
	if err != nil {
		block.Error = err.Error()
		block.Status = status
		return block, nil
	}
	block.OK = true
	block.Status = 200
	block.Capped = limit > 0 && len(rows) >= limit
	ids := make([]int64, 0, len(rows))
	block.Rows = make([]map[string]any, 0, len(rows))
	for _, raw := range rows {
		ids = append(ids, decID(raw))
		block.Rows = append(block.Rows, csTrimAlert(raw, valueSet, decisionsOK))
	}
	return block, ids
}

func csSummaryVersion(decisionIDs, alertIDs []int64, decisionsOK, alertsOK bool) string {
	dCopy := append([]int64(nil), decisionIDs...)
	sort.Slice(dCopy, func(i, j int) bool { return dCopy[i] < dCopy[j] })
	aCopy := append([]int64(nil), alertIDs...)
	sort.Slice(aCopy, func(i, j int) bool { return aCopy[i] < aCopy[j] })

	toCSV := func(ids []int64) string {
		parts := make([]string, len(ids))
		for i, id := range ids {
			parts[i] = strconv.FormatInt(id, 10)
		}
		return strings.Join(parts, ",")
	}
	dFlag, aFlag := "0", "0"
	if decisionsOK {
		dFlag = "1"
	}
	if alertsOK {
		aFlag = "1"
	}
	raw := toCSV(dCopy) + "|" + toCSV(aCopy) + "|" + dFlag + aFlag
	sum := sha1.Sum([]byte(raw))
	return hex.EncodeToString(sum[:])[:16]
}

func (a *App) crowdsecSummaryHandler(w http.ResponseWriter, r *http.Request) {
	if a.cfg.CrowdSecLAPIURL == "" {
		jsonErrorCode(w, "crowdsec_missing", nil, "CROWDSEC_LAPI_URL not configured", http.StatusNotFound)
		return
	}
	q := r.URL.Query()
	forceFull := csTruthy(q.Get("full"))
	limit := a.cfg.CrowdSecAlertLimit
	if v := q.Get("limit"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n >= 0 && n <= 100000 {
			limit = n
		}
	}

	decisionsBlock, decisionIDs, valueSet := a.csSummaryDecisions(r.Context(), forceFull)
	alertsBlock, alertIDs := a.csSummaryAlerts(r.Context(), limit, forceFull, decisionsBlock.OK, valueSet)
	version := csSummaryVersion(decisionIDs, alertIDs, decisionsBlock.OK, alertsBlock.OK)

	if v := strings.TrimSpace(q.Get("version")); v != "" && v == version {
		jsonOK(w, map[string]any{"version": version, "unchanged": true})
		return
	}
	jsonOK(w, map[string]any{
		"version":   version,
		"decisions": decisionsBlock,
		"alerts":    alertsBlock,
	})
}

func bakBaseName(n string) string {
	base := strings.TrimSuffix(n, ".bak")
	if idx := strings.LastIndex(base, "."); idx >= 0 && len(base)-idx == 16 {
		return base[:idx]
	}
	return base
}

func acmeWritable(path string) bool {
	info, err := os.Stat(path)
	if err != nil || info.IsDir() {
		return false
	}
	fh, err := os.OpenFile(path, os.O_WRONLY, 0o600)
	if err != nil {
		return false
	}
	fh.Close()
	return true
}

func (a *App) certsStatusHandler(w http.ResponseWriter, r *http.Request) {
	paths := acmeJSONPaths(a.cfg.ACMEJSONPath)
	found := []string{}
	for _, p := range paths {
		if acmeWritable(p) {
			found = append(found, p)
		}
	}
	restart := a.cfg.RestartMethod == "proxy" || a.cfg.RestartMethod == "socket" || a.cfg.RestartMethod == "poison-pill"
	writable := len(paths) > 0 && len(found) == len(paths)
	reason, reasonCode := "", ""
	switch {
	case len(paths) == 0:
		reason, reasonCode = "ACME_JSON_PATH is not set on this agent", "acme_path_missing"
	case !writable:
		reason, reasonCode = "acme.json is mounted read only on this agent", "acme_read_only"
	case !restart:
		reason, reasonCode = "no RESTART_METHOD is configured on this agent, and Traefik only reads acme.json at startup", "acme_needs_restart"
	}
	method := ""
	if restart {
		method = a.cfg.RestartMethod
	}
	jsonOK(w, map[string]any{
		"available": writable && restart, "writable": writable,
		"restart_method": method, "reason": reason, "reason_code": reasonCode, "paths": found,
	})
}

type certDeleteBody struct {
	Certs []struct {
		Resolver string `json:"resolver"`
		Main     string `json:"main"`
	} `json:"certs"`
}

var acmeMu sync.Mutex

const acmeAttempts = 3

type acmeChangedError struct{ name string }

func (e acmeChangedError) Error() string {
	return e.name + " changed while it was being edited, most likely Traefik renewing a certificate. Nothing was written, try again."
}

func (a *App) certsDeleteHandler(w http.ResponseWriter, r *http.Request) {
	var body certDeleteBody
	if err := json.NewDecoder(r.Body).Decode(&body); err != nil || len(body.Certs) == 0 {
		jsonErrorCode(w, "nothing_selected", nil, "nothing was selected", http.StatusBadRequest)
		return
	}
	paths := acmeJSONPaths(a.cfg.ACMEJSONPath)
	if len(paths) == 0 {
		jsonErrorCode(w, "acme_path_missing", nil, "ACME_JSON_PATH is not set on this agent", http.StatusForbidden)
		return
	}
	restart := a.cfg.RestartMethod == "proxy" || a.cfg.RestartMethod == "socket" || a.cfg.RestartMethod == "poison-pill"
	if !restart {
		jsonErrorCode(w, "acme_needs_restart", nil, "no RESTART_METHOD is configured on this agent, and Traefik only reads acme.json at startup", http.StatusForbidden)
		return
	}
	wanted := map[string]bool{}
	for _, c := range body.Certs {
		if c.Main != "" {
			wanted[c.Resolver+"\x00"+c.Main] = true
		}
	}
	acmeMu.Lock()
	defer acmeMu.Unlock()
	for _, path := range paths {
		if !acmeWritable(path) {
			jsonErrorCode(w, "read_only_not_changed", map[string]any{"file": filepath.Base(path)}, filepath.Base(path)+" is mounted read only on this agent, nothing was changed", http.StatusForbidden)
			return
		}
	}
	type acmePlanned struct {
		path string
		raw  []byte
	}
	var plans []acmePlanned
	for _, path := range paths {
		count, raw, _, err := acmePlan(path, wanted)
		if err != nil {
			jsonError(w, err.Error(), http.StatusInternalServerError)
			return
		}
		if count > 0 {
			plans = append(plans, acmePlanned{path: path, raw: raw})
		}
	}
	removed := 0
	saved := ""
	for _, p := range plans {
		count, bak, err := acmeApply(p.path, wanted, p.raw, a)
		if err != nil {
			if removed > 0 {
				restarted := a.restartAfterCertChange(r)
				msg := fmt.Sprintf("removed %d certificate(s), then stopped at %s: %v", removed, filepath.Base(p.path), err)
				a.failuref("certs", "%s", msg)
				w.Header().Set("Content-Type", "application/json")
				w.WriteHeader(http.StatusInternalServerError)
				_ = json.NewEncoder(w).Encode(map[string]any{"error": msg, "code": "certs_partial", "params": map[string]any{"removed": removed, "file": filepath.Base(p.path), "detail": err.Error()}, "removed": removed, "partial": true, "backup": filepath.Base(saved), "restarted": restarted})
				return
			}
			status := http.StatusInternalServerError
			if _, changed := err.(acmeChangedError); changed {
				status = http.StatusConflict
			}
			jsonError(w, err.Error(), status)
			return
		}
		removed += count
		if bak != "" {
			saved = bak
		}
	}
	if removed == 0 {
		jsonErrorCode(w, "no_matching_cert", nil, "no matching certificate was found", http.StatusNotFound)
		return
	}
	restarted := a.restartAfterCertChange(r)
	jsonOK(w, map[string]any{"ok": true, "removed": removed, "backup": filepath.Base(saved), "restarted": restarted})
}

func acmeRemove(path string, wanted map[string]bool, a *App) (int, string, error) {
	acmeMu.Lock()
	defer acmeMu.Unlock()
	return acmeApply(path, wanted, nil, a)
}

func acmeApply(path string, wanted map[string]bool, raw []byte, a *App) (int, string, error) {
	for attempt := 0; attempt < acmeAttempts; attempt++ {
		if raw == nil {
			read, err := os.ReadFile(path)
			if err != nil {
				return 0, "", fmt.Errorf("could not read %s: %w", filepath.Base(path), err)
			}
			raw = read
		}
		count, body, err := acmeFilter(path, raw, wanted)
		if err != nil {
			return 0, "", err
		}
		if count == 0 {
			return 0, "", nil
		}
		bak, err := acmeCommit(path, raw, body, a)
		if err == nil {
			return count, bak, nil
		}
		if _, changed := err.(acmeChangedError); !changed || attempt == acmeAttempts-1 {
			return 0, "", err
		}
		raw = nil
	}
	return 0, "", nil
}

func acmePlan(path string, wanted map[string]bool) (int, []byte, []byte, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return 0, nil, nil, fmt.Errorf("could not read %s: %w", filepath.Base(path), err)
	}
	count, body, err := acmeFilter(path, raw, wanted)
	return count, raw, body, err
}

func acmeFilter(path string, raw []byte, wanted map[string]bool) (int, []byte, error) {
	var store map[string]json.RawMessage
	if len(bytes.TrimSpace(raw)) > 0 {
		if err := json.Unmarshal(raw, &store); err != nil {
			return 0, nil, fmt.Errorf("%s is not valid JSON, nothing was changed: %w", filepath.Base(path), err)
		}
	}
	removed := 0
	out := map[string]json.RawMessage{}
	for name, blob := range store {
		var section map[string]json.RawMessage
		if err := json.Unmarshal(blob, &section); err != nil {
			out[name] = blob
			continue
		}
		key := ""
		for _, candidate := range []string{"Certificates", "certificates"} {
			if _, ok := section[candidate]; ok {
				key = candidate
				break
			}
		}
		if key == "" {
			out[name] = blob
			continue
		}
		var entries []json.RawMessage
		if err := json.Unmarshal(section[key], &entries); err != nil {
			out[name] = blob
			continue
		}
		kept := []json.RawMessage{}
		for _, entry := range entries {
			var probe struct {
				Domain struct {
					Main string `json:"main"`
				} `json:"domain"`
			}
			if json.Unmarshal(entry, &probe) == nil && wanted[name+"\x00"+probe.Domain.Main] {
				removed++
				continue
			}
			kept = append(kept, entry)
		}
		encoded, err := json.Marshal(kept)
		if err != nil {
			return 0, nil, err
		}
		section[key] = encoded
		merged, err := json.Marshal(section)
		if err != nil {
			return 0, nil, err
		}
		out[name] = merged
	}
	if removed == 0 {
		return 0, nil, nil
	}
	data, err := json.MarshalIndent(out, "", "  ")
	if err != nil {
		return 0, nil, err
	}
	return removed, data, nil
}

func acmeCommit(path string, raw, body []byte, a *App) (string, error) {
	current, err := os.ReadFile(path)
	if err != nil {
		return "", fmt.Errorf("could not read %s: %w", filepath.Base(path), err)
	}
	if !bytes.Equal(current, raw) {
		return "", acmeChangedError{name: filepath.Base(path)}
	}
	bak, err := acmeBackupBytes(path, raw, a)
	if err != nil {
		return "", err
	}
	if err := acmeWriteInPlace(path, body, raw); err != nil {
		return "", err
	}
	return bak, nil
}

func acmeBackup(path string, a *App) (string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return acmeBackupBytes(path, raw, a)
}

func acmeBackupBytes(path string, raw []byte, a *App) (string, error) {
	dir := a.backupDir()
	if err := os.MkdirAll(dir, 0o750); err != nil {
		return "", err
	}
	base := acmeBackupKeys(acmeJSONPaths(a.cfg.ACMEJSONPath))[path]
	if base == "" {
		base = filepath.Base(path)
	}
	for attempt := 0; attempt < acmeAttempts+2; attempt++ {
		dest := filepath.Join(dir, base+"."+time.Now().UTC().Format("20060102_150405")+".bak")
		fh, err := os.OpenFile(dest, os.O_WRONLY|os.O_CREATE|os.O_EXCL, 0o600)
		if os.IsExist(err) {
			time.Sleep(time.Until(time.Now().Truncate(time.Second).Add(time.Second + 10*time.Millisecond)))
			continue
		}
		if err != nil {
			return "", err
		}
		_, werr := fh.Write(raw)
		serr := fh.Sync()
		cerr := fh.Close()
		if werr != nil {
			return "", werr
		}
		if serr != nil {
			return "", serr
		}
		if cerr != nil {
			return "", cerr
		}
		return dest, os.Chmod(dest, 0o600)
	}
	return "", fmt.Errorf("could not create a unique backup of %s, nothing was changed", base)
}

func acmeWriteInPlace(path string, data []byte, restore []byte) error {
	padded := data
	if info, err := os.Stat(path); err == nil && info.Size() > int64(len(data)) {
		padded = append(append([]byte{}, data...), bytes.Repeat([]byte(" "), int(info.Size())-len(data))...)
	}
	if err := acmeWriteAll(path, padded, int64(len(data))); err != nil {
		if restore != nil {
			if perr := acmeWriteInPlace(path, restore, nil); perr != nil {
				log.Printf("certs: could not put %s back after a failed write: %v", filepath.Base(path), perr)
			}
		}
		return err
	}
	if err := os.Chmod(path, 0o600); err != nil {
		return err
	}
	got, err := os.ReadFile(path)
	if err != nil {
		return fmt.Errorf("could not read %s back after writing: %w", filepath.Base(path), err)
	}
	if bytes.Equal(got, data) {
		return nil
	}
	if trimmed := bytes.TrimSpace(got); len(trimmed) == 0 || json.Valid(trimmed) {
		return acmeChangedError{name: filepath.Base(path)}
	}
	if restore != nil {
		if perr := acmeWriteInPlace(path, restore, nil); perr != nil {
			log.Printf("certs: could not put %s back after a failed write: %v", filepath.Base(path), perr)
		}
	}
	return fmt.Errorf("%s did not read back as valid JSON after writing, the previous copy was put back", filepath.Base(path))
}

func acmeWriteAll(path string, padded []byte, size int64) error {
	fh, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE, 0o600)
	if err != nil {
		return err
	}
	defer fh.Close()
	if _, err := fh.Write(padded); err != nil {
		return err
	}
	if err := fh.Sync(); err != nil {
		return err
	}
	if err := fh.Truncate(size); err != nil {
		return err
	}
	return fh.Sync()
}

func acmeKeyPart(parent string) string {
	if parent == "" || parent == "." || parent == "/" {
		return "store"
	}
	return strings.Map(func(r rune) rune {
		if (r >= 'A' && r <= 'Z') || (r >= 'a' && r <= 'z') || (r >= '0' && r <= '9') || r == '.' || r == '_' || r == ' ' || r == '-' {
			return r
		}
		return '-'
	}, parent)
}

func acmeQualifiedKey(path, base string) string {
	return acmeKeyPart(filepath.Base(filepath.Dir(path))) + "-" + base
}

func acmeBackupKey(path string, all []string) string {
	base := filepath.Base(path)
	var same []string
	seen := map[string]bool{}
	for _, other := range all {
		if !seen[other] && filepath.Base(other) == base {
			same = append(same, other)
		}
		seen[other] = true
	}
	if len(same) <= 1 {
		return base
	}
	key := acmeQualifiedKey(path, base)
	for _, other := range same {
		if other != path && acmeQualifiedKey(other, base) == key {
			sum := sha256.Sum256([]byte(path))
			return hex.EncodeToString(sum[:])[:8] + "-" + base
		}
	}
	return key
}

func acmeBackupKeys(paths []string) map[string]string {
	keys := map[string]string{}
	for _, path := range paths {
		keys[path] = acmeBackupKey(path, paths)
	}
	return keys
}

func (a *App) restartAfterCertChange(r *http.Request) bool {
	switch a.cfg.RestartMethod {
	case "poison-pill":
		if a.cfg.SignalFilePath == "" {
			return false
		}
		return os.WriteFile(a.cfg.SignalFilePath, []byte("restart"), 0o644) == nil
	case "socket", "proxy":
		if err := a.dockerPreflight(r.Context()); err != nil {
			a.failuref("restart", "Traefik restart after a certificate change failed: %v", err)
			return false
		}
		go func() {
			time.Sleep(400 * time.Millisecond)
			ctx, cancel := context.WithTimeout(context.Background(), 60*time.Second)
			defer cancel()
			if err := a.dockerRestart(ctx); err != nil {
				a.failuref("restart", "Traefik restart after a certificate change failed: %v", err)
			}
		}()
		return true
	}
	return false
}
