package main

import (
	"crypto/sha256"
	"encoding/hex"
	"os"
	"path/filepath"
	"reflect"
	"sort"
	"strings"

	"gopkg.in/yaml.v3"
)

type routeDep struct {
	Scope string
	Kind  string
	Name  string
}

type sharedChange struct {
	Dep   routeDep
	Path  string
	File  string
	Value any
}

func sectionMap(cfg map[string]any, scope, kind string) map[string]any {
	scoped, _ := cfg[scope].(map[string]any)
	if scoped == nil {
		return nil
	}
	holder, _ := scoped[kind].(map[string]any)
	return holder
}

func routeTransportName(svc any) string {
	svcMap, _ := svc.(map[string]any)
	if svcMap == nil {
		return ""
	}
	lb, _ := svcMap["loadBalancer"].(map[string]any)
	if lb == nil {
		return ""
	}
	name, _ := lb["serversTransport"].(string)
	return name
}

func localMiddlewareNames(router map[string]any) []string {
	var names []string
	list, _ := router["middlewares"].([]any)
	for _, raw := range list {
		name, _ := raw.(string)
		if name == "" {
			continue
		}
		short := name
		if idx := strings.Index(name, "@"); idx >= 0 {
			if name[idx+1:] != "file" {
				continue
			}
			short = name[:idx]
		}
		if short != "" && !slicesContains(names, short) {
			names = append(names, short)
		}
	}
	return names
}

func slicesContains(list []string, want string) bool {
	for _, item := range list {
		if item == want {
			return true
		}
	}
	return false
}

func routeDependencyNames(proto string, router map[string]any, svc any) []routeDep {
	var deps []routeDep
	if transport := routeTransportName(svc); transport != "" {
		deps = append(deps, routeDep{proto, "serversTransports", transport})
	}
	for _, name := range localMiddlewareNames(router) {
		deps = append(deps, routeDep{proto, "middlewares", name})
	}
	if tls, ok := router["tls"].(map[string]any); ok {
		option, _ := tls["options"].(string)
		if idx := strings.Index(option, "@"); idx >= 0 {
			option = option[:idx]
		}
		if option != "" {
			deps = append(deps, routeDep{"tls", "options", option})
		}
	}
	return deps
}

func readConfigFile(path string) map[string]any {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var cfg map[string]any
	if err := yaml.Unmarshal(data, &cfg); err != nil {
		return nil
	}
	return cfg
}

func (a *App) findDefinition(dep routeDep, ownCfg map[string]any, ownPath string) (any, string) {
	if found, ok := sectionMap(ownCfg, dep.Scope, dep.Kind)[dep.Name]; ok {
		return found, ownPath
	}
	for _, path := range a.configFiles() {
		if sameFile(path, ownPath) {
			continue
		}
		if found, ok := sectionMap(readConfigFile(path), dep.Scope, dep.Kind)[dep.Name]; ok {
			return found, path
		}
	}
	return nil, ""
}

func sameFile(left, right string) bool {
	if left == "" || right == "" {
		return false
	}
	leftAbs, err := filepath.Abs(left)
	if err != nil {
		return left == right
	}
	rightAbs, err := filepath.Abs(right)
	if err != nil {
		return left == right
	}
	return leftAbs == rightAbs
}

func (a *App) addRouteDependencies(out map[string]any, cfg map[string]any, proto string,
	router map[string]any, svc any, ownPath string) map[string]any {
	origins := map[string]any{}
	for _, dep := range routeDependencyNames(proto, router, svc) {
		defined, path := a.findDefinition(dep, cfg, ownPath)
		if path == "" {
			continue
		}
		scoped, _ := out[dep.Scope].(map[string]any)
		if scoped == nil {
			scoped = map[string]any{}
			out[dep.Scope] = scoped
		}
		holder, _ := scoped[dep.Kind].(map[string]any)
		if holder == nil {
			holder = map[string]any{}
			scoped[dep.Kind] = holder
		}
		holder[dep.Name] = defined

		originScope, _ := origins[dep.Scope].(map[string]any)
		if originScope == nil {
			originScope = map[string]any{}
			origins[dep.Scope] = originScope
		}
		originKind, _ := originScope[dep.Kind].(map[string]any)
		if originKind == nil {
			originKind = map[string]any{}
			originScope[dep.Kind] = originKind
		}
		originKind[dep.Name] = filepath.Base(path)
	}
	return origins
}

