package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"reflect"
	"strings"
	"testing"
	"time"
)

func resetSummaryCaches() {
	resetCSCache()
	csAlertCache.mu.Lock()
	csAlertCache.items = map[int64]json.RawMessage{}
	csAlertCache.fp = ""
	csAlertCache.limit = 0
	csAlertCache.ready = false
	csAlertCache.synced = time.Time{}
	csAlertCache.mu.Unlock()
}

type summaryDecisionsResp struct {
	OK         bool             `json:"ok"`
	Error      string           `json:"error"`
	Stale      string           `json:"stale"`
	Total      int              `json:"total"`
	Own        int              `json:"own"`
	Subscribed int              `json:"subscribed"`
	Wide       int              `json:"wide"`
	Origins    map[string]int   `json:"origins"`
	Types      map[string]int   `json:"types"`
	Rows       []map[string]any `json:"rows"`
	RowsMore   int              `json:"rows_more"`
}

type summaryAlertsResp struct {
	OK     bool             `json:"ok"`
	Error  string           `json:"error"`
	Status int              `json:"status"`
	Limit  int              `json:"limit"`
	Capped bool             `json:"capped"`
	Rows   []map[string]any `json:"rows"`
}

type summaryResp struct {
	Version   string               `json:"version"`
	Unchanged bool                 `json:"unchanged"`
	Decisions summaryDecisionsResp `json:"decisions"`
	Alerts    summaryAlertsResp    `json:"alerts"`
}

func rowIDs(rows []map[string]any) []int {
	out := make([]int, len(rows))
	for i, row := range rows {
		out[i] = int(row["id"].(float64))
	}
	return out
}

const summaryTestDecisions = `{"id":1,"origin":"capi","value":"1.1.1.1","type":"ban","scope":"Ip","scenario":"a"},` +
	`{"id":2,"origin":"lists","value":"2.2.2.2","type":"ban","scope":"Ip","scenario":"b"},` +
	`{"id":3,"origin":"crowdsec","value":"3.3.3.3","type":"ban","scope":"Ip","scenario":"c"},` +
	`{"id":4,"origin":"cscli","value":"4.4.4.4","type":"captcha","scope":"Ip","scenario":"d"},` +
	`{"id":5,"origin":"manual","value":"5.5.5.5","type":"ban","scope":"Range","scenario":"e"},` +
	`{"id":6,"origin":"","value":"6.6.6.6","type":"ban","scope":"AS","scenario":"f"}`

const summaryTestAlerts = `[
  {"id":101,"uuid":"u1","scenario":"s1","scenario_version":"v1","events_count":3,"capacity":5,
   "leakspeed":"10","simulated":false,"machine_id":"m1","message":"msg1","start_at":"t1","stop_at":"t2",
   "created_at":"t3","source":{"ip":"4.4.4.4","scope":"Ip"},"meta":[{"key":"a"}],
   "events":[{"x":1}],"decisions":[{"origin":"crowdsec"}],"labels":null,"scenario_hash":"h","remediation":true},
  {"id":102,"uuid":"u2","scenario":"s2","source":{"ip":"9.9.9.9"},"events_count":0}
]`

func newSummaryStub(t *testing.T) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch {
		case strings.HasPrefix(r.URL.Path, "/v1/decisions/stream"):
			fmt.Fprintf(w, `{"new":[%s],"deleted":[]}`, summaryTestDecisions)
		case r.URL.Path == "/v1/alerts":
			fmt.Fprint(w, summaryTestAlerts)
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	t.Cleanup(srv.Close)
	return srv
}

