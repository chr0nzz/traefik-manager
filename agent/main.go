package main

import (
	"crypto/tls"
	"crypto/x509"
	"fmt"
	"log"
	"net/http"
	"os"
	"strconv"
	"strings"
	"time"
)

const Version = "1.13.3"

type Config struct {
	APIKey                    string
	Port                      string
	RateLimit                 int
	TraefikAPIURL             string
	TraefikAPIUser            string
	TraefikAPIPassword        string
	TraefikInsecureSkipVerify bool
	ConfigPath                string
	StaticConfigPath          string
	ACMEJSONPath              string
	AccessLogPath             string
	PluginsDir                string
	RestartMethod             string
	TraefikContainer          string
	DockerHost                string
	SignalFilePath            string
	CrowdSecLAPIURL           string
	CrowdSecAPIKey            string
	CrowdSecMachineID         string
	CrowdSecMachinePassword   string
	CrowdSecClientCert        string
	CrowdSecClientKey         string
	CrowdSecCACert            string
	CrowdSecReadTimeout       int
	CrowdSecAlertLimit        int
	GitBackupEnabled          bool
	GitBackupRepo             string
	GitBackupBranch           string
	GitBackupUsername         string
	GitBackupToken            string
	GitBackupAutoPush         bool
	GitBackupCommitMsg        string
	BackupDir                 string
	BackupKeepCount           int
	Debug                     bool
}

type App struct {
	cfg        *Config
	rl         *perIPLimiter
	httpClient *http.Client
	csClient   *http.Client
	keys       *keyStore
	events     *eventLog
}

func buildCSClient(cfg *Config) *http.Client {
	tlsCfg := &tls.Config{}
	configured := false
	if cfg.CrowdSecClientCert != "" && cfg.CrowdSecClientKey != "" {
		pair, err := tls.LoadX509KeyPair(cfg.CrowdSecClientCert, cfg.CrowdSecClientKey)
		if err != nil {
			log.Printf("crowdsec client certificate unusable, mTLS disabled: %v", err)
		} else {
			tlsCfg.Certificates = []tls.Certificate{pair}
			configured = true
		}
	}
	if cfg.CrowdSecCACert != "" {
		pem, err := os.ReadFile(cfg.CrowdSecCACert)
		if err != nil {
			log.Printf("crowdsec CA certificate unreadable: %v", err)
		} else {
			pool := x509.NewCertPool()
			if pool.AppendCertsFromPEM(pem) {
				tlsCfg.RootCAs = pool
				configured = true
			} else {
				log.Printf("crowdsec CA certificate contains no usable PEM data")
			}
		}
	}
	if !configured {
		return &http.Client{Timeout: time.Duration(csReadTimeout(cfg)) * time.Second}
	}
	return &http.Client{
		Timeout:   time.Duration(csReadTimeout(cfg)) * time.Second,
		Transport: &http.Transport{TLSClientConfig: tlsCfg, TLSHandshakeTimeout: 10 * time.Second},
	}
}

func envOr(key, def string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return def
}

func envInt(key string, def int) int {
	if v := os.Getenv(key); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n >= 0 {
			return n
		}
	}
	return def
}

func envBool(key string, def bool) bool {
	v := strings.ToLower(os.Getenv(key))
	if v == "true" || v == "1" || v == "yes" {
		return true
	}
	if v == "false" || v == "0" || v == "no" {
		return false
	}
	return def
}