func fileReference(raw string) string {
	name := strings.TrimSpace(raw)
	idx := strings.Index(name, "@")
	if idx < 0 {
		return name
	}
	if name[idx+1:] != "file" {
		return ""
	}
	return name[:idx]
}

func (a *App) referenceExists(newData, cfg map[string]any, targetPath string, dep routeDep) bool {
	if _, ok := sectionMap(newData, dep.Scope, dep.Kind)[dep.Name]; ok {
		return true
	}
	_, path := a.findDefinition(dep, cfg, targetPath)
	return path != ""
}

func (a *App) missingRouteReferences(newData, cfg map[string]any, targetPath string) []routeDep {
	var missing []routeDep
	check := func(scope, kind, raw string) {
		name := fileReference(raw)
		if name == "" || (kind == "options" && name == "default") {
			return
		}
		dep := routeDep{scope, kind, name}
		if a.referenceExists(newData, cfg, targetPath, dep) {
			return
		}
		for _, seen := range missing {
			if seen == dep {
				return
			}
		}
		missing = append(missing, dep)
	}
	for _, proto := range []string{"http", "tcp", "udp"} {
		for rname, raw := range sectionMap(newData, proto, "routers") {
			router, _ := raw.(map[string]any)
			if router == nil {
				continue
			}
			list, _ := router["middlewares"].([]any)
			for _, item := range list {
				if name, ok := item.(string); ok {
					check(proto, "middlewares", name)
				}
			}
			svcName := rname
			if sn, ok := router["service"].(string); ok && sn != "" {
				svcName = sn
			}
			check(proto, "services", svcName)
			if tls, ok := router["tls"].(map[string]any); ok {
				if option, ok := tls["options"].(string); ok {
					check("tls", "options", option)
				}
			}
		}
		for _, svc := range sectionMap(newData, proto, "services") {
			check(proto, "serversTransports", routeTransportName(svc))
		}
	}
	return missing
}

func writableFile(path string) error {
	fh, err := os.OpenFile(path, os.O_WRONLY, 0o600)
	if err != nil {
		return err
	}
	return fh.Close()
}

func fileFingerprint(path string) string {
	data, err := os.ReadFile(path)
	if err != nil {
		return ""
	}
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:])[:16]
}

func (a *App) dependencyFingerprints(origins map[string]any, ownPath string) map[string]string {
	prints := map[string]string{filepath.Base(ownPath): fileFingerprint(ownPath)}
	for _, kinds := range origins {
		kindMap, _ := kinds.(map[string]any)
		for _, names := range kindMap {
			nameMap, _ := names.(map[string]any)
			for _, where := range nameMap {
				base, _ := where.(string)
				if base == "" || prints[base] != "" {
					continue
				}
				for _, path := range a.configFiles() {
					if filepath.Base(path) == base {
						prints[base] = fileFingerprint(path)
						break
					}
				}
			}
		}
	}
	return prints
}

func dependencyScopes(data map[string]any) []routeDep {
	var scopes []routeDep
	for _, proto := range []string{"http", "tcp", "udp"} {
		for _, kind := range []string{"serversTransports", "middlewares"} {
			if len(sectionMap(data, proto, kind)) > 0 {
				scopes = append(scopes, routeDep{Scope: proto, Kind: kind})
			}
		}
	}
	if len(sectionMap(data, "tls", "options")) > 0 {
		scopes = append(scopes, routeDep{Scope: "tls", Kind: "options"})
	}
	return scopes
}

func (a *App) sectionsDefinedElsewhere(newData, cfg map[string]any, targetPath string) (
	unchanged, changed []sharedChange) {
	for _, scope := range dependencyScopes(newData) {
		for name, edited := range sectionMap(newData, scope.Scope, scope.Kind) {
			dep := routeDep{scope.Scope, scope.Kind, name}
			defined, path := a.findDefinition(dep, cfg, targetPath)
			if path == "" || sameFile(path, targetPath) {
				continue
			}
			change := sharedChange{Dep: dep, Path: path, File: filepath.Base(path), Value: edited}
			if reflect.DeepEqual(edited, defined) {
				unchanged = append(unchanged, change)
			} else {
				changed = append(changed, change)
			}
		}
	}
	return unchanged, changed
}

