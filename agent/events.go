package main

import (
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strconv"
	"sync"
	"time"
)

const eventRingSize = 100

type Event struct {
	ID      int64  `json:"id"`
	At      int64  `json:"at"`
	Kind    string `json:"kind"`
	Message string `json:"message"`
}

type eventLog struct {
	mu     sync.Mutex
	nextID int64
	items  []Event
	boot   string
}

func newEventLog() *eventLog {
	return &eventLog{nextID: 1, boot: newBootToken()}
}

func newBootToken() string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return strconv.FormatInt(time.Now().UnixNano(), 36)
	}
	return hex.EncodeToString(b)
}

func (e *eventLog) record(kind, message string) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.items = append(e.items, Event{
		ID:      e.nextID,
		At:      time.Now().Unix(),
		Kind:    kind,
		Message: message,
	})
	e.nextID++
	if len(e.items) > eventRingSize {
		e.items = append([]Event(nil), e.items[len(e.items)-eventRingSize:]...)
	}
}

func (e *eventLog) since(id int64) []Event {
	e.mu.Lock()
	defer e.mu.Unlock()
	out := make([]Event, 0, len(e.items))
	for _, item := range e.items {
		if item.ID > id {
			out = append(out, item)
		}
	}
	return out
}

func (e *eventLog) latestID() int64 {
	e.mu.Lock()
	defer e.mu.Unlock()
	if len(e.items) == 0 {
		return 0
	}
	return e.items[len(e.items)-1].ID
}

func (a *App) failuref(kind, format string, args ...any) {
	msg := fmt.Sprintf(format, args...)
	log.Printf("%s: %s", kind, msg)
	if a.events != nil {
		a.events.record(kind, msg)
	}
}

func (a *App) eventsHandler(w http.ResponseWriter, r *http.Request) {
	var since int64
	if raw := r.URL.Query().Get("since"); raw != "" {
		parsed, err := strconv.ParseInt(raw, 10, 64)
		if err != nil || parsed < 0 {
			jsonErrorCode(w, "invalid_since", nil, "since must be a non-negative integer", http.StatusBadRequest)
			return
		}
		since = parsed
	}
	if boot := r.URL.Query().Get("boot"); boot != "" && boot != a.events.boot {
		since = 0
	}
	items := a.events.since(since)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{
		"events": items,
		"latest": a.events.latestID(),
		"boot":   a.events.boot,
	})
}
