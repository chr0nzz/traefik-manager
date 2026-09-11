let _rmEditingGroupIdx = -1;

function rmRenderGroupsList() {
    const list = document.getElementById('rmGroupsList');
    if (!list) return;
    const groups = _rmConfig.custom_groups || [];
    const gc = document.getElementById('rmGroupsCount');
    if (gc) gc.textContent = groups.length;
    if (!groups.length) {
        list.innerHTML = `<div class="text-xs py-3 text-center" style="color:var(--muted)">No custom groups yet.</div>`;
        return;
    }
    list.innerHTML = groups.map((g, i) => {
        const color = RM_GROUP_COLORS[i % RM_GROUP_COLORS.length];
        if (_rmEditingGroupIdx === i) {
            return `<div class="flex items-center gap-2 py-2" style="border-bottom:1px solid var(--border)">
                <span style="width:8px;height:8px;border-radius:50%;background:${color};flex-shrink:0;display:inline-block"></span>
                <input type="text" id="rmGroupEditInput" class="input-field" style="flex:1;height:28px;font-size:12px" value="${_esc(g.name)}" onkeydown="if(event.key==='Enter')rmSaveGroupRename(${i});else if(event.key==='Escape')rmCancelGroupEdit()">
                <button onclick="rmSaveGroupRename(${i})" class="btn-icon" style="padding:3px 6px;flex-shrink:0"><i class="ph-bold ph-check text-xs" style="color:var(--green)"></i></button>
                <button onclick="rmCancelGroupEdit()" class="btn-icon" style="padding:3px 6px;flex-shrink:0"><i class="ph-bold ph-x text-xs" style="color:var(--muted)"></i></button>
            </div>`;
        }
        return `<div class="flex items-center gap-2 py-2" style="border-bottom:1px solid var(--border)">
            <span style="width:8px;height:8px;border-radius:50%;background:${color};flex-shrink:0;display:inline-block"></span>
            <span class="text-xs font-semibold" style="color:var(--text);flex:1">${_esc(g.name)}</span>
            <button onclick="rmStartGroupEdit(${i})" class="btn-icon" style="padding:3px 6px;flex-shrink:0"><i class="ph-bold ph-pencil-simple text-xs" style="color:var(--muted)"></i></button>
            <button onclick="rmDeleteCustomGroup(${i})" class="btn-icon" style="padding:3px 6px;flex-shrink:0"><i class="ph-bold ph-trash text-xs" style="color:var(--muted)"></i></button>
        </div>`;
    }).join('');
    if (_rmEditingGroupIdx >= 0) {
        const input = document.getElementById('rmGroupEditInput');
        if (input) { input.focus(); input.select(); }
    }
}

window.rmOpenGroupsModal = function() {
    closeOtherPanels('rmGroupsModal');
    _rmEditingGroupIdx = -1;
    rmRenderGroupsList();
    rmRenderHiddenList();
    document.getElementById('rmGroupsModal').classList.add('open');
    document.getElementById('rmGroupsBackdrop').classList.add('open');
    if (!setDetailDockOpen(true)) document.body.style.overflow = 'hidden';
};

window.rmCloseGroupsModal = function() {
    _rmEditingGroupIdx = -1;
    setDetailDockOpen(false);
    document.getElementById('rmGroupsModal').classList.remove('open');
    document.getElementById('rmGroupsBackdrop').classList.remove('open');
    document.body.style.overflow = '';
};

function rmHiddenIds() {
    const ov = _rmConfig.route_overrides || {};
    return Object.keys(ov).filter(id => ov[id] && ov[id].hidden);
}

window.rmRenderHiddenList = function() {
    const el = document.getElementById('rmHiddenList');
    const cnt = document.getElementById('rmHiddenCount');
    if (!el) return;
    const ids = rmHiddenIds();
    if (cnt) cnt.textContent = ids.length;
    if (!ids.length) {
        el.innerHTML = '<div class="lg-note">Nothing is hidden. Use the pencil on a card to hide it.</div>';
        return;
    }
    const all = (typeof _rmAllRoutes !== 'undefined' ? _rmAllRoutes : []);
    const plain = v => String(v).includes('::') ? String(v).split('::').slice(1).join('::') : String(v);
    el.innerHTML = ids.map(id => {
        const r = all.find(x => x.id === id);
        const ov = (_rmConfig.route_overrides || {})[id] || {};
        const name = ov.display_name || (r && r.name) || plain(id);
        return '<div class="lg-row">'
            + '<span class="lg-id"><span class="lg-name">' + _esc(name) + '</span></span>'
            + '<span class="lg-bad"></span>'
            + '<button type="button" class="sig-flag d-blue" data-dsk="act=unhide;id=' + _esc(encodeURIComponent(id)) + '"'
            + ' title="' + _esc('Show ' + name + ' on the dashboard again') + '">'
            + '<i class="ph-bold ph-eye"></i>show</button></div>';
    }).join('');
};

window.rmUnhideRoute = async function(routeId) {
    const ov = (_rmConfig.route_overrides || {})[routeId];
    if (!ov) return;
    delete ov.hidden;
    if (!Object.keys(ov).length) delete _rmConfig.route_overrides[routeId];
    await rmSaveConfig();
    rmRenderHiddenList();
    if (window.rmInvalidateGroups) window.rmInvalidateGroups();
};

window.rmStartGroupEdit = function(i) {
    _rmEditingGroupIdx = i;
    rmRenderGroupsList();
};

window.rmCancelGroupEdit = function() {
    _rmEditingGroupIdx = -1;
    rmRenderGroupsList();
};

window.rmSaveGroupRename = async function(i) {
    const input = document.getElementById('rmGroupEditInput');
    if (!input) return;
    const newName = input.value.trim();
    if (!newName) return;
    const oldName = _rmConfig.custom_groups[i].name;
    _rmConfig.custom_groups[i].name = newName;
    if (oldName !== newName && _rmConfig.route_overrides) {
        Object.values(_rmConfig.route_overrides).forEach(ov => {
            if (ov.group === oldName) ov.group = newName;
        });
    }
    _rmEditingGroupIdx = -1;
    await rmSaveConfig();
    rmRenderGroupsList();
    if (window.rmInvalidateGroups) window.rmInvalidateGroups();
};