func TestSummaryShapeAndCounts(t *testing.T) {
	resetSummaryCaches()
	srv := newSummaryStub(t)
	a := &App{cfg: &Config{CrowdSecLAPIURL: srv.URL, CrowdSecAPIKey: "k", CrowdSecAlertLimit: 500}, csClient: srv.Client()}

	rec := httptest.NewRecorder()
	a.crowdsecSummaryHandler(rec, httptest.NewRequest(http.MethodGet, "/api/crowdsec/summary", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", rec.Code, rec.Body)
	}
	var resp summaryResp
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("bad response: %v (%s)", err, rec.Body.String())
	}
	if len(resp.Version) != 16 {
		t.Fatalf("expected a 16 char version, got %q", resp.Version)
	}

	d := resp.Decisions
	if !d.OK || d.Error != "" {
		t.Fatalf("decisions block should be ok, got %+v", d)
	}
	if d.Total != 6 || d.Own != 4 || d.Subscribed != 2 || d.Wide != 2 {
		t.Fatalf("unexpected counts: %+v", d)
	}
	wantOrigins := map[string]int{"capi": 1, "lists": 1, "crowdsec": 1, "cscli": 1, "manual": 1, "": 1}
	if !reflect.DeepEqual(d.Origins, wantOrigins) {
		t.Fatalf("origins want %v got %v", wantOrigins, d.Origins)
	}
	wantTypes := map[string]int{"ban": 5, "captcha": 1}
	if !reflect.DeepEqual(d.Types, wantTypes) {
		t.Fatalf("types want %v got %v", wantTypes, d.Types)
	}
	if got, want := rowIDs(d.Rows), []int{6, 5, 4}; !reflect.DeepEqual(got, want) {
		t.Fatalf("rows want %v got %v (own, origin != crowdsec, id desc)", want, got)
	}
	if d.RowsMore != 0 {
		t.Fatalf("rows_more should be 0 under the cap, got %d", d.RowsMore)
	}

	al := resp.Alerts
	if !al.OK || al.Error != "" {
		t.Fatalf("alerts block should be ok, got %+v", al)
	}
	if al.Limit != 500 || al.Capped {
		t.Fatalf("unexpected limit/capped: %+v", al)
	}
	if got, want := rowIDs(al.Rows), []int{102, 101}; !reflect.DeepEqual(got, want) {
		t.Fatalf("alert rows want %v got %v", want, got)
	}
	row101 := al.Rows[1]
	for _, dropped := range []string{"events", "decisions", "labels", "scenario_hash", "remediation"} {
		if _, has := row101[dropped]; has {
			t.Fatalf("alert row must not carry %q: %+v", dropped, row101)
		}
	}
	for _, kept := range []string{"id", "uuid", "scenario", "scenario_version", "events_count", "capacity",
		"leakspeed", "simulated", "machine_id", "message", "start_at", "stop_at", "created_at", "source", "meta"} {
		if _, has := row101[kept]; !has {
			t.Fatalf("alert row must keep %q: %+v", kept, row101)
		}
	}
	if handled, _ := row101["handled"].(bool); !handled {
		t.Fatalf("alert on 4.4.4.4 should be handled (it is an active decision value), got %+v", row101)
	}
	row102 := al.Rows[0]
	if handled, _ := row102["handled"].(bool); handled {
		t.Fatalf("alert on 9.9.9.9 should not be handled, got %+v", row102)
	}

	rec2 := httptest.NewRecorder()
	a.crowdsecSummaryHandler(rec2, httptest.NewRequest(http.MethodGet, "/api/crowdsec/summary?version="+resp.Version, nil))
	var raw map[string]any
	if err := json.Unmarshal(rec2.Body.Bytes(), &raw); err != nil {
		t.Fatalf("bad unchanged response: %v", err)
	}
	if raw["unchanged"] != true || raw["version"] != resp.Version {
		t.Fatalf("expected an unchanged response for a matching version, got %v", raw)
	}
	if _, has := raw["decisions"]; has {
		t.Fatalf("an unchanged response must not carry the sub-blocks, got %v", raw)
	}
}

