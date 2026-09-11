package main

import (
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func resetCSCache() {
	csJWT, csJWTExpiry = "", time.Time{}
	csCache.mu.Lock()
	csCache.items = map[int64]json.RawMessage{}
	csCache.fp = ""
	csCache.ready = false
	csCache.mu.Unlock()
	csStreamable = true
}

func newStreamStub(t *testing.T, supportStream bool) (*httptest.Server, *[]string) {
	t.Helper()
	paths := []string{}
	pool := []string{}
	for i := 1; i <= 3; i++ {
		pool = append(pool, fmt.Sprintf(`{"id":%d,"value":"10.0.0.%d","origin":"crowdsec","type":"ban","scenario":"s","scope":"Ip","duration":"1h"}`, i, i))
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		paths = append(paths, r.URL.String())
		w.Header().Set("Content-Type", "application/json")
		if strings.HasPrefix(r.URL.Path, "/v1/decisions/stream") {
			if !supportStream {
				w.WriteHeader(http.StatusNotFound)
				w.Write([]byte(`{"message":"not found"}`))
				return
			}
			if r.URL.Query().Get("startup") == "true" {
				fmt.Fprintf(w, `{"new":[%s],"deleted":[]}`, strings.Join(pool, ","))
				return
			}
			fmt.Fprint(w, `{"new":[{"id":9,"value":"9.9.9.9","origin":"cscli","type":"ban","scenario":"s","scope":"Ip","duration":"1h"}],"deleted":[{"id":1,"value":"10.0.0.1"}]}`)
			return
		}
		if r.URL.Path == "/v1/decisions" {
			if r.URL.Query().Get("id_gt") == "0" {
				fmt.Fprintf(w, `[%s]`, strings.Join(pool, ","))
				return
			}
			fmt.Fprint(w, `[]`)
			return
		}
		if r.URL.Path == "/v1/watchers/login" {
			fmt.Fprint(w, `{"token":"tok","expire":"2099-01-01T00:00:00Z"}`)
			return
		}
		if r.URL.Path == "/v1/alerts" {
			fmt.Fprint(w, `[]`)
			return
		}
		w.WriteHeader(http.StatusNotFound)
	}))
	t.Cleanup(srv.Close)
	return srv, &paths
}

func TestAgentDecisionsUseStreamAndThenDelta(t *testing.T) {
	resetCSCache()
	srv, paths := newStreamStub(t, true)
	a := &App{cfg: &Config{CrowdSecLAPIURL: srv.URL, CrowdSecAPIKey: "k"}, csClient: srv.Client()}

	rec := httptest.NewRecorder()
	a.crowdsecDecisionsHandler(rec, httptest.NewRequest(http.MethodGet, "/api/crowdsec/decisions", nil))
	if rec.Code != 200 {
		t.Fatalf("first read: %d %s", rec.Code, rec.Body)
	}
	if got := len(decisionValues(t, rec.Body.Bytes())); got != 3 {
		t.Fatalf("expected 3 decisions on startup, got %d", got)
	}
	if !strings.Contains((*paths)[0], "startup=true") {
		t.Fatalf("first call should be a startup sync, got %s", (*paths)[0])
	}

	rec2 := httptest.NewRecorder()
	a.crowdsecDecisionsHandler(rec2, httptest.NewRequest(http.MethodGet, "/api/crowdsec/decisions", nil))
	vals := decisionValues(t, rec2.Body.Bytes())
	if strings.Contains((*paths)[1], "startup=true") {
		t.Fatalf("second call must be an incremental delta, got %s", (*paths)[1])
	}
	joined := strings.Join(vals, ",")
	if !strings.Contains(joined, "9.9.9.9") {
		t.Fatalf("delta add missing, got %v", vals)
	}
	if strings.Contains(joined, "10.0.0.1") {
		t.Fatalf("delta delete not applied, got %v", vals)
	}
}

func TestAgentFallsBackToPagedWalkWithoutStream(t *testing.T) {
	resetCSCache()
	srv, paths := newStreamStub(t, false)
	a := &App{cfg: &Config{CrowdSecLAPIURL: srv.URL, CrowdSecAPIKey: "k"}, csClient: srv.Client()}

	rec := httptest.NewRecorder()
	a.crowdsecDecisionsHandler(rec, httptest.NewRequest(http.MethodGet, "/api/crowdsec/decisions", nil))
	if rec.Code != 200 {
		t.Fatalf("fallback read failed: %d %s", rec.Code, rec.Body)
	}
	if got := len(decisionValues(t, rec.Body.Bytes())); got != 3 {
		t.Fatalf("paged fallback should return every decision, got %d", got)
	}
	sawStream, sawPaged := false, false
	for _, p := range *paths {
		if strings.Contains(p, "stream") {
			sawStream = true
		}
		if strings.Contains(p, "id_gt=") {
			sawPaged = true
		}
	}
	if !sawStream || !sawPaged {
		t.Fatalf("expected stream attempt then paged fallback, got %v", *paths)
	}
}

func TestAgentAlertsAreBounded(t *testing.T) {
	resetCSCache()
	srv, paths := newStreamStub(t, true)
	a := &App{cfg: &Config{CrowdSecLAPIURL: srv.URL, CrowdSecAPIKey: "k",
		CrowdSecMachineID: "m", CrowdSecMachinePassword: "p", CrowdSecAlertLimit: 250}, csClient: srv.Client()}

	rec := httptest.NewRecorder()
	a.crowdsecAlertsHandler(rec, httptest.NewRequest(http.MethodGet, "/api/crowdsec/alerts", nil))

	found := false
	for _, p := range *paths {
		if strings.Contains(p, "/v1/alerts") {
			found = true
			if !strings.Contains(p, "limit=250") {
				t.Fatalf("alerts must be bounded by the configured limit, got %s", p)
			}
			if strings.Contains(p, "limit=0") {
				t.Fatalf("alerts must not request every alert ever stored, got %s", p)
			}
		}
	}
	if !found {
		t.Fatalf("no alerts call made, paths=%v", *paths)
	}
}

func TestCSReadTimeoutDefaultsAndClamps(t *testing.T) {
	if got := csReadTimeout(&Config{}); got != 20 {
		t.Fatalf("default read timeout should be 20, got %d", got)
	}
	if got := csReadTimeout(&Config{CrowdSecReadTimeout: 45}); got != 45 {
		t.Fatalf("explicit read timeout should be honoured, got %d", got)
	}
	if got := csReadTimeout(nil); got != 20 {
		t.Fatalf("nil config must not panic, got %d", got)
	}
}

func TestCSClientAlwaysHasATimeout(t *testing.T) {
	c := buildCSClient(&Config{})
	if c.Timeout == 0 {
		t.Fatal("the CrowdSec client must not hang forever on a stalled LAPI")
	}
}