func loadConfig() *Config {
	return &Config{
		APIKey:                    strings.TrimSpace(os.Getenv("TMA_API_KEY")),
		Port:                      envOr("TMA_PORT", "8090"),
		RateLimit:                 envInt("TMA_RATE_LIMIT", 300),
		TraefikAPIURL:             envOr("TRAEFIK_API_URL", "http://traefik:8080"),
		TraefikAPIUser:            os.Getenv("TRAEFIK_API_USER"),
		TraefikAPIPassword:        os.Getenv("TRAEFIK_API_PASSWORD"),
		TraefikInsecureSkipVerify: envBool("TRAEFIK_INSECURE_SKIP_VERIFY", false),
		ConfigPath:                envOr("CONFIG_PATH", "/app/config"),
		StaticConfigPath:          os.Getenv("STATIC_CONFIG_PATH"),
		ACMEJSONPath:              os.Getenv("ACME_JSON_PATH"),
		AccessLogPath:             os.Getenv("ACCESS_LOG_PATH"),
		PluginsDir:                os.Getenv("PLUGINS_DIR"),
		RestartMethod:             os.Getenv("RESTART_METHOD"),
		TraefikContainer:          envOr("TRAEFIK_CONTAINER", "traefik"),
		DockerHost:                os.Getenv("DOCKER_HOST"),
		SignalFilePath:            os.Getenv("SIGNAL_FILE_PATH"),
		CrowdSecReadTimeout:       envIntRange("CROWDSEC_READ_TIMEOUT", 20, 1, 120),
		CrowdSecAlertLimit:        envIntRange("CROWDSEC_ALERT_LIMIT", 500, 0, 100000),
		CrowdSecLAPIURL:           os.Getenv("CROWDSEC_LAPI_URL"),
		CrowdSecAPIKey:            os.Getenv("CROWDSEC_API_KEY"),
		CrowdSecMachineID:         os.Getenv("CROWDSEC_MACHINE_ID"),
		CrowdSecMachinePassword:   os.Getenv("CROWDSEC_MACHINE_PASSWORD"),
		CrowdSecClientCert:        os.Getenv("CROWDSEC_CLIENT_CERT"),
		CrowdSecClientKey:         os.Getenv("CROWDSEC_CLIENT_KEY"),
		CrowdSecCACert:            os.Getenv("CROWDSEC_CA_CERT"),
		GitBackupEnabled:          envBool("GIT_BACKUP_ENABLED", false),
		GitBackupRepo:             os.Getenv("GIT_BACKUP_REPO"),
		GitBackupBranch:           envOr("GIT_BACKUP_BRANCH", "main"),
		GitBackupUsername:         os.Getenv("GIT_BACKUP_USERNAME"),
		GitBackupToken:            os.Getenv("GIT_BACKUP_TOKEN"),
		GitBackupAutoPush:         envBool("GIT_BACKUP_AUTO_PUSH", true),
		GitBackupCommitMsg:        envOr("GIT_BACKUP_COMMIT_MESSAGE", "traefik-manager: {action} at {timestamp}"),
		BackupDir:                 envOr("BACKUP_DIR", "/app/backups"),
		BackupKeepCount:           envInt("BACKUP_KEEP_COUNT", 0),
		Debug:                     envBool("TMA_DEBUG", false),
	}
}