func TestSummaryVersionChangesAfterDelta(t *testing.T) {
	resetSummaryCaches()
	calls := 0
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		switch {
		case strings.HasPrefix(r.URL.Path, "/v1/decisions/stream"):
			calls++
			if calls == 1 {
				fmt.Fprint(w, `{"new":[{"id":1,"origin":"cscli","value":"1.1.1.1","type":"ban","scope":"Ip"}],"deleted":[]}`)
				return
			}
			fmt.Fprint(w, `{"new":[{"id":2,"origin":"cscli","value":"2.2.2.2","type":"ban","scope":"Ip"}],"deleted":[]}`)
		case r.URL.Path == "/v1/alerts":
			fmt.Fprint(w, `[]`)
		default:
			w.WriteHeader(http.StatusNotFound)
		}
	}))
	defer srv.Close()
	a := &App{cfg: &Config{CrowdSecLAPIURL: srv.URL, CrowdSecAPIKey: "k"}, csClient: srv.Client()}

	rec1 := httptest.NewRecorder()
	a.crowdsecSummaryHandler(rec1, httptest.NewRequest(http.MethodGet, "/api/crowdsec/summary", nil))
	var r1 summaryResp
	if err := json.Unmarshal(rec1.Body.Bytes(), &r1); err != nil {
		t.Fatalf("bad response: %v", err)
	}

	rec2 := httptest.NewRecorder()
	a.crowdsecSummaryHandler(rec2, httptest.NewRequest(http.MethodGet, "/api/crowdsec/summary", nil))
	var r2 summaryResp
	if err := json.Unmarshal(rec2.Body.Bytes(), &r2); err != nil {
		t.Fatalf("bad response: %v", err)
	}
	if r1.Version == r2.Version {
		t.Fatalf("version should change after a decisions delta, got %s twice", r1.Version)
	}

	rec3 := httptest.NewRecorder()
	a.crowdsecSummaryHandler(rec3, httptest.NewRequest(http.MethodGet, "/api/crowdsec/summary?version="+r2.Version, nil))
	var raw map[string]any
	if err := json.Unmarshal(rec3.Body.Bytes(), &raw); err != nil {
		t.Fatalf("bad response: %v", err)
	}
	if raw["unchanged"] != true {
		t.Fatalf("matching version should report unchanged, got %v", raw)
	}
}

func TestSummaryDecisionsNotOKWhileAlertsOK(t *testing.T) {
	resetSummaryCaches()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if strings.HasPrefix(r.URL.Path, "/v1/decisions/stream") {
			w.WriteHeader(http.StatusInternalServerError)
			w.Write([]byte(`{"message":"lapi down"}`))
			return
		}
		if r.URL.Path == "/v1/alerts" {
			w.Header().Set("Content-Type", "application/json")
			fmt.Fprint(w, `[{"id":201,"source":{"ip":"1.2.3.4"},"events_count":1}]`)
			return
		}
		w.WriteHeader(http.StatusNotFound)
	}))
	defer srv.Close()
	a := &App{cfg: &Config{CrowdSecLAPIURL: srv.URL, CrowdSecAPIKey: "k", CrowdSecAlertLimit: 500}, csClient: srv.Client()}

	rec := httptest.NewRecorder()
	a.crowdsecSummaryHandler(rec, httptest.NewRequest(http.MethodGet, "/api/crowdsec/summary", nil))
	if rec.Code != http.StatusOK {
		t.Fatalf("summary must always answer 200 when the LAPI url is set, got %d: %s", rec.Code, rec.Body)
	}
	var resp summaryResp
	if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
		t.Fatalf("bad response: %v", err)
	}
	if resp.Decisions.OK {
		t.Fatal("decisions block should be not-ok when the LAPI stream is down")
	}
	if resp.Decisions.Error == "" {
		t.Fatal("decisions block should carry the LAPI error text")
	}
	if resp.Decisions.Total != 0 || len(resp.Decisions.Rows) != 0 || len(resp.Decisions.Origins) != 0 || len(resp.Decisions.Types) != 0 {
		t.Fatalf("a failed decisions block must report zero counts and no rows, got %+v", resp.Decisions)
	}
	if !resp.Alerts.OK {
		t.Fatalf("alerts block should stay ok even though decisions failed: %+v", resp.Alerts)
	}
	if len(resp.Alerts.Rows) != 1 {
		t.Fatalf("expected 1 alert row, got %d", len(resp.Alerts.Rows))
	}
	if _, has := resp.Alerts.Rows[0]["handled"]; has {
		t.Fatal("handled must be absent when decisions.ok is false")
	}
}

type searchResp struct {
	Rows        []map[string]any `json:"rows"`
	Total       int              `json:"total"`
	Page        int              `json:"page"`
	Pages       int              `json:"pages"`
	Per         int              `json:"per"`
	FacetTotals map[string]int   `json:"facet_totals"`
}