func (a *App) routesUsing(dep routeDep) []string {
	services := map[string]bool{}
	if dep.Kind == "serversTransports" {
		for _, path := range a.configFiles() {
			for name, svc := range sectionMap(readConfigFile(path), dep.Scope, "services") {
				if routeTransportName(svc) == dep.Name {
					services[name] = true
				}
			}
		}
	}
	seen := map[string]bool{}
	for _, path := range a.configFiles() {
		cfg := readConfigFile(path)
		for _, proto := range []string{"http", "tcp", "udp"} {
			if dep.Kind != "options" && proto != dep.Scope {
				continue
			}
			for rname, raw := range sectionMap(cfg, proto, "routers") {
				router, _ := raw.(map[string]any)
				if router == nil {
					continue
				}
				hit := false
				switch dep.Kind {
				case "middlewares":
					hit = slicesContains(localMiddlewareNames(router), dep.Name)
				case "serversTransports":
					svcName := rname
					if sn, ok := router["service"].(string); ok && sn != "" {
						svcName = sn
					}
					hit = services[svcName]
				default:
					tls, _ := router["tls"].(map[string]any)
					option, _ := tls["options"].(string)
					if idx := strings.Index(option, "@"); idx >= 0 {
						option = option[:idx]
					}
					hit = option == dep.Name
				}
				if hit {
					seen[rname] = true
				}
			}
		}
	}
	routes := make([]string, 0, len(seen))
	for name := range seen {
		routes = append(routes, name)
	}
	sort.Strings(routes)
	return routes
}

func (a *App) sharedChangePrompt(changes []sharedChange) []map[string]any {
	prompt := make([]map[string]any, 0, len(changes))
	for _, change := range changes {
		routes := a.routesUsing(change.Dep)
		shown := routes
		if len(shown) > 3 {
			shown = shown[:3]
		}
		prompt = append(prompt, map[string]any{
			"name": change.Dep.Name, "kind": change.Dep.Kind, "file": change.File,
			"usedBy": map[string]any{"count": len(routes), "routes": shown},
		})
	}
	return prompt
}

func (a *App) renamedSharedDefinition(newData, cfg map[string]any, targetPath string) (string, string) {
	for _, proto := range []string{"http", "tcp"} {
		for _, kind := range []string{"middlewares", "serversTransports"} {
			present := sectionMap(newData, proto, kind)
			for rname, raw := range sectionMap(newData, proto, "routers") {
				router, _ := raw.(map[string]any)
				if router == nil {
					continue
				}
				svcName := rname
				if sn, ok := router["service"].(string); ok && sn != "" {
					svcName = sn
				}
				svc := sectionMap(newData, proto, "services")[svcName]
				for _, dep := range routeDependencyNames(proto, router, svc) {
					if dep.Kind != kind || dep.Scope != proto {
						continue
					}
					if _, still := present[dep.Name]; still {
						continue
					}
					_, path := a.findDefinition(dep, cfg, targetPath)
					if path == "" || sameFile(path, targetPath) {
						continue
					}
					for candidate := range present {
						if _, where := a.findDefinition(routeDep{proto, kind, candidate}, cfg,
							targetPath); where == "" {
							return dep.Name, filepath.Base(path)
						}
					}
				}
			}
		}
	}
	return "", ""
}

func (a *App) writeSharedDefinitions(changes []sharedChange) error {
	paths := map[string]bool{}
	for _, change := range changes {
		paths[change.Path] = true
	}
	ordered := make([]string, 0, len(paths))
	for path := range paths {
		ordered = append(ordered, path)
	}
	sort.Strings(ordered)
	for _, path := range ordered {
		cfg := readConfigFile(path)
		if cfg == nil {
			cfg = map[string]any{}
		}
		for _, change := range changes {
			if change.Path != path {
				continue
			}
			scoped, _ := cfg[change.Dep.Scope].(map[string]any)
			if scoped == nil {
				scoped = map[string]any{}
				cfg[change.Dep.Scope] = scoped
			}
			holder, _ := scoped[change.Dep.Kind].(map[string]any)
			if holder == nil {
				holder = map[string]any{}
				scoped[change.Dep.Kind] = holder
			}
			holder[change.Dep.Name] = change.Value
		}
		if err := a.createFileBak(path, filepath.Base(path)); err != nil {
			return err
		}
		out, err := yaml.Marshal(cfg)
		if err != nil {
			return err
		}
		if err := atomicWrite(path, out); err != nil {
			return err
		}
	}
	return nil
}