window.rmAddCustomGroup = async function() {
    const nameEl = document.getElementById('rmNewGroupName');
    const name   = nameEl.value.trim();
    if (!name) return;
    _rmConfig.custom_groups.push({ name });
    await rmSaveConfig();
    rmRenderGroupsList();
    nameEl.value = '';
    if (window.rmInvalidateGroups) window.rmInvalidateGroups();
};

window.rmDeleteCustomGroup = async function(i) {
    const removed = _rmConfig.custom_groups.splice(i, 1)[0];
    if (removed && _rmConfig.route_overrides) {
        Object.values(_rmConfig.route_overrides).forEach(ov => {
            if (ov.group === removed.name) delete ov.group;
        });
    }
    await rmSaveConfig();
    rmRenderGroupsList();
    if (window.rmInvalidateGroups) window.rmInvalidateGroups();
};

let _rmEditRouteId   = null;
let _rmEditIconType  = 'auto';

window.rmOpenEditModal = function(routeId) {
    closeOtherPanels('rmEditModal');
    _rmEditRouteId = routeId;
    const ov = (_rmConfig.route_overrides || {})[routeId] || {};

    const route = (typeof _rmAllRoutes !== 'undefined' ? _rmAllRoutes : [])
        .find(r => r.id === routeId);
    const title = document.getElementById('rmEditModalTitle');
    if (title) {
        const shown = ov.display_name || (route && route.name)
            || (String(routeId).includes('::') ? String(routeId).split('::').slice(1).join('::') : routeId);
        title.textContent = shown || 'Card settings';
        title.title = routeId;
    }

    document.getElementById('rmEditDisplayName').value = ov.display_name || '';
    document.getElementById('rmEditUrl').value = ov.url || '';
    document.getElementById('rmEditLinkDisabled').checked = !!ov.link_disabled;

    _rmEditIconType = ov.icon_type || 'auto';
    document.getElementById('rmEditIconSlug').value = ov.icon_slug || '';
    document.getElementById('rmEditIconUrl').value  = ov.icon_url  || '';
    rmEditSetIconType(_rmEditIconType);

    const sel = document.getElementById('rmEditGroup');
    sel.innerHTML = '<option value="">Auto-detect</option>';
    const allGroups = [
        ...(_rmConfig.custom_groups || []).map(g => g.name),
        ...['Media','Monitoring','Infrastructure','Security','Home','Files & Data','Network','Dev','Servers','Other']
    ];
    allGroups.forEach(name => {
        const opt = document.createElement('option');
        opt.value = name;
        opt.textContent = name;
        opt.selected = (ov.group || '') === name;
        sel.appendChild(opt);
    });

    const hid = document.getElementById('rmEditHidden');
    if (hid) hid.checked = !!ov.hidden;

    document.getElementById('rmEditModal').classList.add('open');
    document.getElementById('rmEditBackdrop').classList.add('open');
    if (!setDetailDockOpen(true)) document.body.style.overflow = 'hidden';
};

window.rmCloseEditModal = function() {
    setDetailDockOpen(false);
    document.getElementById('rmEditModal').classList.remove('open');
    document.getElementById('rmEditBackdrop').classList.remove('open');
    document.body.style.overflow = '';
    _rmEditRouteId = null;
};

window.rmEditSetIconType = function(type) {
    _rmEditIconType = type;
    ['auto','slug','url'].forEach(t => {
        document.getElementById(`rmEditIconBtn${t.charAt(0).toUpperCase()+t.slice(1)}`).classList.toggle('active', t === type);
    });
    document.getElementById('rmEditIconSlugRow').style.display = type === 'slug' ? 'block' : 'none';
    document.getElementById('rmEditIconUrlRow').style.display  = type === 'url'  ? 'block' : 'none';
    rmEditPreviewIcon();
};

window.rmEditPreviewIcon = function() {
    const prev  = document.getElementById('rmEditIconPreview');
    const label = document.getElementById('rmEditIconPreviewLabel');
    let url = '', autoSlug = '';
    if (_rmEditIconType === 'slug') {
        const slug = document.getElementById('rmEditIconSlug').value.trim();
        if (slug) url = `${RM_ICON_CDN}/${slug}.png`;
    } else if (_rmEditIconType === 'url') {
        url = document.getElementById('rmEditIconUrl').value.trim();
    } else if (_rmEditRouteId) {
        const route = (typeof _rmAllRoutes !== 'undefined' ? _rmAllRoutes : [])
            .find(r => r.id === _rmEditRouteId);
        autoSlug = route
            ? window.rmIconSlug(route)
            : _rmEditRouteId.split('@')[0].replace(/:\d+$/, '')
                .replace(/[-_](?:service|svc|router|app|container|pod)s?$/i, '')
                .toLowerCase().replace(/[^a-z0-9-]/g, '');
        url = `${RM_ICON_CDN}/${autoSlug}.png`;
    }
    if (url) {
        prev.dataset.slug = autoSlug;
        prev.src = url;
        prev.style.display = 'block';
        label.textContent  = _rmEditIconType === 'auto' ? 'Auto-detected' : '';
        prev.onerror = () => {
            const before = prev.dataset.slug;
            if (autoSlug && before) {
                window.rmIconFallback(prev);
                if (prev.dataset.slug !== before && prev.style.display !== 'none') return;
            }
            prev.style.display = 'none';
            label.textContent = 'No icon found';
        };
    } else {
        prev.style.display = 'none';
        label.textContent  = '';
    }
};

window.rmSaveRouteEdit = async function() {
    if (!_rmEditRouteId) return;
    if (!_rmConfig.route_overrides) _rmConfig.route_overrides = {};
    const ov = {};
    const dn = document.getElementById('rmEditDisplayName').value.trim();
    if (dn) ov.display_name = dn;
    ov.icon_type = _rmEditIconType;
    if (_rmEditIconType === 'slug') ov.icon_slug = document.getElementById('rmEditIconSlug').value.trim();
    if (_rmEditIconType === 'url')  ov.icon_url  = document.getElementById('rmEditIconUrl').value.trim();
    const grp = document.getElementById('rmEditGroup').value;
    if (grp) ov.group = grp;
    const linkUrl = document.getElementById('rmEditUrl').value.trim();
    if (linkUrl) ov.url = linkUrl;
    if (document.getElementById('rmEditLinkDisabled').checked) ov.link_disabled = true;
    if (document.getElementById('rmEditHidden')?.checked) ov.hidden = true;
    _rmConfig.route_overrides[_rmEditRouteId] = ov;
    await rmSaveConfig();
    rmCloseEditModal();
    if (window.rmInvalidateGroups) window.rmInvalidateGroups();
};