func TestSearchFiltersPagingOrderAndFacets(t *testing.T) {
	resetSummaryCaches()
	decisions := `{"id":1,"origin":"capi","value":"1.1.1.1","type":"ban","scope":"Ip","scenario":"crowdsecurity/ssh-bf"},` +
		`{"id":2,"origin":"lists","value":"2.2.2.2","type":"ban","scope":"Ip","scenario":"list-block"},` +
		`{"id":3,"origin":"cscli","value":"3.3.3.3","type":"ban","scope":"Ip","scenario":"manual-ban"},` +
		`{"id":4,"origin":"manual","value":"4.4.4.4","type":"captcha","scope":"Ip","scenario":"manual-captcha"},` +
		`{"id":5,"origin":"crowdsec","value":"5.5.5.5","type":"ban","scope":"Ip","scenario":"crowdsecurity/http-probing"}`
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if strings.HasPrefix(r.URL.Path, "/v1/decisions/stream") {
			if r.URL.Query().Get("startup") == "true" {
				fmt.Fprintf(w, `{"new":[%s],"deleted":[]}`, decisions)
				return
			}
			fmt.Fprint(w, `{"new":[],"deleted":[]}`)
			return
		}
		w.WriteHeader(http.StatusNotFound)
	}))
	defer srv.Close()
	a := &App{cfg: &Config{CrowdSecLAPIURL: srv.URL, CrowdSecAPIKey: "k"}, csClient: srv.Client()}

	search := func(query string) searchResp {
		t.Helper()
		rec := httptest.NewRecorder()
		a.crowdsecDecisionsSearchHandler(rec, httptest.NewRequest(http.MethodGet, "/api/crowdsec/decisions/search?"+query, nil))
		if rec.Code != http.StatusOK {
			t.Fatalf("query %q: got %d: %s", query, rec.Code, rec.Body)
		}
		var resp searchResp
		if err := json.Unmarshal(rec.Body.Bytes(), &resp); err != nil {
			t.Fatalf("bad response for %q: %v", query, err)
		}
		return resp
	}

	t.Run("no filter orders own first then id desc", func(t *testing.T) {
		resp := search("")
		if want := []int{5, 4, 3, 2, 1}; !reflect.DeepEqual(rowIDs(resp.Rows), want) {
			t.Fatalf("want %v, got %v", want, rowIDs(resp.Rows))
		}
		if resp.Total != 5 || resp.Pages != 1 {
			t.Fatalf("unexpected total/pages: %+v", resp)
		}
	})

	t.Run("origin own", func(t *testing.T) {
		resp := search("origin=own")
		if want := []int{5, 4, 3}; !reflect.DeepEqual(rowIDs(resp.Rows), want) {
			t.Fatalf("want %v, got %v", want, rowIDs(resp.Rows))
		}
		if resp.FacetTotals["origin"] != 3 {
			t.Fatalf("facet origin want 3, got %d", resp.FacetTotals["origin"])
		}
		if resp.FacetTotals["type"] != 5 {
			t.Fatalf("facet type (unfiltered by origin) want 5, got %d", resp.FacetTotals["type"])
		}
	})

	t.Run("origin subscribed", func(t *testing.T) {
		resp := search("origin=subscribed")
		if want := []int{2, 1}; !reflect.DeepEqual(rowIDs(resp.Rows), want) {
			t.Fatalf("want %v, got %v", want, rowIDs(resp.Rows))
		}
	})

	t.Run("origin byhand", func(t *testing.T) {
		resp := search("origin=byhand")
		if want := []int{4, 3}; !reflect.DeepEqual(rowIDs(resp.Rows), want) {
			t.Fatalf("want %v, got %v", want, rowIDs(resp.Rows))
		}
	})

	t.Run("origin exact match", func(t *testing.T) {
		resp := search("origin=crowdsec")
		if want := []int{5}; !reflect.DeepEqual(rowIDs(resp.Rows), want) {
			t.Fatalf("want %v, got %v", want, rowIDs(resp.Rows))
		}
	})

	t.Run("type filter", func(t *testing.T) {
		resp := search("type=ban")
		if want := []int{5, 3, 2, 1}; !reflect.DeepEqual(rowIDs(resp.Rows), want) {
			t.Fatalf("want %v, got %v", want, rowIDs(resp.Rows))
		}
		if resp.FacetTotals["type"] != 4 {
			t.Fatalf("facet type want 4, got %d", resp.FacetTotals["type"])
		}
		if resp.FacetTotals["origin"] != 5 {
			t.Fatalf("facet origin (unfiltered by type) want 5, got %d", resp.FacetTotals["origin"])
		}
	})

	t.Run("ip filter", func(t *testing.T) {
		resp := search("ip=3.3.3.3")
		if want := []int{3}; !reflect.DeepEqual(rowIDs(resp.Rows), want) {
			t.Fatalf("want %v, got %v", want, rowIDs(resp.Rows))
		}
	})

	t.Run("scenario filter", func(t *testing.T) {
		resp := search("scenario=manual-ban")
		if want := []int{3}; !reflect.DeepEqual(rowIDs(resp.Rows), want) {
			t.Fatalf("want %v, got %v", want, rowIDs(resp.Rows))
		}
	})

	t.Run("q substring", func(t *testing.T) {
		resp := search("q=probing")
		if want := []int{5}; !reflect.DeepEqual(rowIDs(resp.Rows), want) {
			t.Fatalf("want %v, got %v", want, rowIDs(resp.Rows))
		}
	})

	t.Run("paging", func(t *testing.T) {
		resp := search("per=2&page=2")
		if want := []int{3, 2}; !reflect.DeepEqual(rowIDs(resp.Rows), want) {
			t.Fatalf("want %v, got %v", want, rowIDs(resp.Rows))
		}
		if resp.Total != 5 || resp.Pages != 3 || resp.Page != 2 || resp.Per != 2 {
			t.Fatalf("unexpected paging: %+v", resp)
		}
	})

	t.Run("page clamped to pages", func(t *testing.T) {
		resp := search("per=2&page=99")
		if resp.Page != 3 {
			t.Fatalf("page should clamp to 3, got %d", resp.Page)
		}
	})
}