func main() {
	cfg := loadConfig()
	if cfg.APIKey == "" {
		log.Fatal("TMA_API_KEY environment variable is required")
	}

	transport := &http.Transport{
		TLSClientConfig: &tls.Config{InsecureSkipVerify: cfg.TraefikInsecureSkipVerify},
	}
	app := &App{
		cfg:        cfg,
		rl:         newPerIPLimiter(cfg.RateLimit),
		httpClient: &http.Client{Transport: transport},
		csClient:   buildCSClient(cfg),
		keys:       newKeyStore(cfg.BackupDir),
		events:     newEventLog(),
	}

	for _, problem := range unwritableStorage(cfg) {
		log.Printf("storage: %s at %s is not writable (%s). Config writes and backups will fail.",
			problem.Label, problem.Path, problem.Err)
		app.events.record("storage", fmt.Sprintf("%s at %s is not writable (%s)",
			problem.Label, problem.Path, problem.Err))
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/health", app.healthHandler)
	mux.Handle("/api/", app.rateLimitMiddleware(app.authMiddleware(http.HandlerFunc(app.router))))

	log.Printf("TMA v%s listening on :%s (traefik=%s, insecure-tls=%v, traefik-auth=%v, debug=%v)", Version, cfg.Port, cfg.TraefikAPIURL, cfg.TraefikInsecureSkipVerify, cfg.TraefikAPIUser != "", cfg.Debug)
	if err := http.ListenAndServe(":"+cfg.Port, mux); err != nil {
		log.Fatal(err)
	}
}

func (a *App) router(w http.ResponseWriter, r *http.Request) {
	p := r.URL.Path
	m := r.Method

	switch {
	case p == "/api/events" && m == http.MethodGet:
		a.eventsHandler(w, r)

	case p == "/api/traefik/overview" && m == http.MethodGet:
		a.traefikProxy(w, r, "/api/overview")
	case p == "/api/traefik/routers" && m == http.MethodGet:
		a.routersHandler(w, r)
	case strings.HasPrefix(p, "/api/traefik/router/") && m == http.MethodGet:
		a.routerDetailHandler(w, r, strings.TrimPrefix(p, "/api/traefik/router/"))
	case p == "/api/traefik/services" && m == http.MethodGet:
		a.servicesHandler(w, r)
	case p == "/api/traefik/middlewares" && m == http.MethodGet:
		a.middlewaresHandler(w, r)
	case p == "/api/traefik/entrypoints" && m == http.MethodGet:
		a.traefikProxy(w, r, "/api/entrypoints?per_page=1000")
	case p == "/api/traefik/version" && m == http.MethodGet:
		a.traefikProxy(w, r, "/api/version")
	case p == "/api/traefik/logs" && m == http.MethodGet:
		a.logsHandler(w, r)
	case p == "/api/traefik/certs" && m == http.MethodGet:
		a.certsHandler(w, r)
	case p == "/api/traefik/plugins" && m == http.MethodGet:
		a.pluginsHandler(w, r)

	case p == "/api/configs" && m == http.MethodGet:
		a.configsReadHandler(w, r)
	case p == "/api/configs" && m == http.MethodPost:
		a.configsWriteHandler(w, r)

	case p == "/api/static" && m == http.MethodGet:
		a.staticReadHandler(w, r)
	case p == "/api/static" && m == http.MethodPost:
		a.staticWriteHandler(w, r)
	case p == "/api/static/restart" && m == http.MethodPost:
		a.staticRestartHandler(w, r)
	case p == "/api/static/status" && m == http.MethodGet:
		a.staticStatusHandler(w, r)

	case p == "/api/crowdsec/decisions" && m == http.MethodGet:
		a.crowdsecDecisionsHandler(w, r)
	case p == "/api/crowdsec/decisions" && m == http.MethodPost:
		a.crowdsecAddDecisionHandler(w, r)
	case p == "/api/crowdsec/alerts" && m == http.MethodGet:
		a.crowdsecAlertsHandler(w, r)
	case strings.HasPrefix(p, "/api/crowdsec/decisions/") && m == http.MethodDelete:
		id := strings.TrimPrefix(p, "/api/crowdsec/decisions/")
		a.crowdsecProxy(w, r, http.MethodDelete, "/v1/decisions/"+id)
		csCacheReset()

	case p == "/api/backups" && m == http.MethodGet:
		a.backupsListHandler(w, r)
	case p == "/api/backup/create" && m == http.MethodPost:
		a.backupCreateHandler(w, r)
	case strings.HasPrefix(p, "/api/restore/") && m == http.MethodPost:
		a.restoreHandler(w, r)
	case strings.HasPrefix(p, "/api/backup/delete/") && m == http.MethodPost:
		a.backupDeleteHandler(w, r)

	case p == "/api/backup/git/status" && m == http.MethodGet:
		a.gitStatusHandler(w, r)
	case p == "/api/backup/git/push" && m == http.MethodPost:
		a.gitPushHandler(w, r)
	case p == "/api/backup/git/test" && m == http.MethodPost:
		a.gitTestHandler(w, r)
	case p == "/api/backup/git/commits" && m == http.MethodGet:
		a.gitCommitsHandler(w, r)
	case strings.HasPrefix(p, "/api/backup/git/commit/") && strings.HasSuffix(p, "/diff") && m == http.MethodGet:
		sha := strings.TrimSuffix(strings.TrimPrefix(p, "/api/backup/git/commit/"), "/diff")
		a.gitDiffHandler(w, r, sha)
	case strings.HasPrefix(p, "/api/backup/git/restore/") && m == http.MethodPost:
		sha := strings.TrimPrefix(p, "/api/backup/git/restore/")
		a.gitRestoreHandler(w, r, sha)
	case p == "/api/backup/git/repo" && m == http.MethodDelete:
		a.gitResetHandler(w, r)

	case p == "/api/keys" && m == http.MethodGet:
		a.keysListHandler(w, r)
	case p == "/api/keys" && m == http.MethodPost:
		a.keysCreateHandler(w, r)
	case strings.HasPrefix(p, "/api/keys/") && m == http.MethodDelete:
		a.keysDeleteHandler(w, r, strings.TrimPrefix(p, "/api/keys/"))

	case strings.HasPrefix(p, "/api/routes/") && strings.HasSuffix(p, "/raw") && m == http.MethodGet:
		id := strings.TrimSuffix(strings.TrimPrefix(p, "/api/routes/"), "/raw")
		a.routeRawGetHandler(w, r, id)
	case strings.HasPrefix(p, "/api/routes/") && strings.HasSuffix(p, "/raw") && m == http.MethodPost:
		id := strings.TrimSuffix(strings.TrimPrefix(p, "/api/routes/"), "/raw")
		a.routeRawSaveHandler(w, r, id)

	default:
		jsonError(w, "not found", http.StatusNotFound)
	}
}

func csReadTimeout(cfg *Config) int {
	if cfg == nil || cfg.CrowdSecReadTimeout <= 0 {
		return 20
	}
	return cfg.CrowdSecReadTimeout
}

func envIntRange(name string, def, lo, hi int) int {
	v, err := strconv.Atoi(strings.TrimSpace(os.Getenv(name)))
	if err != nil {
		return def
	}
	if v < lo {
		return lo
	}
	if v > hi {
		return hi
	}
	return v
}