(function() {

const POD_RULES = [
    { name: 'Media',          icon: 'ph-film-strip',          keywords: ['plex','jellyfin','emby','navidrome','kavita','komga','audiobookshelf','sonarr','radarr','lidarr','readarr','whisparr','prowlarr','qbittorrent','transmission','deluge','sabnzbd','nzbget','bazarr','tautulli','overseerr','requestrr','immich','photoprism','pigallery','damselfly'] },
    { name: 'Monitoring',     icon: 'ph-chart-line-up',       keywords: ['grafana','prometheus','alertmanager','loki','uptime','kuma','glances','netdata','zabbix','influx','telegraf','speedtest','myspeed','healthchecks','statping','gatus','scrutiny'] },
    { name: 'Infrastructure', icon: 'ph-wrench',              keywords: ['traefik','portainer','proxmox','cockpit','nginx','caddy','haproxy','watchtower','dozzle','komodo','flint','gitea','gitlab','forgejo','drone','jenkins','vault','consul','nomad','ansible','terraform','penpot','n8n','windmill'] },
    { name: 'Security',       icon: 'ph-shield-check',        keywords: ['authentik','authelia','vaultwarden','bitwarden','crowdsec','fail2ban','wireguard','vpn','keycloak','zitadel','casdoor','lldap','kanidm'] },
    { name: 'Home',           icon: 'ph-house',               keywords: ['homeassistant','home-assistant','nodered','node-red','esphome','zigbee2mqtt','z2m','frigate','scrypted','wyze','tuya','matter','openhabing'] },
    { name: 'Files & Data',   icon: 'ph-folder-open',         keywords: ['nextcloud','seafile','filebrowser','syncthing','paperless','mealie','tandoor','grocy','bookstack','wiki','notion','obsidian','miniflux','freshrss','wallabag','linkding','shlink'] },
    { name: 'Network',        icon: 'ph-network',             keywords: ['pihole','adguard','unifi','technitium','bind','nginx-proxy','ddclient','cloudflare','tailscale','zerotier','headscale','netbird'] },
    { name: 'Dev',            icon: 'ph-code',                keywords: ['gitea','gitlab','forgejo','github','gogs','drone','jenkins','argocd','harbor','registry','sonar','nexus','artifactory','semaphore','woodpecker','act','renovate','dependabot','code-server','coder','vscode','jupyter','jupyterlab','mlflow','airflow','prefect','dagster'] },
    { name: 'Servers',        icon: 'ph-desktop-tower',       keywords: ['proxmox','cockpit','idrac','ilo','ipmi','esxi','xcp','xen','hyperv','kvm','pve','unraid','truenas','freenas','opnsense','pfsense','mikrotik','synology','qnap','asustor'] },
];

const DASH_POD_LIMIT  = 6;
const DASH_ICON_LIMIT = 24;
const _dskColl = new Intl.Collator(undefined, { sensitivity: 'base' });

window.rmIconSlug = function(route) {
    let s = (route.service_name || route.name || '').split('@')[0];
    s = s.replace(/:\d+$/, '');
    s = s.replace(/[-_](?:service|svc|router|app|container|pod)s?$/i, '');
    return s.toLowerCase().replace(/[^a-z0-9-]/g, '');
};

function rmGetIconUrl(route) {
    const ov = (_rmConfig.route_overrides || {})[route.id] || {};
    if (ov.icon_type === 'url' && ov.icon_url)   return ov.icon_url;
    if (ov.icon_type === 'slug' && ov.icon_slug) return `${RM_ICON_CDN}/${ov.icon_slug}.png`;
    const tmName = (_rmConfig.tm_route_name || 'traefik-manager').toLowerCase();
    if ((route.name || '').toLowerCase() === tmName) return tmUrl('/static/icons/icon.png');
    return `${RM_ICON_CDN}/${window.rmIconSlug(route)}.png`;
}

function rmGetPod(route) {
    const ov = (_rmConfig.route_overrides || {})[route.id] || {};
    if (ov.group) {
        const custom = window.rmGetCustomGroups();
        const ci = custom.findIndex(g => g.name === ov.group);
        if (ci >= 0) return { name: custom[ci].name, icon: 'ph-tag' };
        const bi = POD_RULES.find(p => p.name === ov.group);
        if (bi) return bi;
    }
    const n = (route.name || '').toLowerCase().replace(/[-_]/g,'');
    const s = (route.service_name || '').toLowerCase().replace(/[-_]/g,'');
    for (const pod of POD_RULES) {
        if (pod.keywords.some(k => n.includes(k.replace(/[-_]/g,'')) || s.includes(k.replace(/[-_]/g,'')))) {
            return pod;
        }
    }
    return { name: 'Other', icon: 'ph-squares-four' };
}

let _dashProto    = 'all';
let _dashProvider = 'all';
let _dashSearch   = '';
let _dashDrawn    = false;
let _dashFilterTimer = null;

const _dskOpen  = new Set();
const _dskPods  = new Map();
let   _dskBound = false;

function dashPodDensity() {
    return typeof tmPref === 'function' && tmPref('dashPodDensity') === 'icons' ? 'icons' : 'list';
}

function _dskSpec(o) {
    return Object.keys(o).map(k => k + '=' + encodeURIComponent(o[k])).join(';');
}

function _dskParse(s) {
    const out = {};
    String(s || '').split(';').forEach(kv => {
        const i = kv.indexOf('=');
        if (i < 0) return;
        const k = kv.slice(0, i);
        const v = kv.slice(i + 1);
        try { out[k] = decodeURIComponent(v); } catch(_) { out[k] = v; }
    });
    return out;
}

function _dskSlug(s) {
    return String(s || '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '') || 'pod';
}

function _dskMono(name) {
    return _tmMono(name);
}

function _dskPlain(html) {
    return String(html || '')
        .replace(/<[^>]*>/g, '')
        .replace(/&lt;/g, '<').replace(/&gt;/g, '>')
        .replace(/&quot;/g, '"').replace(/&#39;/g, "'")
        .replace(/&amp;/g, '&');
}

function _dskTerse(msg) {
    const raw = String(msg || '').replace(/\s+/g, ' ').trim();
    if (!raw) return '';
    if (typeof _sdTerse === 'function') return _sdTerse(raw);
    return raw.length > 40 ? raw.slice(0, 39) + '...' : raw;
}

function _dskQualify(name, prov) {
    return String(name || '').includes('@') ? String(name) : String(name || '') + '@' + prov;
}

function _dskRouterState(r) {
    const proto = (r.protocol || 'http') + ':';
    const prov  = r.provider || 'file';
    return _rmRouterStatus[proto + _dskQualify(r.name, prov)]
        || _rmRouterStatus[proto + _dskQualify(r.id, prov)]
        || _rmRouterStatus[proto + (r.name || '')]
        || null;
}

function _dskSvcState(r) {
    const sn = r.service_name || '';
    if (!sn) return null;
    const proto = (r.protocol || 'http') + ':';
    const prov  = r.provider || 'file';
    return _rmSvcStatus[proto + _dskQualify(sn, prov)]
        || _rmSvcStatus[proto + sn]
        || null;
}

function _dskRuleBranches(rule) {
    const parts = [];
    let depth = 0, buf = '', tick = false;
    for (let i = 0; i < rule.length; i++) {
        const c = rule[i];
        if (c === '`') { tick = !tick; buf += c; continue; }
        if (!tick) {
            if (c === '(') depth++;
            else if (c === ')') depth--;
            else if (c === '|' && rule[i + 1] === '|' && depth === 0) {
                parts.push(buf); buf = ''; i++; continue;
            }
        }
        buf += c;
    }
    parts.push(buf);
    return parts;
}

function _dskWebUrl(u) {
    return /^https?:\/\/\S/i.test(String(u || '').trim()) ? String(u).trim() : null;
}

function _dashLaunchInfo(r, ov) {
    if (ov.link_disabled) return { url: null, why: 'link disabled for this route', glyph: 'ph-bold ph-link-simple-break' };
    if (ov.url) {
        const safe = _dskWebUrl(ov.url);
        return safe
            ? { url: safe, hosts: 1 }
            : { url: null, why: 'the link override is not an http or https URL. <b>Fix it in edit</b>', glyph: 'ph-bold ph-link-break' };
    }
    if ((r.protocol || 'http') !== 'http') return { url: null, why: 'stream route, nothing to open', glyph: 'ph-bold ph-terminal-window' };
    const rule = r.rule || '';
    if (!rule) return { url: null, why: 'no rule, nothing to open. <b>Set a link in edit</b>', glyph: 'ph-bold ph-link-break' };
    let picked = null, hosts = 0, wild = false;
    _dskRuleBranches(rule).forEach(b => {
        const hostRe = /(!?)\s*Host\(`([^`]+)`\)/g;
        let m, host = null;
        while ((m = hostRe.exec(b))) { if (m[1] !== '!') { host = m[2]; break; } }
        if (!host) return;
        if (host.indexOf('*') >= 0) { wild = true; return; }
        hosts++;
        if (!picked) picked = { host: host, path: (b.match(/PathPrefix\(`([^`]+)`\)/) || [])[1] || '' };
    });
    if (!picked) {
        const why = wild
            ? 'no launch URL, wildcard host. <b>Set one in edit</b>'
            : (/HostRegexp|HostSNI/.test(rule)
                ? 'no launch URL, pattern rule. <b>Set one in edit</b>'
                : 'no launch URL, the rule has no host. <b>Set one in edit</b>');
        return { url: null, why: why, glyph: 'ph-bold ph-link-break' };
    }
    return { url: (r.tls ? 'https' : 'http') + '://' + picked.host + picked.path, hosts: hosts };
}

function _dskState(r) {
    const ov  = (_rmConfig.route_overrides || {})[r.id] || {};
    const st  = _dskRouterState(r);
    const svc = _dskSvcState(r);
    const chk = (typeof window._rhGet === 'function') ? window._rhGet(r.id) : null;
    const lnk = _dashLaunchInfo(r, ov);
    const s = {
        ov: ov, url: lnk.url, hosts: lnk.hosts || 0,
        health: '', dot: '', dotTip: '', note: null, noteIc: '', noteCls: '',
    };

    if (r.enabled === false) {
        s.health  = 'idle';
        s.dot     = 'sig-cell-idle';
        s.dotTip  = 'Not served, the route is disabled';
        s.note    = 'disabled, not served by Traefik';
        s.noteIc  = 'ph-bold ph-power';
        s.noteCls = 'd-off';
    } else if (st && st.err) {
        s.health  = 'down';
        s.dot     = 'sig-cell-err';
        s.dotTip  = 'Traefik rejected this router' + (st.msg ? ' - ' + st.msg : '');
        s.note    = 'router error, <b>' + _esc(_dskTerse(st.msg) || 'see details') + '</b>';
        s.noteIc  = 'ph-fill ph-x-circle';
        s.noteCls = 'd-bad';
    } else if (st && !st.up) {
        s.health  = 'idle';
        s.dot     = 'sig-cell-idle';
        s.dotTip  = 'Traefik reports this router as not enabled';
        s.note    = 'router loaded but not enabled';
        s.noteIc  = 'ph-bold ph-power';
        s.noteCls = 'd-off';
    } else if (svc && svc.total && svc.up === 0) {
        s.health  = 'down';
        s.dot     = 'sig-cell-err';
        s.dotTip  = 'Backend unreachable - 0 of ' + svc.total + ' servers up';
        s.note    = 'backend unreachable <b>0/' + svc.total + ' servers</b>';
        s.noteIc  = 'ph-fill ph-warning-octagon';
        s.noteCls = 'd-bad';
    } else if (svc && svc.total && svc.up < svc.total) {
        s.health  = 'warn';
        s.dot     = 'sig-cell-warn';
        s.dotTip  = 'Backend degraded - ' + svc.up + ' of ' + svc.total + ' servers up';
        s.note    = 'backend degraded <b>' + svc.up + '/' + svc.total + ' servers</b>';
        s.noteIc  = 'ph-fill ph-warning';
        s.noteCls = 'd-warn';
    } else if (_rmStatusBlind) {
        s.dot    = 'sig-cell-idle';
        s.dotTip = 'Live status unavailable, the Traefik API did not answer';
    } else if (!st) {
        s.health  = 'unknown';
        s.dot     = 'sig-cell-idle dsk-dot-unk';
        s.dotTip  = 'Traefik has not reported this router';
        s.note    = 'declared here, not reported by Traefik';
        s.noteIc  = 'ph-bold ph-question';
        s.noteCls = 'd-off';
    } else if (svc && svc.total) {
        s.health = 'up';
        s.dot    = 'sig-cell-ok';
        s.dotTip = 'Router loaded, ' + svc.up + ' of ' + svc.total + ' backend servers up';
    } else if (chk && chk.state === 'down') {
        s.health  = 'down';
        s.dot     = 'sig-cell-err';
        s.dotTip  = (chk.source === 'traefik' || chk.source === 'servers')
            ? 'Backend unreachable - 0 of ' + ((chk.servers || {}).total || 0) + ' servers up'
            : 'Unreachable' + (chk.error ? ': ' + chk.error : '') + ' \u00b7 ' + _dskAgo(chk.at);
        s.note    = 'backend unreachable';
        s.noteIc  = 'ph-fill ph-warning-octagon';
        s.noteCls = 'd-bad';
    } else if (chk && chk.state === 'degraded') {
        const sv  = chk.servers || {};
        s.health  = 'warn';
        s.dot     = 'sig-cell-warn';
        s.dotTip  = 'Backend degraded - ' + sv.up + ' of ' + sv.total + ' servers up'
            + ((chk.down_servers || []).length ? ' (' + chk.down_servers.join(', ') + ' down)' : '') + ' \u00b7 ' + _dskAgo(chk.at);
        s.note    = 'backend degraded <b>' + sv.up + '/' + sv.total + ' servers</b>';
        s.noteIc  = 'ph-fill ph-warning';
        s.noteCls = 'd-warn';
    } else if (chk && chk.state === 'up') {
        s.health = 'up';
        s.dot    = 'sig-cell-ok';
        s.dotTip = (chk.self ? 'Online (self)'
            : chk.unverified ? 'Proxy answered ' + chk.status_code + ', backend not verified' + (chk.note ? '. ' + chk.note : '')
            : chk.via_target ? 'Backend online \u00b7 ' + chk.latency_ms + 'ms'
            : 'Online \u00b7 ' + chk.latency_ms + 'ms (' + chk.status_code + ')') + ' \u00b7 ' + _dskAgo(chk.at);
    } else if (chk && chk.state === 'pending') {
        s.dotTip = 'Router loaded, the last check failed' + (chk.error ? ': ' + chk.error : '') + ', confirming on the next pass';
    } else if (!_dskChecksOn()) {
        s.dotTip = 'Router loaded, route checks are off in Settings';
    } else if (!lnk.url) {
        s.dotTip = 'Router loaded, no backend health from Traefik and the rule has no host to check. Set a link in edit and it will be checked';
    } else {
        s.dotTip = 'Router loaded and enabled, Traefik reports no backend health for this service and it has not been checked yet';
    }

    if (!s.note && !s.url && lnk.why) {
        s.note    = lnk.why;
        s.noteIc  = lnk.glyph;
        s.noteCls = 'd-off';
    }
    return s;
}

function _dskIdleRank(x) {
    return x.s.health === 'idle' ? 1 : 0;
}

function _dskLabel(x) {
    return String(x.s.ov.display_name || x.r.name || '');
}

function _dskHostText(s, r) {
    if (s.url) return /^https:\/\//i.test(s.url) ? s.url.replace(/^https:\/\//i, '') : s.url;
    const t = r.target || r.service_name || '';
    return (t && t !== 'N/A') ? t : '';
}

function _dskRowTitle(r, s, name) {
    const bits = [];
    if (name !== r.name) bits.push(r.name);
    if (s.url) bits.push(s.url + ' \u2192 ' + (r.target && r.target !== 'N/A' ? r.target : (r.service_name || 'unknown backend')));
    else if (r.target && r.target !== 'N/A') bits.push('backend ' + r.target);
    bits.push('provider ' + (r.provider || 'file'));
    const eps = r.entryPoints || [];
    if (eps.length) bits.push('entry point ' + eps.join(', '));
    const nsrv = (r.servers || []).length;
    if (nsrv) bits.push(nsrv + (nsrv === 1 ? ' server' : ' servers'));
    const mws = r.middlewares || [];
    if (mws.length) bits.push(mws.length + ' middleware' + (mws.length === 1 ? '' : 's') + ': ' + mws.map(m => String(m).split('@')[0]).join(', '));
    if (r.certResolver) bits.push('cert resolver ' + r.certResolver);
    if (r.healthCheck && Object.keys(r.healthCheck).length) bits.push('active health check');
    if (s.hosts > 1) bits.push(s.hosts + ' hosts in the rule, the first is used');
    if (r.configFile) bits.push(r.configFile);
    if (s.note) bits.push(_dskPlain(s.note));
    return bits.join(' \u00b7 ');
}

function _dskPlate(r, name, s) {
    return '<span class="dsk-ic" data-mono="' + _esc(_dskMono(name)) + '">'
        + '<img class="dsk-ic-img" src="' + _esc(rmGetIconUrl(r)) + '" data-slug="' + _esc(window.rmIconSlug(r)) + '"'
        + ' alt="" loading="lazy" decoding="async" onerror="window.rmIconFallback(this)">'
        + '<span class="sig-cell dsk-dot ' + s.dot + '" data-rid="' + _esc(r.id) + '" title="' + _esc(s.dotTip) + '"></span>'
        + '</span>';
}

function dashBuildRouteRow(r, s) {
    const name  = s.ov.display_name || r.name;
    const proto = (r.protocol || 'http').toUpperCase();
    const host  = _dskHostText(s, r);
    const row   = document.createElement('div');

    row.className = 'dsk-row';
    if (s.health) row.dataset.health = s.health;
    if (s.health === 'down' || s.health === 'warn') row.tabIndex = -1;
    row.title = _dskRowTitle(r, s, name);

    row.innerHTML = _dskPlate(r, name, s)
        + '<span class="dsk-id">'
        + (proto !== 'HTTP' ? '<span class="d-proto">' + _esc(proto) + '</span>' : '')
        + (s.url
            ? '<a class="dsk-name" href="' + _esc(s.url) + '" target="_blank" rel="noopener noreferrer">' + _esc(name) + '</a>'
            : '<span class="dsk-name">' + _esc(name) + '</span>')
        + (host ? '<span class="dsk-host">' + _esc(host) + '</span>' : '')
        + '</span>'
        + (s.note
            ? '<span class="dsk-note"><i class="' + s.noteIc + ' ' + s.noteCls + '"></i><span class="dsk-note-t">' + s.note + '</span></span>'
            : '')
        + '<span class="dsk-rail">'
        + '<button type="button" class="dsk-btn" data-dsk="' + _esc(_dskSpec({ act: 'info', id: r.id })) + '"'
        + ' title="Route details" aria-label="Details for ' + _esc(name) + '"><i class="ph-bold ph-info"></i></button>'
        + '<button type="button" class="dsk-btn" data-dsk="' + _esc(_dskSpec({ act: 'edit', id: r.id })) + '"'
        + ' title="Edit route" aria-label="Edit ' + _esc(name) + '"><i class="ph-bold ph-pencil-simple"></i></button>'
        + '</span>';
    return row;
}

function dashBuildIconTile(r, s) {
    const name = s.ov.display_name || r.name;
    const host = _dskHostText(s, r);
    const tile = document.createElement('div');

    tile.className = 'dsk-tile';
    if (s.health) tile.dataset.health = s.health;
    if (s.health === 'down' || s.health === 'warn') tile.tabIndex = -1;
    if (!s.url) tile.dataset.launch = 'off';

    const tipBits = [name];
    if (s.note) tipBits.push(_dskPlain(s.note));
    else if (host) tipBits.push(host);
    const tip = _esc(tipBits.join(' \u00b7 '));

    tile.innerHTML = _dskPlate(r, name, s)
        + (s.url
            ? '<a class="dsk-tile-lk dsk-tile-name" href="' + _esc(s.url) + '" target="_blank" rel="noopener noreferrer" title="' + tip + '">' + _esc(name) + '</a>'
            : '<span class="dsk-tile-name" title="' + tip + '">' + _esc(name) + '</span>')
        + '<button type="button" class="dsk-tile-btn dsk-tile-btn-l" data-dsk="' + _esc(_dskSpec({ act: 'info', id: r.id })) + '"'
        + ' title="Route details" aria-label="Details for ' + _esc(name) + '"><i class="ph-bold ph-info"></i></button>'
        + '<button type="button" class="dsk-tile-btn" data-dsk="' + _esc(_dskSpec({ act: 'edit', id: r.id })) + '"'
        + ' title="Edit ' + _esc(name) + '" aria-label="Edit ' + _esc(name) + '"><i class="ph-bold ph-pencil-simple"></i></button>';
    return tile;
}

function _dskAlarm(meta, down, warn) {
    let html = '';
    if (down) {
        html += '<button type="button" class="sig-flag dsk-alarm" data-dsk="' + _esc(_dskSpec({ act: 'alarm', pod: meta.name })) + '"'
            + ' title="' + down + ' route' + (down === 1 ? '' : 's') + ' in ' + _esc(meta.name) + ' need attention">'
            + '<i class="ph-fill ph-warning-octagon"></i><b>' + down + '</b><span class="sig-fl">down</span></button>';
    }
    if (warn) {
        html += '<button type="button" class="sig-flag dsk-alarm dsk-alarm-warn" data-dsk="' + _esc(_dskSpec({ act: 'alarm', pod: meta.name })) + '"'
            + ' title="' + warn + ' route' + (warn === 1 ? '' : 's') + ' in ' + _esc(meta.name) + ' have a backend server down">'
            + '<i class="ph-fill ph-warning"></i><b>' + warn + '</b><span class="sig-fl">degraded</span></button>';
    }
    return html;
}

function dashBuildPod(entry) {
    const meta  = entry.meta;
    const icons = entry.icons;
    const list  = entry.entries;
    const limit = icons ? DASH_ICON_LIMIT : DASH_POD_LIMIT;
    const open  = _dskOpen.has(meta.name);
    const bodyId = 'dskbody-' + _dskSlug(meta.name) + (icons ? '-i' : '-l');

    const down = list.filter(x => x.s.health === 'down').length;
    const warn = list.filter(x => x.s.health === 'warn').length;

    const pod = document.createElement('section');
    pod.className = 'dsk-pod' + (icons ? ' dsk-pod-icons' : '');
    pod.dataset.pod = meta.name;
    if (down) pod.dataset.health = 'down';
    else if (warn) pod.dataset.health = 'warn';

    pod.innerHTML = '<div class="sig-ep-head">'
        + '<i class="ph-fill ' + _esc(meta.icon) + ' sig-ep-headic"></i>'
        + '<span class="sc-sec-label">' + _esc(meta.name) + '</span>'
        + '<span class="d-n">' + list.length + '</span>'
        + '<span class="sc-sec-rule"></span>'
        + _dskAlarm(meta, down, warn)
        + '</div>'
        + '<div class="dsk-body' + (icons ? ' dsk-tiles' : '') + '" id="' + bodyId + '"></div>';

    const body = pod.querySelector('.dsk-body');

    if (!list.length) {
        body.remove();
        const note = document.createElement('p');
        note.className = 'lg-note';
        note.textContent = 'Custom group with no routes yet. Assign one with the pencil on any route.';
        pod.appendChild(note);
        return pod;
    }

    (open ? list : list.slice(0, limit)).forEach(x => {
        body.appendChild(icons ? dashBuildIconTile(x.r, x.s) : dashBuildRouteRow(x.r, x.s));
    });

    if (list.length > limit) {
        const hidden = list.slice(limit);
        const hDown  = hidden.filter(x => x.s.health === 'down').length;
        const hWarn  = hidden.filter(x => x.s.health === 'warn').length;
        const noun   = icons ? 'apps' : 'routes';
        const btn    = document.createElement('button');
        btn.type = 'button';
        btn.className = 'dsk-more' + (open ? '' : (hDown ? ' dsk-more-bad' : (hWarn ? ' dsk-more-warn' : '')));
        btn.dataset.dsk = _dskSpec({ act: 'more', pod: meta.name });
        btn.setAttribute('aria-expanded', open ? 'true' : 'false');
        btn.setAttribute('aria-controls', bodyId);
        btn.setAttribute('aria-label', open
            ? 'Show fewer ' + noun + ' in ' + meta.name + ', ' + list.length + ' shown'
            : 'Show ' + hidden.length + ' more ' + noun + ' in ' + meta.name
              + (hDown ? ', ' + hDown + ' of them down' : '') + (hWarn ? ', ' + hWarn + ' of them degraded' : ''));
        btn.innerHTML = open
            ? '<i class="ph-bold ph-caret-up"></i>show less'
            : '<i class="ph-bold ph-caret-down"></i><b>' + hidden.length + '</b> more'
              + (hDown ? ' <span class="dsk-more-n">\u00b7 ' + hDown + ' down</span>' : '')
              + (hWarn ? ' <span class="dsk-more-w">\u00b7 ' + hWarn + ' degraded</span>' : '');
        pod.appendChild(btn);
    }
    return pod;
}

function _dskPodRank(name) {
    const bi = POD_RULES.findIndex(p => p.name === name);
    if (bi >= 0) return bi;
    if (name === 'Other') return 100000;
    const ci = window.rmGetCustomGroups().findIndex(g => g.name === name);
    return 1000 + (ci >= 0 ? ci : 999);
}

function dashRenderPods(routes) {
    const grid = document.getElementById('dashPodsGrid');
    if (!grid) return;
    grid.innerHTML = '';
    _dskPods.clear();

    const icons    = dashPodDensity() === 'icons';
    const unfilter = !_dashSearch && _dashProto === 'all' && _dashProvider === 'all';
    const podMap   = new Map();

    if (unfilter) {
        window.rmGetCustomGroups().forEach(g => {
            podMap.set(g.name, { meta: { name: g.name, icon: 'ph-tag' }, entries: [], icons: icons });
        });
    }
    routes.forEach(r => {
        const meta = rmGetPod(r);
        if (!podMap.has(meta.name)) podMap.set(meta.name, { meta: meta, entries: [], icons: icons });
        podMap.get(meta.name).entries.push({ r: r, s: _dskState(r) });
    });

    const pods = [...podMap.values()];
    pods.forEach(p => p.entries.sort((a, b) =>
        (_dskIdleRank(a) - _dskIdleRank(b)) || _dskColl.compare(_dskLabel(a), _dskLabel(b))));
    pods.sort((a, b) => (_dskPodRank(a.meta.name) - _dskPodRank(b.meta.name)) || _dskColl.compare(a.meta.name, b.meta.name));
    pods.forEach(p => {
        _dskPods.set(p.meta.name, p);
        grid.appendChild(dashBuildPod(p));
    });
}

function _dskChecksOn() {
    return !(window._rhMeta && window._rhMeta.loaded && window._rhMeta.enabled === false);
}

function _dskAgo(at) {
    if (!at) return '';
    const sec = Math.max(0, Math.floor(Date.now() / 1000) - at);
    if (sec < 60)   return 'checked just now';
    if (sec < 3600) return 'checked ' + Math.floor(sec / 60) + 'm ago';
    return 'checked ' + Math.floor(sec / 3600) + 'h ago';
}

function _dskTogglePod(name, force) {
    const entry = _dskPods.get(name);
    const grid  = document.getElementById('dashPodsGrid');
    if (!entry || !grid) return;
    const open = force === true ? true : !_dskOpen.has(name);
    if (open) _dskOpen.add(name); else _dskOpen.delete(name);

    const old = [...grid.children].find(el => el.dataset && el.dataset.pod === name);
    const fresh = dashBuildPod(entry);
    if (old) grid.replaceChild(fresh, old); else grid.appendChild(fresh);

    if (force === true) {
        const bad = fresh.querySelector('[data-health="down"]') || fresh.querySelector('[data-health="warn"]');
        if (bad) {
            bad.scrollIntoView({ block: 'nearest' });
            bad.focus({ preventScroll: true });
            return;
        }
    }
    const btn = fresh.querySelector('.dsk-more');
    if (btn) btn.focus({ preventScroll: true });
}

function _dashHostsOf(r) {
    const out = [];
    const re = /Host(?:SNI|Regexp)?\(`([^`]+)`\)/g;
    let m;
    while ((m = re.exec(r.rule || '')) !== null) out.push(m[1]);
    return out;
}

function _dashFilteredRoutes() {
    return _rmAllRoutes.filter(r => {
        if (((_rmConfig.route_overrides || {})[r.id] || {}).hidden) return false;
        if (_dashProto !== 'all' && r.protocol !== _dashProto) return false;
        if (_dashProvider !== 'all' && (r.provider || 'file') !== _dashProvider) return false;
        if (_dashSearch) {
            const ov  = (_rmConfig.route_overrides || {})[r.id] || {};
            const hay = [ov.display_name || '', r.name || '', r.service_name || '', r.target || '']
                .concat(_dashHostsOf(r)).join(' ').toLowerCase();
            if (!hay.includes(_dashSearch)) return false;
        }
        return true;
    });
}

window.dashFilterProvider = function(p) {
    _dashProvider = p;
    document.querySelectorAll('#dashProviderFilters .proto-btn').forEach(b => b.classList.remove('active-http'));
    const btn = document.getElementById('dashpf-' + p);
    if (btn) btn.classList.add('active-http');
    dashRender();
};

window.dashFilterProto = function(proto) {
    _dashProto = proto;
    document.querySelectorAll('#dashProtoFilters .proto-btn').forEach(b => b.classList.remove('active-http'));
    const btn = document.getElementById('dashf-' + proto);
    if (btn) btn.classList.add('active-http');
    dashRender();
};

window.dashApplyFilter = function() {
    const el = document.getElementById('dashSearch');
    const v  = el ? el.value.trim().toLowerCase() : '';
    if (_dashFilterTimer) clearTimeout(_dashFilterTimer);
    _dashFilterTimer = setTimeout(() => {
        _dashFilterTimer = null;
        if (v === _dashSearch) return;
        _dashSearch = v;
        dashRender();
    }, 120);
};

function dashRenderProviderFilters() {
    const container = document.getElementById('dashProviderFilters');
    if (!container) return;
    const providers = [...new Set(_rmAllRoutes.map(r => r.provider || 'file'))].sort();
    if (providers.length <= 1) {
        container.style.setProperty('display', 'none', 'important');
        return;
    }
    container.style.removeProperty('display');
    container.innerHTML = '';
    ['all', ...providers].forEach(p => {
        const btn = document.createElement('button');
        btn.id = 'dashpf-' + p;
        btn.className = 'proto-btn text-xs px-3 py-1.5' + (p === _dashProvider ? ' active-http' : '');
        btn.textContent = p === 'all' ? 'All' : p;
        btn.onclick = () => window.dashFilterProvider(p);
        container.appendChild(btn);
    });
}

function _dskEmptyPanel(total) {
    const ic   = document.getElementById('dashEmptyIc');
    const ttl  = document.getElementById('dashEmptyT');
    const note = document.getElementById('dashEmptyNote');
    const acts = document.getElementById('dashEmptyDo');
    if (!ic || !ttl || !note || !acts) return;

    const on = [];
    if (_dashSearch)             on.push('the search <code>' + _esc(_dashSearch) + '</code>');
    if (_dashProto !== 'all')    on.push('the <b>' + _esc(_dashProto) + '</b> protocol filter');
    if (_dashProvider !== 'all') on.push('the <b>' + _esc(_dashProvider) + '</b> provider filter');

    if (total && on.length) {
        ic.className  = 'ph-fill ph-funnel';
        ttl.textContent = 'Nothing matches';
        const listed = on.length === 1 ? on[0] : on.slice(0, -1).join(', ') + ' and ' + on[on.length - 1];
        note.innerHTML = total + ' route' + (total === 1 ? ' is' : 's are') + ' loaded. ' + listed
            + (on.length === 1 ? ' matches none of them.' : ' together match none of them.');
        acts.innerHTML = (_dashSearch
            ? '<button type="button" class="sig-flag d-blue" data-dsk="act=clear;what=search"><i class="ph-bold ph-x"></i>clear search</button>'
            : '')
            + '<button type="button" class="sig-flag d-blue" data-dsk="act=clear;what=all"><i class="ph-bold ph-arrow-counter-clockwise"></i>reset all filters</button>';
    } else {
        ic.className  = 'ph-fill ph-plus-circle';
        ttl.textContent = 'No routes yet';
        note.innerHTML = 'No routes are managed here and the Traefik API reported none. Add one from the Routes tab, or point traefik-manager at a config file that already has some.';
        acts.innerHTML = '';
    }
}

function dashRender() {
    const pods  = document.getElementById('dashPodsContainer');
    const empty = document.getElementById('dashEmpty');
    const deg   = document.getElementById('dashDegraded');
    if (!pods || !empty) return;
    if (deg) deg.classList.add('hidden');

    const routes = _dashFilteredRoutes();
    if (!routes.length) {
        pods.classList.add('hidden');
        empty.classList.remove('hidden');
        _dskEmptyPanel(_rmAllRoutes.length);
        return;
    }
    empty.classList.add('hidden');
    pods.classList.remove('hidden');
    document.getElementById('dashBlind')?.classList.toggle('hidden', !_rmStatusBlind);
    dashRenderPods(routes);
}

function _dskGo(p) {
    if (p.act === 'info')  { window.rmOpenRouteInfo(p.id); return; }
    if (p.act === 'edit')  { window.rmOpenEditModal(p.id); return; }
    if (p.act === 'unhide') { window.rmUnhideRoute(p.id); return; }
    if (p.act === 'more')  { _dskTogglePod(p.pod, null);   return; }
    if (p.act === 'alarm') { _dskTogglePod(p.pod, true);   return; }
    if (p.act === 'retry') { _dashDrawn = false; window.refreshDashboardTab(); return; }
    if (p.act === 'clear') {
        if (p.what === 'search' || p.what === 'all') {
            _dashSearch = '';
            if (_dashFilterTimer) { clearTimeout(_dashFilterTimer); _dashFilterTimer = null; }
            const inp = document.getElementById('dashSearch');
            if (inp) inp.value = '';
        }
        if (p.what === 'all') {
            _dashProto    = 'all';
            _dashProvider = 'all';
            document.querySelectorAll('#dashProtoFilters .proto-btn').forEach(b => b.classList.remove('active-http'));
            document.getElementById('dashf-all')?.classList.add('active-http');
            document.querySelectorAll('#dashProviderFilters .proto-btn').forEach(b => b.classList.remove('active-http'));
            document.getElementById('dashpf-all')?.classList.add('active-http');
        }
        dashRender();
    }
}

function _dskBind() {
    if (_dskBound) return;
    _dskBound = true;
    document.addEventListener('click', e => {
        if (!e.target || typeof e.target.closest !== 'function') return;
        const t = e.target.closest('[data-dsk]');
        if (!t || t.hasAttribute('disabled')) return;
        const scopes = ['tab-dashboard', 'rmGroupsModal', 'rmEditModal'];
        if (!scopes.some(id => document.getElementById(id)?.contains(t))) return;
        e.preventDefault();
        e.stopPropagation();
        _dskGo(_dskParse(t.getAttribute('data-dsk')));
    });
}

window.rmOpenRouteInfo = function(routeId) {
    const r = _rmAllRoutes.find(x => x.id === routeId);
    if (r) openRouteDetail(r.name, r.protocol, r);
};

window.refreshDashboardTab = async function() {
    const loading = document.getElementById('dashLoading');
    const pods    = document.getElementById('dashPodsContainer');
    const empty   = document.getElementById('dashEmpty');
    const deg     = document.getElementById('dashDegraded');
    _dskBind();

    if (!_dashDrawn && window.rmHydrate()) {
        _dashDrawn = true;
        dashRenderProviderFilters();
        dashRender();
    }

    if (!_dashDrawn) {
        if (loading) loading.classList.remove('hidden');
        if (pods)  pods.classList.add('hidden');
        if (empty) empty.classList.add('hidden');
        if (deg)   deg.classList.add('hidden');
    }

    const ok = await window.rmEnsureData(false, { services: true });
    if (loading) loading.classList.add('hidden');

    if (!ok) {
        const first = !_dashDrawn;
        _dashDrawn = false;
        if (pods)  pods.classList.add('hidden');
        if (empty) empty.classList.add('hidden');
        if (deg)   deg.classList.remove('hidden');
        if (first) showToast('Could not load dashboard data.', 'error');
        return;
    }
    if (typeof window._rhLoad === 'function') await window._rhLoad(_rmServerId());
    _dashDrawn = true;
    dashRenderProviderFilters();
    dashRender();
};

window.rmInvalidateGroups = function() {
    if (document.getElementById('tab-dashboard')?.classList.contains('active')) dashRender();
};

window.rmInvalidateDashboard = function() {
    _dashDrawn = false;
};

})();