func TestAlertsCacheFullThenDeltaThenCap(t *testing.T) {
	resetSummaryCaches()
	var calls []string
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls = append(calls, r.URL.String())
		w.Header().Set("Content-Type", "application/json")
		if strings.Contains(r.URL.RawQuery, "since=") {
			fmt.Fprint(w, `[{"id":3,"source":{"ip":"3.3.3.3"}},{"id":4,"source":{"ip":"4.4.4.4"}}]`)
			return
		}
		fmt.Fprint(w, `[{"id":1,"source":{"ip":"1.1.1.1"}},{"id":2,"source":{"ip":"2.2.2.2"}}]`)
	}))
	defer srv.Close()
	a := &App{cfg: &Config{CrowdSecLAPIURL: srv.URL, CrowdSecAPIKey: "k"}, csClient: srv.Client()}

	rows, mode, _, err := a.csAlerts(context.Background(), 2, false)
	if err != nil {
		t.Fatalf("first fetch: %v", err)
	}
	if mode != "full" {
		t.Fatalf("first fetch should be full, got %s", mode)
	}
	if len(rows) != 2 {
		t.Fatalf("expected 2 rows, got %d", len(rows))
	}
	if strings.Contains(calls[0], "since=") {
		t.Fatalf("first fetch must not use since=, got %s", calls[0])
	}

	csAlertCache.mu.Lock()
	csAlertCache.synced = time.Now().Add(-59 * time.Minute)
	csAlertCache.mu.Unlock()

	rows2, mode2, _, err2 := a.csAlerts(context.Background(), 2, false)
	if err2 != nil {
		t.Fatalf("second fetch: %v", err2)
	}
	if mode2 != "delta" {
		t.Fatalf("second fetch should be delta, got %s", mode2)
	}
	if !strings.Contains(calls[len(calls)-1], "since=") {
		t.Fatalf("delta fetch must use since=, got %s", calls[len(calls)-1])
	}
	if len(rows2) != 2 {
		t.Fatalf("merged cache should stay capped at the limit, got %d rows", len(rows2))
	}
	got := []int64{}
	for _, r := range rows2 {
		got = append(got, decID(r))
	}
	if want := []int64{4, 3}; !reflect.DeepEqual(got, want) {
		t.Fatalf("expected only the newest ids kept, want %v got %v", want, got)
	}
}

