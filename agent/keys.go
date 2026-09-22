package main

import (
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

type APIKey struct {
	ID         string     `json:"id"`
	Name       string     `json:"name"`
	KeyHash    string     `json:"key_hash"`
	CreatedAt  time.Time  `json:"created_at"`
	LastUsedAt *time.Time `json:"last_used_at,omitempty"`
}

type keyStore struct {
	mu           sync.RWMutex
	saveMu       sync.Mutex
	path         string
	keys         []APIKey
	lastUsedSave time.Time
}

func newKeyStore(dir string) *keyStore {
	ks := &keyStore{
		path: filepath.Join(dir, "api_keys.json"),
		keys: []APIKey{},
	}
	ks.load()
	return ks
}

func (ks *keyStore) load() {
	data, err := os.ReadFile(ks.path)
	if err != nil {
		return
	}
	var keys []APIKey
	if err := json.Unmarshal(data, &keys); err != nil {
		aside := fmt.Sprintf("%s.corrupt-%d", ks.path, time.Now().Unix())
		log.Printf("keys: %s is not valid JSON, moved it to %s and started without extra keys: %v", ks.path, aside, err)
		_ = os.Rename(ks.path, aside)
		ks.keys = []APIKey{}
		return
	}
	if keys == nil {
		keys = []APIKey{}
	}
	ks.keys = keys
}

func (ks *keyStore) persist() error {
	ks.saveMu.Lock()
	defer ks.saveMu.Unlock()
	ks.mu.RLock()
	snap := make([]APIKey, len(ks.keys))
	copy(snap, ks.keys)
	ks.mu.RUnlock()
	if err := os.MkdirAll(filepath.Dir(ks.path), 0o755); err != nil {
		return err
	}
	data, err := json.MarshalIndent(snap, "", "  ")
	if err != nil {
		return err
	}
	return writeFileAtomic(ks.path, data, 0o600)
}

func writeFileAtomic(path string, data []byte, mode os.FileMode) error {
	tmp, err := os.CreateTemp(filepath.Dir(path), filepath.Base(path)+".tmp-*")
	if err != nil {
		return writeFileInPlace(path, data, mode)
	}
	name := tmp.Name()
	_, werr := tmp.Write(data)
	serr := tmp.Sync()
	cerr := tmp.Chmod(mode)
	xerr := tmp.Close()
	if werr != nil || serr != nil || cerr != nil || xerr != nil {
		os.Remove(name)
		return writeFileInPlace(path, data, mode)
	}
	if err := os.Rename(name, path); err != nil {
		os.Remove(name)
		return writeFileInPlace(path, data, mode)
	}
	return nil
}

func writeFileInPlace(path string, data []byte, mode os.FileMode) error {
	fh, err := os.OpenFile(path, os.O_WRONLY|os.O_CREATE, mode)
	if err != nil {
		return err
	}
	defer fh.Close()
	if _, err := fh.Write(data); err != nil {
		return err
	}
	if err := fh.Truncate(int64(len(data))); err != nil {
		return err
	}
	if err := fh.Sync(); err != nil {
		return err
	}
	return os.Chmod(path, mode)
}

func hashKey(key string) string {
	h := sha256.Sum256([]byte(key))
	return hex.EncodeToString(h[:])
}

func (ks *keyStore) validate(key string) bool {
	hash := hashKey(key)
	ks.mu.Lock()
	defer ks.mu.Unlock()
	for i, k := range ks.keys {
		if subtle.ConstantTimeCompare([]byte(k.KeyHash), []byte(hash)) == 1 {
			now := time.Now().UTC()
			ks.keys[i].LastUsedAt = &now
			if now.Sub(ks.lastUsedSave) > time.Minute {
				ks.lastUsedSave = now
				go ks.persist()
			}
			return true
		}
	}
	return false
}

func (ks *keyStore) list() []map[string]any {
	ks.mu.RLock()
	defer ks.mu.RUnlock()
	out := make([]map[string]any, 0, len(ks.keys))
	for _, k := range ks.keys {
		m := map[string]any{
			"id":         k.ID,
			"name":       k.Name,
			"created_at": k.CreatedAt,
		}
		if k.LastUsedAt != nil {
			m["last_used_at"] = k.LastUsedAt
		}
		out = append(out, m)
	}
	return out
}

func (ks *keyStore) create(name string) (string, string, error) {
	raw := make([]byte, 32)
	if _, err := rand.Read(raw); err != nil {
		return "", "", err
	}
	rawKey := hex.EncodeToString(raw)
	idBytes := make([]byte, 8)
	_, _ = rand.Read(idBytes)

	k := APIKey{
		ID:        hex.EncodeToString(idBytes),
		Name:      name,
		KeyHash:   hashKey(rawKey),
		CreatedAt: time.Now().UTC(),
	}
	ks.mu.Lock()
	ks.keys = append(ks.keys, k)
	ks.mu.Unlock()
	return k.ID, rawKey, ks.persist()
}

func (ks *keyStore) delete(id string) bool {
	ks.mu.Lock()
	found := false
	for i, k := range ks.keys {
		if k.ID == id {
			ks.keys = append(ks.keys[:i], ks.keys[i+1:]...)
			found = true
			break
		}
	}
	ks.mu.Unlock()
	if found {
		_ = ks.persist()
	}
	return found
}

func (a *App) keysListHandler(w http.ResponseWriter, r *http.Request) {
	jsonOK(w, map[string]any{"keys": a.keys.list()})
}

func (a *App) keysCreateHandler(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Name string `json:"name"`
	}
	_ = json.NewDecoder(r.Body).Decode(&body)
	name := strings.TrimSpace(body.Name)
	if name == "" {
		jsonErrorCode(w, "name_required", nil, "name is required", http.StatusBadRequest)
		return
	}
	id, rawKey, err := a.keys.create(name)
	if err != nil {
		jsonErrorCode(w, "key_create_failed", map[string]any{"detail": err.Error()}, "failed to create key: "+err.Error(), http.StatusInternalServerError)
		return
	}
	jsonOK(w, map[string]any{"ok": true, "id": id, "name": name, "key": rawKey})
}

func (a *App) keysDeleteHandler(w http.ResponseWriter, r *http.Request, id string) {
	if !a.keys.delete(id) {
		jsonErrorCode(w, "key_not_found", nil, "key not found", http.StatusNotFound)
		return
	}
	jsonOK(w, map[string]any{"ok": true})
}