func TestAlertsCacheServesStaleOnFailure(t *testing.T) {
	resetSummaryCaches()
	fail := false
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if fail {
			w.WriteHeader(http.StatusBadGateway)
			w.Write([]byte(`{"message":"down"}`))
			return
		}
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprint(w, `[{"id":1,"source":{"ip":"1.1.1.1"}}]`)
	}))
	defer srv.Close()
	a := &App{cfg: &Config{CrowdSecLAPIURL: srv.URL, CrowdSecAPIKey: "k"}, csClient: srv.Client()}

	if _, _, _, err := a.csAlerts(context.Background(), 10, false); err != nil {
		t.Fatalf("initial read: %v", err)
	}

	csAlertCache.mu.Lock()
	csAlertCache.synced = time.Now().Add(-20 * time.Minute)
	csAlertCache.mu.Unlock()
	fail = true

	rows, mode, _, err := a.csAlerts(context.Background(), 10, false)
	if err != nil {
		t.Fatalf("a dead LAPI with a ready cache must not error, got %v", err)
	}
	if !strings.HasPrefix(mode, "stale:") {
		t.Fatalf("expected a stale mode after a 20 minute old cache and a dead LAPI, got %s", mode)
	}
	if len(rows) != 1 {
		t.Fatalf("expected the last good read served from cache, got %d rows", len(rows))
	}
}

func TestPostDecisionResetsAlertsCache(t *testing.T) {
	resetSummaryCaches()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if r.URL.Path == "/v1/alerts" && r.Method == http.MethodGet {
			fmt.Fprint(w, `[{"id":1,"source":{"ip":"1.1.1.1"}}]`)
			return
		}
		if r.URL.Path == "/v1/alerts" && r.Method == http.MethodPost {
			fmt.Fprint(w, `[]`)
			return
		}
		w.WriteHeader(http.StatusNotFound)
	}))
	defer srv.Close()
	a := &App{cfg: &Config{CrowdSecLAPIURL: srv.URL, CrowdSecAPIKey: "k"}, csClient: srv.Client()}

	if _, _, _, err := a.csAlerts(context.Background(), 10, false); err != nil {
		t.Fatalf("priming the alert cache: %v", err)
	}
	csAlertCache.mu.Lock()
	ready := csAlertCache.ready
	csAlertCache.mu.Unlock()
	if !ready {
		t.Fatal("alert cache should be primed before the add-decision call")
	}

	body := strings.NewReader(`{"value":"9.9.9.9","type":"ban"}`)
	rec := httptest.NewRecorder()
	a.crowdsecAddDecisionHandler(rec, httptest.NewRequest(http.MethodPost, "/api/crowdsec/decisions", body))
	if rec.Code != http.StatusOK {
		t.Fatalf("add decision failed: %d %s", rec.Code, rec.Body)
	}

	csAlertCache.mu.Lock()
	defer csAlertCache.mu.Unlock()
	if csAlertCache.ready {
		t.Fatal("adding a decision must drop the alert cache too")
	}
}

func TestListEndpointsStillReturnArrays(t *testing.T) {
	resetSummaryCaches()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		if strings.HasPrefix(r.URL.Path, "/v1/decisions/stream") {
			fmt.Fprint(w, `{"new":[{"id":1,"origin":"cscli","value":"1.1.1.1","type":"ban","scope":"Ip"}],"deleted":[]}`)
			return
		}
		if r.URL.Path == "/v1/alerts" {
			fmt.Fprint(w, `[{"id":1,"source":{"ip":"1.1.1.1"}}]`)
			return
		}
		w.WriteHeader(http.StatusNotFound)
	}))
	defer srv.Close()
	a := &App{cfg: &Config{CrowdSecLAPIURL: srv.URL, CrowdSecAPIKey: "k"}, csClient: srv.Client()}

	rec := httptest.NewRecorder()
	a.crowdsecDecisionsHandler(rec, httptest.NewRequest(http.MethodGet, "/api/crowdsec/decisions", nil))
	var decisions []map[string]any
	if err := json.Unmarshal(rec.Body.Bytes(), &decisions); err != nil {
		t.Fatalf("decisions endpoint must still return a bare array: %v (%s)", err, rec.Body.String())
	}

	rec2 := httptest.NewRecorder()
	a.crowdsecAlertsHandler(rec2, httptest.NewRequest(http.MethodGet, "/api/crowdsec/alerts", nil))
	var alerts []map[string]any
	if err := json.Unmarshal(rec2.Body.Bytes(), &alerts); err != nil {
		t.Fatalf("alerts endpoint must still return a bare array: %v (%s)", err, rec2.Body.String())
	}
}
